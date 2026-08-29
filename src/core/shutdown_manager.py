"""
Shutdown Manager — Gestión de apagado seguro con timeouts y cleanup
"""

import asyncio
import signal
import sys
import time
from typing import List, Dict, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from src.utils.logger import get_logger

class ShutdownPhase(Enum):
    INITIATED = 0
    SIGNAL_RECEIVED = 1
    CANCEL_TASKS = 2
    CLEANUP = 3
    FINALIZE = 4
    COMPLETE = 5

@dataclass
class ShutdownHook:
    name: str
    callback: Callable[[], Awaitable[Any]]
    priority: int = 10  # menor = más prioritario
    timeout: float = 30.0

class ShutdownManager:
    """
    Administrador de apagado seguro con hooks, timeouts y fallback.
    """
    
    def __init__(self):
        self.logger = get_logger()
        self.hooks: List[ShutdownHook] = []
        self.is_shutting_down = False
        self.shutdown_event = asyncio.Event()
        self.phase = ShutdownPhase.INITIATED
        self.start_time: Optional[float] = None
        self.total_timeout = 60.0  # segundos máximo para todo el shutdown
        self._signal_handlers_registered = False

    def register_hook(self, name: str, callback: Callable[[], Awaitable[Any]], 
                      priority: int = 10, timeout: float = 30.0):
        """Registra un hook de apagado."""
        self.hooks.append(ShutdownHook(name, callback, priority, timeout))
        self.hooks.sort(key=lambda h: h.priority)
        self.logger.debug("SHUTDOWN", f"Hook registrado: {name} (prioridad={priority})")

    def register_signal_handlers(self):
        """Registra manejadores de señales."""
        if self._signal_handlers_registered:
            return
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        self._signal_handlers_registered = True
        self.logger.info("SHUTDOWN", "Manejadores de señales registrados")

    def _signal_handler(self, signum, frame):
        """Manejador de señales."""
        self.logger.info("SHUTDOWN", f"Señal recibida: {signum}")
        asyncio.create_task(self.shutdown(reason=f"Signal {signum}"))

    async def shutdown(self, reason: str = "Manual", force: bool = False) -> bool:
        """Inicia el apagado del sistema."""
        if self.is_shutting_down:
            self.logger.warning("SHUTDOWN", "Apagado ya en progreso")
            return False

        self.is_shutting_down = True
        self.start_time = time.time()
        self.phase = ShutdownPhase.INITIATED
        self.logger.info("SHUTDOWN", f"Iniciando apagado: {reason}")

        try:
            # Fase 1: Señal
            self.phase = ShutdownPhase.SIGNAL_RECEIVED
            self.logger.info("SHUTDOWN", "Fase 1/5: Señal recibida")

            # Fase 2: Cancelar tareas
            self.phase = ShutdownPhase.CANCEL_TASKS
            self.logger.info("SHUTDOWN", "Fase 2/5: Cancelando tareas...")
            await self._cancel_tasks()

            # Fase 3: Cleanup (hooks)
            self.phase = ShutdownPhase.CLEANUP
            self.logger.info("SHUTDOWN", "Fase 3/5: Ejecutando cleanup...")
            if force:
                self.logger.warning("SHUTDOWN", "Apagado forzado, saltando hooks")
            else:
                await self._run_hooks()

            # Fase 4: Finalizar
            self.phase = ShutdownPhase.FINALIZE
            self.logger.info("SHUTDOWN", "Fase 4/5: Finalizando...")

            # Fase 5: Completar
            self.phase = ShutdownPhase.COMPLETE
            self.shutdown_event.set()
            self.logger.info("SHUTDOWN", f"Fase 5/5: Apagado completado en {time.time() - self.start_time:.2f}s")

            return True

        except Exception as e:
            self.logger.error("SHUTDOWN", f"Error durante apagado: {e}")
            self.shutdown_event.set()
            return False

    async def _cancel_tasks(self):
        """Cancela todas las tareas asíncronas."""
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        if not tasks:
            return

        self.logger.info("SHUTDOWN", f"Cancelando {len(tasks)} tareas...")
        
        for task in tasks:
            task.cancel()
        
        # Esperar a que se cancelen con timeout
        try:
            await asyncio.wait(tasks, timeout=self.total_timeout / 2)
        except asyncio.CancelledError:
            pass

        # Verificar tareas que no se cancelaron
        remaining = [t for t in tasks if not t.done()]
        if remaining:
            self.logger.warning("SHUTDOWN", f"{len(remaining)} tareas no se cancelaron correctamente")

    async def _run_hooks(self):
        """Ejecuta los hooks de apagado en orden."""
        for hook in self.hooks:
            if time.time() - self.start_time > self.total_timeout:
                self.logger.warning("SHUTDOWN", f"Timeout global alcanzado, saltando hook {hook.name}")
                break

            try:
                self.logger.debug("SHUTDOWN", f"Ejecutando hook: {hook.name}")
                await asyncio.wait_for(hook.callback(), timeout=hook.timeout)
            except asyncio.TimeoutError:
                self.logger.warning("SHUTDOWN", f"Hook {hook.name} timeout después de {hook.timeout}s")
            except Exception as e:
                self.logger.error("SHUTDOWN", f"Hook {hook.name} falló: {e}")

    def wait_for_shutdown(self):
        """Espera a que el sistema se apague."""
        return self.shutdown_event.wait()

    async def wait_for_shutdown_async(self, timeout: Optional[float] = None):
        """Espera asíncronamente a que el sistema se apague."""
        try:
            await asyncio.wait_for(self.shutdown_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            self.logger.warning("SHUTDOWN", "Timeout esperando apagado")

    def get_status(self) -> Dict[str, Any]:
        """Retorna el estado del shutdown."""
        return {
            'is_shutting_down': self.is_shutting_down,
            'phase': self.phase.name,
            'start_time': self.start_time,
            'elapsed': time.time() - self.start_time if self.start_time else 0,
            'hooks': [{'name': h.name, 'priority': h.priority} for h in self.hooks],
            'total_hooks': len(self.hooks),
            'total_timeout': self.total_timeout
        }
