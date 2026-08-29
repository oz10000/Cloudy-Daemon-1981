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

from src.exchanges.base import ExchangeFactory

from src.daps.anomaly_engine import AnomalyEngine

from src.certification.certifier import Certifier

from src.repair.repair_engine import RepairEngine

from src.monitoring.heartbeat import Heartbeat
from src.monitoring.metrics import MetricsCollector
from src.monitoring.telemetry import Telemetry

from src.utils.logger import get_logger, setup_logger

class Daemon1981Omega:
    """Daemon principal del sistema 1981 Ω V3."""
    
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
        """Punto de entrada principal."""
        self.logger.info("DAEMON", "1981 DAEMON Ω V3 iniciando...")
        self.state_machine.transition_to(State.BOOT)
        self.lifecycle.transition_to(LifecycleState.BOOT)
        self.telemetry.record_event("daemon_started")
        
        # Inicializar
        await self._init_components()
        
        # Iniciar supervisor
        await self.supervisor.start()
        
        # Registrar tareas en el supervisor
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
        
        # Esperar shutdown
        await self.shutdown_manager.wait_for_shutdown_async()

    async def _init_components(self):
        """Inicializa componentes y restaura estado."""
        self.logger.info("INIT", "Inicializando componentes...")
        self.state_machine.transition_to(State.INIT)
        self.lifecycle.transition_to(LifecycleState.INIT)
        
        # Recuperar estado anterior
        snapshot = await self.recovery.recover()
        if snapshot:
            await self.position_manager.restore(snapshot.get('positions', []))
            await self.order_manager.restore(snapshot.get('orders', []))
            self.logger.info("INIT", f"Estado restaurado: {len(snapshot.get('positions', []))} posiciones")
        
        # Self-test
        if not await self._self_test():
            self.logger.error("INIT", "Self-test fallido")
            self.state_machine.transition_to(State.ERROR)
            self.lifecycle.transition_to(LifecycleState.ERROR)
            raise RuntimeError("Self-test fallido")
        
        # Certificar
        if self.config.get('certification', {}).get('enabled', True):
            await self._certify_modules()
        
        self.state_machine.transition_to(State.STANDALONE)
        self.lifecycle.transition_to(LifecycleState.STANDALONE)
        self.logger.info("INIT", "Sistema listo en modo STANDALONE")

    async def _self_test(self) -> bool:
        """Ejecuta autodiagnóstico."""
        self.logger.info("SELFTEST", "Ejecutando self-test...")
        self.state_machine.transition_to(State.SELF_TEST)
        self.lifecycle.transition_to(LifecycleState.SELF_TEST)
        
        try:
            # Probar almacenamiento
            await self.store.save_state({'test': 'ok'})
            test = await self.store.load_state()
            if test.get('test') != 'ok':
                raise RuntimeError("Persistencia falló")
            
            # Probar exchange
            health = await self.exchange.health_check()
            if not health.is_connected:
                raise RuntimeError("Exchange no conectado")
            
            self.logger.info("SELFTEST", "Self-test completado")
            return True
        except Exception as e:
            self.logger.error("SELFTEST", f"Falló: {e}")
            return False

    async def _certify_modules(self):
        """Certifica todos los módulos críticos."""
        self.logger.info("CERTIFY", "Certificando módulos...")
        self.state_machine.transition_to(State.CERTIFY)
        self.lifecycle.transition_to(LifecycleState.CERTIFY)
        
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
                self.logger.error("CERTIFY", f"Fallo certificación de {name}: {result}")
                raise RuntimeError(f"Certificación fallida para {name}")
            self.logger.info("CERTIFY", f"{name} certificado (score={result['score']:.1f}%)")
        
        self.logger.info("CERTIFY", "Todos los módulos certificados")

    # --- Tareas periódicas ---
    
    async def _heartbeat_task(self):
        while self.running:
            pulse = await self.heartbeat.pulse()
            self.telemetry.record_heartbeat(pulse)
            self.state_machine.transition_to(State.LIVE)
            self.lifecycle.transition_to(LifecycleState.LIVE)
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
                if self.risk_engine.can_open_position(signal):
                    result = await self.execution_engine.execute(signal)
                    self.telemetry.record_order(result)
                else:
                    self.logger.warning("RISK", f"Señal rechazada: {signal.get('symbol')}")
            await asyncio.sleep(5)

    async def _execution_task(self):
        while self.running:
            await self.execution_engine.process_pending_orders()
            await self.position_manager.update_prices(
                'BTCUSDT', await self.exchange.get_price('BTCUSDT')
            )
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
                self.logger.warning("DAPS", f"Score crítico: {daps_score.overall}")
                self.emergency_stop.activate(EmergencyStopReason.DAPS_CRITICAL)
            await asyncio.sleep(60)

    async def _repair_task(self):
        while self.running:
            issues = await self.repair_engine.detect(self.position_manager, self.order_manager, self.exchange)
            if issues:
                self.logger.warning("REPAIR", f"{len(issues)} issues detectados")
                for issue in issues:
                    await self.repair_engine.repair(issue, self.position_manager, self.order_manager, self.exchange)
            await asyncio.sleep(30)

    # --- Hooks de apagado ---
    
    async def _save_final_state(self):
        self.logger.info("SHUTDOWN", "Guardando estado final...")
        await self.store.save_state({
            'positions': self.position_manager.to_dict(),
            'orders': self.order_manager.to_dict(),
            'timestamp': self.telemetry.get_last_timestamp()
        })

    async def _close_exchange(self):
        self.logger.info("SHUTDOWN", "Cerrando conexiones exchange...")
        await self.exchange.close()
        await self.signal_engine.close()