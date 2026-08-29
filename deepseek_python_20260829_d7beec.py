"""
Supervisor — Gestión de tareas con health checks y reinicios
"""

import asyncio
import time
from typing import Dict, Any, Callable, Awaitable, Optional
from dataclasses import dataclass, field
from src.utils.logger import get_logger

@dataclass
class TaskStatus:
    name: str
    healthy: bool = True
    last_restart: float = 0.0
    restart_count: int = 0
    last_error: str = ""
    uptime: float = 0.0
    last_health_check: float = 0.0

class Supervisor:
    """
    Supervisor de tareas con reinicio automático, backoff exponencial
    y health checks periódicos.
    """
    
    def __init__(self, max_restarts: int = 10, backoff_base: int = 5):
        self.logger = get_logger()
        self.tasks: Dict[str, asyncio.Task] = {}
        self.statuses: Dict[str, TaskStatus] = {}
        self.max_restarts = max_restarts
        self.backoff_base = backoff_base
        self._running = False
        self._health_check_task: Optional[asyncio.Task] = None

    async def start(self):
        """Inicia el supervisor."""
        self._running = True
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        self.logger.info("SUPERVISOR", "Supervisor iniciado")

    async def _health_check_loop(self):
        """Loop de verificación de salud de tareas."""
        while self._running:
            for name, task in list(self.tasks.items()):
                if task.done():
                    status = self.statuses.get(name)
                    if status:
                        status.healthy = False
                        # El wrap_task maneja el reinicio automático
                elif self.statuses.get(name):
                    self.statuses[name].healthy = True
                    self.statuses[name].last_health_check = time.time()
            await asyncio.sleep(10)

    async def wrap_task(self, name: str, coro: Awaitable) -> None:
        """Envuelve una tarea con supervisión y reinicio automático."""
        self.statuses[name] = TaskStatus(name=name)
        
        while self._running:
            start_time = time.time()
            try:
                await coro
                # Si la tarea termina sin error, esperar un poco y reiniciar si es necesario
                if self._running:
                    self.logger.info("SUPERVISOR", f"Tarea {name} finalizada, reiniciando...")
                    await asyncio.sleep(1)
                continue
            except asyncio.CancelledError:
                self.logger.warning("SUPERVISOR", f"Tarea {name} cancelada")
                break
            except Exception as e:
                self.logger.error("SUPERVISOR", f"Tarea {name} falló: {e}")
                status = self.statuses[name]
                status.healthy = False
                status.last_error = str(e)
                status.restart_count += 1
                status.uptime = time.time() - start_time
                status.last_restart = time.time()
                
                if status.restart_count > self.max_restarts:
                    self.logger.critical("SUPERVISOR", f"Demasiados reinicios para {name}, deteniendo")
                    raise RuntimeError(f"Task {name} failed too many times")
                
                backoff = self.backoff_base * min(status.restart_count, 10)
                self.logger.info("SUPERVISOR", f"Reiniciando {name} en {backoff}s (intento {status.restart_count})")
                await asyncio.sleep(backoff)
                status.healthy = True
                continue
            break

    def register_task(self, name: str, task: asyncio.Task):
        """Registra una tarea ya creada."""
        self.tasks[name] = task
        if name not in self.statuses:
            self.statuses[name] = TaskStatus(name=name)

    def get_status(self) -> Dict[str, bool]:
        """Retorna el estado de salud de todas las tareas."""
        return {name: status.healthy for name, status in self.statuses.items()}

    def get_full_status(self) -> Dict[str, Dict]:
        """Retorna el estado completo de todas las tareas."""
        return {
            name: {
                'healthy': status.healthy,
                'restart_count': status.restart_count,
                'last_error': status.last_error,
                'uptime': status.uptime,
                'last_restart': status.last_restart
            }
            for name, status in self.statuses.items()
        }

    def is_healthy(self, name: str) -> bool:
        """Verifica si una tarea específica está saludable."""
        status = self.statuses.get(name)
        return status is not None and status.healthy

    async def stop(self):
        """Detiene el supervisor y todas las tareas."""
        self._running = False
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except:
                pass
        
        for name, task in self.tasks.items():
            if not task.done():
                task.cancel()
        
        if self.tasks:
            await asyncio.wait([t for t in self.tasks.values() if not t.done()], timeout=10)
        
        self.logger.info("SUPERVISOR", "Supervisor detenido")