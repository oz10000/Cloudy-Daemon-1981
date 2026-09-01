"""
Shutdown Manager — Gestión de apagado graceful
"""
import asyncio
import signal
import time
from typing import List, Dict, Any, Callable, Awaitable
from src.utils.logger import get_logger

class ShutdownHook:
    def __init__(self, name: str, callback: Callable[[], Awaitable[Any]], priority: int = 10, timeout: float = 30.0):
        self.name = name
        self.callback = callback
        self.priority = priority
        self.timeout = timeout

class ShutdownManager:
    def __init__(self):
        self.logger = get_logger()
        self.hooks: List[ShutdownHook] = []
        self.is_shutting_down = False
        self.shutdown_event = asyncio.Event()
        self._signal_handlers_registered = False

    def register_hook(self, name: str, callback: Callable[[], Awaitable[Any]], priority: int = 10, timeout: float = 30.0):
        self.hooks.append(ShutdownHook(name, callback, priority, timeout))
        self.hooks.sort(key=lambda h: h.priority)
        self.logger.debug(f"Shutdown hook registrado: {name} (prioridad={priority})")

    def register_signal_handlers(self):
        if self._signal_handlers_registered:
            return
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        self._signal_handlers_registered = True
        # CORREGIDO: un solo argumento
        self.logger.info("SHUTDOWN: Manejadores de señales registrados")

    def _signal_handler(self, signum, frame):
        self.logger.info(f"SHUTDOWN: Señal {signum} recibida")
        asyncio.create_task(self.shutdown(reason=f"Signal {signum}"))

    async def shutdown(self, reason: str = "Manual", force: bool = False) -> bool:
        if self.is_shutting_down:
            self.logger.warning("SHUTDOWN: Apagado ya en progreso")
            return False

        self.is_shutting_down = True
        self.logger.info(f"SHUTDOWN: Iniciando apagado por {reason}")

        try:
            # Cancelar tareas asíncronas
            tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            if tasks:
                self.logger.info(f"SHUTDOWN: Cancelando {len(tasks)} tareas...")
                for task in tasks:
                    task.cancel()
                await asyncio.wait(tasks, timeout=10)

            # Ejecutar hooks
            if not force:
                for hook in self.hooks:
                    try:
                        self.logger.debug(f"SHUTDOWN: Ejecutando hook {hook.name}")
                        await asyncio.wait_for(hook.callback(), timeout=hook.timeout)
                    except asyncio.TimeoutError:
                        self.logger.warning(f"SHUTDOWN: Hook {hook.name} timeout")
                    except Exception as e:
                        self.logger.error(f"SHUTDOWN: Hook {hook.name} falló: {e}")

            self.shutdown_event.set()
            self.logger.info("SHUTDOWN: Apagado completado")
            return True

        except Exception as e:
            self.logger.error(f"SHUTDOWN: Error durante apagado: {e}")
            self.shutdown_event.set()
            return False

    def wait_for_shutdown(self):
        return self.shutdown_event.wait()
