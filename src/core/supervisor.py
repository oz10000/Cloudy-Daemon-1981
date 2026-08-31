# src/core/supervisor.py
import asyncio
import time
from typing import Dict, Any, Callable, Awaitable, Optional
from src.utils.logger import get_logger

class Supervisor:
    def __init__(self, max_restarts: int = 10, backoff_base: int = 5):
        self.logger = get_logger()
        self.tasks: Dict[str, asyncio.Task] = {}
        self.statuses: Dict[str, Dict] = {}
        self.max_restarts = max_restarts
        self.backoff_base = backoff_base
        self._running = False
        self._health_check_task: Optional[asyncio.Task] = None

    async def start(self):
        self._running = True
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        self.logger.info("SUPERVISOR — Supervisor iniciado")  # CORREGIDO

    async def _health_check_loop(self):
        while self._running:
            for name, task in list(self.tasks.items()):
                if task.done():
                    if name in self.statuses:
                        self.statuses[name]['healthy'] = False
                else:
                    if name in self.statuses:
                        self.statuses[name]['healthy'] = True
                        self.statuses[name]['last_health_check'] = time.time()
            await asyncio.sleep(10)

    async def wrap_task(self, name: str, coro: Awaitable) -> None:
        self.statuses[name] = {'healthy': True, 'restart_count': 0, 'last_restart': 0, 'uptime': 0, 'last_error': ''}
        while self._running:
            start_time = time.time()
            try:
                await coro
                if self._running:
                    self.logger.info(f"SUPERVISOR — Tarea {name} finalizada, reiniciando...")
                    await asyncio.sleep(1)
                continue
            except asyncio.CancelledError:
                self.logger.warning(f"SUPERVISOR — Tarea {name} cancelada")
                break
            except Exception as e:
                self.logger.error(f"SUPERVISOR — Tarea {name} falló: {e}")
                status = self.statuses[name]
                status['healthy'] = False
                status['last_error'] = str(e)
                status['restart_count'] += 1
                status['uptime'] = time.time() - start_time
                status['last_restart'] = time.time()
                if status['restart_count'] > self.max_restarts:
                    self.logger.critical(f"SUPERVISOR — Demasiados reinicios para {name}, deteniendo")
                    raise RuntimeError(f"Task {name} failed too many times")
                backoff = self.backoff_base * min(status['restart_count'], 10)
                self.logger.info(f"SUPERVISOR — Reiniciando {name} en {backoff}s (intento {status['restart_count']})")
                await asyncio.sleep(backoff)
                status['healthy'] = True
                continue
            break

    def register_task(self, name: str, task: asyncio.Task):
        self.tasks[name] = task
        if name not in self.statuses:
            self.statuses[name] = {'healthy': True, 'restart_count': 0, 'last_restart': 0, 'uptime': 0, 'last_error': ''}

    def get_status(self) -> Dict[str, bool]:
        return {name: status['healthy'] for name, status in self.statuses.items()}

    def get_full_status(self) -> Dict[str, Dict]:
        return self.statuses.copy()

    def is_healthy(self, name: str) -> bool:
        status = self.statuses.get(name)
        return status is not None and status['healthy']

    async def stop(self):
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
        self.logger.info("SUPERVISOR — Supervisor detenido")
