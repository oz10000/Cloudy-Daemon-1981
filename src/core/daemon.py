"""Orquestador principal event-driven con reintentos y circuit breaker."""
import asyncio
import os
import signal
from typing import Dict, Any
from datetime import datetime

from src.core.state_machine import DaemonState, StateMachine
from src.core.shutdown_manager import ShutdownManager, ShutdownHook
from src.execution.signal_watcher import SignalWatcher
from src.execution.tier_manager import TierManager
from src.execution.execution_engine import ExecutionEngine
from src.execution.order_manager import OrderManager
from src.execution.position_manager import PositionManager
from src.risk.risk_engine import RiskEngine
from src.risk.emergency_stop import EmergencyStop
from src.exchanges.base import ExchangeFactory
from src.persistence.sqlite_store import SQLiteStore
from src.persistence.snapshot_manager import SnapshotManager
from src.persistence.recovery import RecoveryManager
from src.monitoring.heartbeat import Heartbeat
from src.utils.logger import get_logger
from src.utils.file_manager import ensure_directories
from src.utils.retry import retry
from src.utils.circuit_breaker import CircuitBreaker

logger = get_logger("daemon")

class Daemon1981:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logger
        self.running = False
        self.busy = False

        self.state_machine = StateMachine()
        self.shutdown_manager = ShutdownManager()
        self.shutdown_manager.register_hook(ShutdownHook("save_state", self._save_final_state, timeout=5.0))

        # Persistencia
        self.store = SQLiteStore(config.get('persistence', {}))
        self.snapshot_manager = SnapshotManager(self.store)
        self.recovery = RecoveryManager(self.snapshot_manager)

        # Heartbeat
        self.heartbeat = Heartbeat(config.get('heartbeat_interval', 60))

        # Exchange
        exchange_config = config.get('exchange', {})
        exchange_name = exchange_config.get('name', 'simulator')
        self.exchange = ExchangeFactory.create(exchange_name, exchange_config)

        self.logger.info(f"Exchange: {exchange_name}")
        self.logger.info(f"Leverage: {exchange_config.get('leverage', 1)}X")
        self.logger.info(f"Capital usage: {exchange_config.get('capital_usage', 1.0)*100}%")
        self.logger.info(f"Max positions: {config.get('risk', {}).get('max_positions', 1)}")

        # Gestión de órdenes y posiciones
        self.order_manager = OrderManager(self.exchange)
        self.position_manager = PositionManager(self.exchange, self.store)

        # Riesgo
        risk_config = config.get('risk', {})
        self.risk_engine = RiskEngine(
            max_risk_per_trade=risk_config.get('risk_per_trade', 0.02),
            max_position_size=1000.0,
            default_leverage=exchange_config.get('leverage', 1)
        )
        self.emergency_stop = EmergencyStop(self.exchange)

        # Tier Manager
        tier_config = config.get('tier_filter', {})
        self.tier_manager = TierManager(tier_config.get('config_path', './config/tiers.yaml'))

        # Signal Watcher
        signal_config = config.get('signal_source', {})
        self.signal_watcher = SignalWatcher(
            repo=signal_config.get('repo', 'oz10000/D.A.P.S-Sognals'),
            token=os.environ.get('GH_PAT'),
            state_file='./data/state/last_signal.yaml'
        )

        # Execution Engine
        self.execution_engine = ExecutionEngine(
            exchange=self.exchange,
            risk_engine=self.risk_engine,
            order_manager=self.order_manager,
            position_manager=self.position_manager
        )

        self.check_interval = signal_config.get('check_interval', 300)

        # Circuit breaker para GitHub
        self.github_cb = CircuitBreaker("github", failure_threshold=3, timeout=60.0)

        ensure_directories(['./data/logs', './data/state', './data/snapshots'])

        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        self.logger.info(f"Señal {signum} recibida")
        self.running = False

    async def _restore_state(self):
        try:
            state = await asyncio.wait_for(self.recovery.recover(), timeout=10.0)
            if state:
                positions = state.get('positions', [])
                for pos_data in positions:
                    await self.position_manager.add_position(pos_data, {})
                self.logger.info(f"Estado restaurado: {len(positions)} posiciones")
        except asyncio.TimeoutError:
            self.logger.error("Timeout restaurando estado (10s)")
        except Exception as e:
            self.logger.error(f"Error restaurando estado: {e}")

    async def _save_final_state(self):
        try:
            state = {
                'timestamp': datetime.now().isoformat(),
                'positions': self.position_manager.get_all(),
                'state': self.state_machine.current_state.name
            }
            await asyncio.wait_for(self.snapshot_manager.save(state), timeout=5.0)
            self.logger.info("Estado final guardado")
        except Exception as e:
            self.logger.error(f"Error guardando estado final: {e}")

    @retry(max_attempts=2, delay=5.0, backoff=2.0, exceptions=(Exception,))
    async def _check_for_signal(self):
        if not self.github_cb.can_execute():
            self.logger.warning("Circuit breaker GitHub abierto, saltando check")
            return
        try:
            signals = await asyncio.wait_for(
                self.signal_watcher.check_and_fetch(),
                timeout=30.0
            )
            if signals:
                self.github_cb.record_success()
                self.logger.info(f"Señales recibidas: {len(signals)}")
                await self._process_signals(signals)
            else:
                self.logger.debug("No hay nuevas señales")
        except asyncio.TimeoutError:
            self.github_cb.record_failure()
            self.logger.error("Timeout al buscar señales (30s)")
        except Exception as e:
            self.github_cb.record_failure()
            self.logger.error(f"Error obteniendo señales: {e}")

    async def _process_signals(self, signals):
        self.state_machine.transition(DaemonState.WAITING_EVENT, DaemonState.EVENT_RECEIVED)
        filtered = self.tier_manager.filter_signals(signals)
        for signal in filtered:
            try:
                await asyncio.wait_for(
                    self.execution_engine.execute(signal),
                    timeout=20.0
                )
            except asyncio.TimeoutError:
                self.logger.error(f"Timeout ejecutando señal {signal.get('symbol')}")
            except Exception as e:
                self.logger.error(f"Error ejecutando señal: {e}")
        self.state_machine.transition(DaemonState.EVENT_RECEIVED, DaemonState.SLEEPING)

    async def _monitor_positions(self):
        try:
            await asyncio.wait_for(
                self.execution_engine.check_exits(),
                timeout=15.0
            )
        except asyncio.TimeoutError:
            self.logger.error("Timeout monitoreando posiciones")
        except Exception as e:
            self.logger.error(f"Error monitoreando posiciones: {e}")

    async def run(self):
        await self._restore_state()
        self.running = True
        self.logger.info("Daemon iniciado (event-driven)")

        # El estado inicial ya es SLEEPING, no se necesita transición a sí mismo.
        # self.state_machine.transition(DaemonState.SLEEPING, DaemonState.SLEEPING)  # ← ELIMINADO

        while self.running:
            try:
                current = self.state_machine.current_state
                if current == DaemonState.SLEEPING:
                    self.state_machine.transition(DaemonState.SLEEPING, DaemonState.WAITING_EVENT)
                elif current == DaemonState.WAITING_EVENT:
                    await self._check_for_signal()
                elif current in (DaemonState.POSITION_ACTIVE, DaemonState.MONITORING):
                    await self._monitor_positions()
                elif current == DaemonState.ERROR:
                    self.logger.warning("En estado ERROR, esperando recuperación...")
                    await asyncio.sleep(10)
                    self.state_machine.transition(DaemonState.ERROR, DaemonState.SLEEPING)
                elif current == DaemonState.SHUTDOWN:
                    break

                if int(datetime.now().timestamp()) % 60 == 0:
                    self.heartbeat.ping()

                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                self.logger.info("Bucle cancelado")
                break
            except Exception as e:
                self.logger.error(f"Error crítico: {e}")
                self.state_machine.transition(DaemonState.WAITING_EVENT, DaemonState.ERROR)

        await self.shutdown_manager.shutdown()
