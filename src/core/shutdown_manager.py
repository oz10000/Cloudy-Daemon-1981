"""Gestión de apagado graceful con hooks y timeouts."""
import asyncio
from typing import List, Callable, Awaitable, Optional
from src.utils.logger import get_logger

logger = get_logger("shutdown_manager")

class ShutdownHook:
    def __init__(self, name: str, callback: Callable[[], Awaitable[None]], timeout: float = 5.0):
        self.name = name
        self.callback = callback
        self.timeout = timeout

class ShutdownManager:
    def __init__(self):
        self._hooks: List[ShutdownHook] = []
        self._shutdown_in_progress = False

    def register_hook(self, hook: ShutdownHook) -> None:
        self._hooks.append(hook)
        logger.info(f"SHUTDOWN — Hook '{hook.name}' registrado")

    async def shutdown(self) -> None:
        if self._shutdown_in_progress:
            return
        self._shutdown_in_progress = True
        logger.info("SHUTDOWN — Iniciando apagado graceful")
        for hook in reversed(self._hooks):
            try:
                await asyncio.wait_for(hook.callback(), timeout=hook.timeout)
                logger.info(f"SHUTDOWN — Hook '{hook.name}' completado")
            except asyncio.TimeoutError:
                logger.error(f"SHUTDOWN — Hook '{hook.name}' timeout ({hook.timeout}s)")
            except Exception as e:
                logger.error(f"SHUTDOWN — Hook '{hook.name}' falló: {e}")
        logger.info("SHUTDOWN — Apagado completado")
