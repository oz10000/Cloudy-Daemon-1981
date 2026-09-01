"""
Daemon1981 — Orquestador principal event-driven (bajo consumo)
"""
import asyncio
import os
import signal
import sys
from typing import Dict, Any
from datetime import datetime

from src.core.state_machine import DaemonState, StateMachine
from src.core.shutdown_manager import ShutdownManager
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

class Daemon1981:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = get_logger()
        self.running = False
        self.busy = False
        self._initialized = False

        self.state_machine = StateMachine()
        self.shutdown_manager = ShutdownManager()
        self.shutdown_manager.register_signal_handlers()
        self.shutdown_manager.register_hook("save_final_state", self._save_final_state, priority=1)

        # Persistencia
        self.store = SQLiteStore(config.get('persistence', {}))
        self.snapshot_manager = SnapshotManager(self.store)
        self.recovery = RecoveryManager(self.store, self.snapshot_manager)

        # Heartbeat
        self.heartbeat = Heartbeat(config.get('heartbeat_interval', 60))

        # Exchange
        exchange_config = config.get('exchange', {})
        exchange_name = exchange_config.get('name', 'simulator')
        self.exchange = ExchangeFactory.create(exchange_name, exchange_config)

        # Logging de configuración (un solo argumento)
        self.logger.info(f"Exchange: {exchange_name}")
        self.logger.info(f"Leverage: {exchange_config.get('leverage', 1)}X")
        self.logger.info(f"Capital usage: {exchange_config.get('capital_usage', 1.0)*100}%")
        self.logger.info(f"Max positions: {config.get('risk', {}).get('max_positions', 1)}")

        # Gestión de órdenes y posiciones
        self.order_manager = OrderManager()
        self.position_manager = PositionManager()

        # Riesgo
        risk_config = config.get('risk', {})
        self.risk_engine = RiskEngine(risk_config, self.position_manager)
        self.emergency_stop = EmergencyStop()

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
            order_manager=self.order_manager,
            position_manager=self.position_manager,
            risk_engine=self.risk_engine
        )

        self.check_interval = signal_config.get('check_interval', 300)
        self._shutdown_event = asyncio.Event()

        # Asegurar directorios
        ensure_directories(['./data/logs', './data/state', './data/snapshots'])

        # La recuperación se hará en run() para poder usar await
        self._restore_task = None

    async def _restore_state(self):
        """Recupera el estado desde persistencia (async)."""
        state = await self.recovery.recover()
        if state:
            positions = state.get('positions', [])
            if positions:
                self.position_manager.restore(positions)
                self.logger.info(f"Posiciones recuperadas: {len(positions)}")
                if any(p.get('state') == 'OPEN' for p in positions):
                    self.state_machine.transition_to(DaemonState.POSITION_ACTIVE)
            orders = state.get('orders', [])
            if orders:
                self.order_manager.restore(orders)
                self.logger.info(f"Órdenes recuperadas: {len(orders)}")
        else:
            self.logger.info("No se encontró estado previo, iniciando desde cero")

    async def _save_final_state(self):
        self.logger.info("Guardando estado final...")
        await self.store.save_state({
            'positions': self.position_manager.to_dict(),
            'orders': self.order_manager.to_dict(),
            'timestamp': datetime.now().isoformat()
        })

    async def run(self):
        # Recuperar estado antes de entrar al bucle
        await self._restore_state()

        self.running = True
        self.logger.info("Daemon iniciado (event-driven)")

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        self.state_machine.transition_to(DaemonState.SLEEPING)

        while self.running:
            try:
                if self.state_machine.get_state() == DaemonState.SHUTDOWN:
                    break

                if self.position_manager.has_open_positions():
                    await self._monitor_positions()
                    await asyncio.sleep(10)
                    continue

                if self.busy:
                    self.logger.debug("Ocupado, saltando ciclo")
                    await asyncio.sleep(5)
                    continue

                await self._check_for_signal()
                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error en bucle principal: {e}", exc_info=True)
                self.state_machine.transition_to(DaemonState.ERROR)
                await asyncio.sleep(10)

        self.logger.info("Daemon detenido")

    def _signal_handler(self, signum, frame):
        self.logger.info(f"Señal {signum} recibida")
        asyncio.create_task(self.shutdown())

    async def shutdown(self):
        self.running = False
        self.state_machine.transition_to(DaemonState.SHUTDOWN)
        await self._save_final_state()
        await self.exchange.close()
        self.logger.info("Apagado completado")
        sys.exit(0)

    async def _check_for_signal(self):
        self.state_machine.transition_to(DaemonState.WAITING_EVENT)
        signals = await self.signal_watcher.check_and_fetch()
        if not signals:
            self.logger.debug("No hay nuevas señales")
            self.state_machine.transition_to(DaemonState.SLEEPING)
            return

        self.busy = True
        self.state_machine.transition_to(DaemonState.EVENT_RECEIVED)

        try:
            filtered = self.tier_manager.filter_signals(signals)
            if not filtered:
                self.logger.info("Todas las señales filtradas por tiers")
                self.state_machine.transition_to(DaemonState.SLEEPING)
                return

            signal = filtered[0]
            self.logger.info(f"Señal seleccionada: {signal.get('symbol')} {signal.get('direction')} Tier:{signal.get('level')}")

            self.state_machine.transition_to(DaemonState.VALIDATING)
            if not self.risk_engine.can_open_position(signal):
                self.logger.info("Señal rechazada por riesgo")
                self.state_machine.transition_to(DaemonState.SLEEPING)
                return

            self.state_machine.transition_to(DaemonState.RISK_APPROVAL)
            self.state_machine.transition_to(DaemonState.EXECUTING)
            result = await self.execution_engine.execute(signal)

            if result.get('status') == 'executed':
                self.logger.info(f"Orden ejecutada: {result.get('position_id')}")
                self.state_machine.transition_to(DaemonState.POSITION_ACTIVE)
                await self._save_final_state()
            else:
                self.logger.error(f"Error ejecución: {result.get('reason')}")
                self.state_machine.transition_to(DaemonState.ERROR)

        except Exception as e:
            self.logger.error(f"Error procesando señal: {e}", exc_info=True)
            self.state_machine.transition_to(DaemonState.ERROR)
        finally:
            self.busy = False
            self.state_machine.transition_to(DaemonState.SLEEPING)

    async def _monitor_positions(self):
        if not self.position_manager.has_open_positions():
            return
        self.state_machine.transition_to(DaemonState.MONITORING)
        try:
            await self.execution_engine.check_exits()
            if not self.position_manager.has_open_positions():
                self.state_machine.transition_to(DaemonState.CERTIFICATION)
                await self._save_final_state()
                self.logger.info("Posición cerrada, certificada")
                self.state_machine.transition_to(DaemonState.SLEEPING)
        except Exception as e:
            self.logger.error(f"Error en monitoreo: {e}", exc_info=True)
