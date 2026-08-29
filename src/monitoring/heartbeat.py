# src/monitoring/heartbeat.py
"""Heartbeat — Latidos del sistema con métricas de sistema"""

import time
import psutil
from datetime import datetime
from typing import Dict, Any

class Heartbeat:
    def __init__(self, interval: int = 60):
        self.interval = interval
        self.counter = 0
        self.last_pulse = None

    async def pulse(self) -> Dict[str, Any]:
        self.counter += 1
        self.last_pulse = datetime.now()
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory()
        return {
            "counter": self.counter,
            "timestamp": self.last_pulse.isoformat(),
            "cpu_percent": cpu,
            "memory_percent": mem.percent,
            "status": "ALIVE"
        }

    def get_state(self) -> Dict:
        return {
            "counter": self.counter,
            "last_pulse": self.last_pulse.isoformat() if self.last_pulse else None,
            "interval": self.interval
        }
