"""Sistema de latidos para monitorizar la salud del daemon (con métricas)."""
import psutil
from datetime import datetime
from typing import Dict, Any
from src.utils.logger import get_logger

logger = get_logger("heartbeat")

class Heartbeat:
    def __init__(self, interval: int = 60):
        self.interval = interval
        self.last_pulse = None
        self.counter = 0

    async def pulse(self) -> Dict[str, Any]:
        """Genera un latido con métricas del sistema."""
        self.counter += 1
        self.last_pulse = datetime.now()
        return {
            "counter": self.counter,
            "timestamp": self.last_pulse.isoformat(),
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "status": "ALIVE"
        }

    def get_state(self) -> Dict:
        """Retorna el estado actual del heartbeat."""
        return {
            "counter": self.counter,
            "last_pulse": self.last_pulse.isoformat() if self.last_pulse else None,
            "interval": self.interval
        }

    def ping(self) -> None:
        """Registra un ping simple (para compatibilidad con el daemon)."""
        self.counter += 1
        self.last_pulse = datetime.now()
        logger.debug(f"HEARTBEAT — Ping #{self.counter}")
