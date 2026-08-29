"""
Event Loop Manager — Control de bucle de eventos asíncrono
"""

import asyncio
import time
from typing import Dict, Any, List, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from src.utils.logger import get_logger

class TaskPriority(Enum):
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4

@dataclass
class ScheduledTask:
    id: str
    coro: Callable[[], Awaitable[Any]]
    priority: TaskPriority = TaskPriority.NORMAL
    interval: float = 0.0  # 0 = una sola vez
    last_run: float = 0.0
    running: bool = False
    name: str = ""

class EventLoopManager:
    """
    Administrador del event loop con priorización de tareas,
    monitoreo de rendimiento y control de tiempo.
    """
    
    def __init__(self):
        self.logger = get_logger()
        self.tasks: Dict[str, ScheduledTask] = {}
        self.loop = asyncio.get_event_loop()
        self.running = False
        self.metrics: Dict[str, Any] = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'avg_latency_ms': 0.0
        }
        self._task_counter = 0
        self._latency_samples: List[float] = []
        self._max_latency_samples = 100

    def register_task(self, name: str, coro: Callable[[], Awaitable[Any]], 
                      priority: TaskPriority = TaskPriority.NORMAL,
                      interval: float = 0.0) -> str:
        """Registra una tarea en el loop."""
        self._task_counter += 1
        task_id = f"{name}_{self._task_counter}"
        self.tasks[task_id] = ScheduledTask(
            id=task_id,
            coro=coro,
            priority=priority,
            interval=interval,
            name=name
        )
        self.logger.debug("EVENT_LOOP", f"Tarea registrada: {name} (id={task_id})")
        return task_id

    async def run(self):
        """Ejecuta el event loop."""
        self.running = True
        self.logger.info("EVENT_LOOP", "Event Loop iniciado")

        # Ordenar tareas por prioridad
        sorted_tasks = sorted(self.tasks.values(), key=lambda t: t.priority.value)

        while self.running:
            for task in sorted_tasks:
                if not self.running:
                    break
                if task.running:
                    continue
                
                # Verificar si debe ejecutarse
                now = time.time()
                if task.interval > 0 and (now - task.last_run) < task.interval:
                    continue

                # Ejecutar tarea
                try:
                    task.running = True
                    self.metrics['total_tasks'] += 1
                    start = time.perf_counter()
                    
                    # Ejecutar el coro
                    if asyncio.iscoroutinefunction(task.coro):
                        await task.coro()
                    else:
                        # Si es una función síncrona, ejecutar en thread pool
                        await asyncio.to_thread(task.coro)
                    
                    elapsed_ms = (time.perf_counter() - start) * 1000
                    self._latency_samples.append(elapsed_ms)
                    if len(self._latency_samples) > self._max_latency_samples:
                        self._latency_samples.pop(0)
                    
                    self.metrics['completed_tasks'] += 1
                    self.metrics['avg_latency_ms'] = sum(self._latency_samples) / len(self._latency_samples)
                    
                    task.last_run = now
                    
                except Exception as e:
                    self.logger.error("EVENT_LOOP", f"Tarea {task.name} falló: {e}")
                    self.metrics['failed_tasks'] += 1
                finally:
                    task.running = False

                # Pequeña pausa para no saturar
                await asyncio.sleep(0.001)

            # Si no hay tareas, esperar un poco
            if not any(t.running for t in sorted_tasks):
                await asyncio.sleep(0.1)

        self.logger.info("EVENT_LOOP", "Event Loop detenido")

    async def stop(self):
        """Detiene el event loop."""
        self.running = False
        self.logger.info("EVENT_LOOP", "Deteniendo event loop...")

    def get_metrics(self) -> Dict[str, Any]:
        """Retorna métricas del event loop."""
        return {
            **self.metrics,
            'tasks_registered': len(self.tasks),
            'tasks_running': sum(1 for t in self.tasks.values() if t.running),
            'avg_latency_ms': self.metrics['avg_latency_ms'],
            'pending_tasks': len([t for t in self.tasks.values() if not t.running and t.interval > 0])
        }

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retorna el estado de una tarea específica."""
        task = self.tasks.get(task_id)
        if not task:
            return None
        return {
            'id': task.id,
            'name': task.name,
            'priority': task.priority.name,
            'interval': task.interval,
            'last_run': task.last_run,
            'running': task.running
        }
