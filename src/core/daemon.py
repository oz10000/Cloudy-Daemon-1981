"""
Daemon 1981 Ω V3 — Núcleo del sistema
"""

import asyncio
import signal
import sys
from typing import Dict, Any, List

from src.core.event_loop import EventLoopManager
from src.core.supervisor import Supervisor
from src.core.lifecycle import LifecycleManager, LifecycleState
from src.core.state_machine import StateMachine, State
from src.core.shutdown_manager import ShutdownManager

from src.persistence.sqlite_store import SQLiteStore
from src.persistence.snapshot_manager import SnapshotManager
from src.persistence.recovery import RecoveryManager

from src.execution.signal_engine import SignalEngine
from src.execution.execution_engine import ExecutionEngine
from src.execution.order_manager import OrderManager
from src.execution.position_manager import PositionManager
from src.execution.reconciliation import Reconciliation

from src.risk.risk_engine import RiskEngine
from src.risk.emergency_stop import EmergencyStop, EmergencyStopReason
from src.risk.leverage_manager import LeverageManager

from src.exchanges.base import ExchangeFactory

from src.daps.anomaly_engine import AnomalyEngine

from src.certification.certifier import Certifier

from src.repair.repair_engine import RepairEngine

from src.monitoring.heartbeat import Heartbeat
from src.monitoring.metrics import MetricsCollector
from src.monitoring.telemetry import Telemetry

from src.utils.logger import get_logger, setup_logger


class Daemon1981Omega:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = get_logger()

        # Core
        self.state_machine = StateMachine()
        self.lifecycle = LifecycleManager()
        self.supervisor = Supervisor()
        self.shutdown_manager = ShutdownManager()
        self.event_loop = EventLoopManager()
        self.running = True

        # Persistencia
        self.store = SQLiteStore(config.get('persistence', {}))
        self.snapshot_manager = SnapshotManager(self.store)
        self.recovery = RecoveryManager(self.store, self.snapshot_manager)

        # Monitoreo
        self.heartbeat = Heartbeat(config.get('heartbeat_interval', 60))
        self.metrics = MetricsCollector()
        self.telemetry = Telemetry(config.get('telemetry', {}))

        # Exchange
        exchange_config = config.get('exchanges', {})
        self.exchange = ExchangeFactory.create(
            exchange_config.get('primary', 'simulator'),
            exchange_config
        )

        # Riesgo
        self.risk_engine = RiskEngine(config.get('risk', {}))
        self.emergency_stop = EmergencyStop()
        self.leverage_manager = LeverageManager(config.get('leverage', {}))

        # Ejecución
        self.order_manager = OrderManager()
        self.position_manager = PositionManager()
        self.signal_engine = SignalEngine(config.get('signal_source', {}))
        self.reconciliation = Reconciliation(self.exchange, self.position_manager, self.order_manager)
        self.execution_engine = ExecutionEngine(
            self.exchange, self.order_manager, self.position_manager, self.risk_engine
        )

        # DAPS
        self.anomaly_engine = AnomalyEngine()

        # Reparación
        self.repair_engine = RepairEngine(config.get('repair', {}))

        # Certificación
        self.certifier = Certifier(config.get('certification', {}))

        # Tareas
        self.tasks: List[asyncio.Task] = []

        # Señales
        self.shutdown_manager.register_signal_handlers()
        self.shutdown_manager.register_hook("save_state", self._save_final_state, priority=1)
        self.shutdown_manager.register_hook("close_exchange", self._close_exchange, priority=2)

    async def run(self):
        self.logger.info("DAEMON — 1981 DAEMON Ω V3 iniciando...")
        self.state_machine.transition_to(State.BOOT)
        await self.lifecycle.transition_to(LifecycleState.BOOT)  # CORREGIDO: await
        self.telemetry.record_event("daemon_started")

        await self._init_components()
        await self.supervisor.start()

        task_coros = [
            ("heartbeat", self._heartbeat_task),
            ("signal", self._signal_task),
            ("execution", self._execution_task),
            ("reconciliation", self._reconciliation_task),
            ("snapshot", self._snapshot_task),
            ("monitor", self._monitor_task),
            ("repair", self._repair_task)
        ]

        for name, coro in task_coros:
            task = asyncio.create_task(self.supervisor.wrap_task(name, coro()))
            self.supervisor.register_task(name, task)
            self.tasks.append(task)

        await self.shutdown_manager.wait_for_shutdown_async()

    async def _init_components(self):
        self.logger.info("INIT — Inicializando componentes...")
        self.state_machine.transition_to(State.INIT)
        await self.lifecycle.transition_to(LifecycleState.INIT)

        snapshot = await self.recovery.recover()
        if snapshot:
            await self.position_manager.restore(snapshot.get('positions', []))
            await self.order_manager.restore(snapshot.get('orders', []))
            self.logger.info(f"INIT — Estado restaurado: {len(snapshot.get('positions', []))} posiciones")

        if not await self._self_test():
            self.logger.error("INIT — Self-test fallido")
            self.state_machine.transition_to(State.ERROR)
            await self.lifecycle.transition_to(LifecycleState.ERROR)
            raise RuntimeError("Self-test fallido")

        if self.config.get('certification', {}).get('enabled', True):
            await self._certify_modules()

        self.state_machine.transition_to(State.STANDALONE)
        await self.lifecycle.transition_to(LifecycleState.STANDALONE)
        self.logger.info("INIT — Sistema listo en modo STANDALONE")

    async def _self_test(self) -> bool:
        self.logger.info("SELFTEST — Ejecutando self-test...")
        self.state_machine.transition_to(State.SELF_TEST)
        await self.lifecycle.transition_to(LifecycleState.SELF_TEST)

        try:
            await self.store.save_state({'test': 'ok'})
            test = await self.store.load_state()
            if test.get('test') != 'ok':
                raise RuntimeError("Persistencia falló")

            health = await self.exchange.health_check()
            if not health.is_connected:
                raise RuntimeError("Exchange no conectado")

            self.logger.info("SELFTEST — Self-test completado")
            return True
        except Exception as e:
            self.logger.error(f"SELFTEST — Falló: {e}")
            return False

    async def _certify_modules(self):
        self.logger.info("CERTIFY — Certificando módulos...")
        self.state_machine.transition_to(State.CERTIFY)
        await self.lifecycle.transition_to(LifecycleState.CERTIFY)

        modules = [
            ('exchange', self.exchange),
            ('risk_engine', self.risk_engine),
            ('execution_engine', self.execution_engine),
            ('signal_engine', self.signal_engine),
            ('repair_engine', self.repair_engine)
        ]

        for name, module in modules:
            result = await self.certifier.certify_module(module)
            if not result['certified']:
                self.logger.error(f"CERTIFY — Fallo certificación de {name}: {result}")
                raise RuntimeError(f"Certificación fallida para {name}")
            self.logger.info(f"CERTIFY — {name} certificado (score={result['score']:.1f}%)")

        self.logger.info("CERTIFY — Todos los módulos certificados")

    # --- Tareas periódicas ---

    async def _heartbeat_task(self):
        while self.running:
            pulse = await self.heartbeat.pulse()
            self.telemetry.record_heartbeat(pulse)
            self.state_machine.transition_to(State.LIVE)
            await self.lifecycle.transition_to(LifecycleState.LIVE)
            await asyncio.sleep(self.heartbeat.interval)

    async def _signal_task(self):
        while self.running:
            if self.emergency_stop.is_active():
                await asyncio.sleep(1)
                continue

            signals = await self.signal_engine.read_signals()
            for signal in signals:
                if self.emergency_stop.is_active():
                    break
                leverage = self.leverage_manager.get_optimal_leverage(signal)
                signal['leverage'] = leverage
                if self.risk_engine.can_open_position(signal, self.position_manager):
                    result = await self.execution_engine.execute(signal)
                    self.telemetry.record_order(result)
                else:
                    self.logger.warning(f"SIGNAL — Señal rechazada: {signal.get('symbol')}")
            await asyncio.sleep(5)

    async def _execution_task(self):
        while self.running:
            await self.execution_engine.process_pending_orders()
            if hasattr(self.exchange, 'get_price'):
                try:
                    price = await self.exchange.get_price('BTCUSDT')
                    await self.position_manager.update_prices('BTCUSDT', price, self.exchange)
                except Exception as e:
                    self.logger.warning(f"EXEC — Error actualizando precios: {e}")
            await self.execution_engine.check_exits()
            await asyncio.sleep(1)

    async def _reconciliation_task(self):
        while self.running:
            await self.reconciliation.sync()
            await asyncio.sleep(60)

    async def _snapshot_task(self):
        while self.running:
            await self.snapshot_manager.save_snapshot(
                positions=self.position_manager.to_dict(),
                orders=self.order_manager.to_dict()
            )
            await asyncio.sleep(300)

    async def _monitor_task(self):
        while self.running:
            metrics = await self.metrics.collect(self.position_manager, self.order_manager)
            self.telemetry.record_metrics(metrics)
            daps_score = await self.anomaly_engine.analyze(metrics)
            self.telemetry.record_daps(daps_score)
            if daps_score.overall < 40:
                self.logger.warning(f"DAPS — Score crítico: {daps_score.overall}")
                self.emergency_stop.activate(EmergencyStopReason.DAPS_CRITICAL)
            await asyncio.sleep(60)

    async def _repair_task(self):
        while self.running:
            issues = await self.repair_engine.detect(self.position_manager, self.order_manager, self.exchange)
            if issues:
                self.logger.warning(f"REPAIR — {len(issues)} issues detectados")
                for issue in issues:
                    await self.repair_engine.repair(issue, self.position_manager, self.order_manager, self.exchange)
            await asyncio.sleep(30)

    async def _save_final_state(self):
        self.logger.info("SHUTDOWN — Guardando estado final...")
        await self.store.save_state({
            'positions': self.position_manager.to_dict(),
            'orders': self.order_manager.to_dict(),
            'timestamp': self.telemetry.get_last_timestamp()
        })

    async def _close_exchange(self):
        self.logger.info("SHUTDOWN — Cerrando conexiones exchange...")
        await self.exchange.close()
        await self.signal_engine.close()
