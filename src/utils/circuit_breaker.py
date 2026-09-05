"""
Circuit Breaker — Protección contra fallos repetidos con integración @retry
"""
import time
from typing import Dict, Optional
from src.utils.logger import get_logger

logger = get_logger()

class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 5, timeout: float = 60.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def record_success(self):
        self.failure_count = 0
        if self.state == "HALF_OPEN":
            self.state = "CLOSED"
            logger.info(f"🔓 Circuit breaker {self.name} cerró (éxito)")

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(f"🔒 Circuit breaker {self.name} abrió (fallos: {self.failure_count})")

    def can_execute(self) -> bool:
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "HALF_OPEN"
                logger.info(f"🔓 Circuit breaker {self.name} en HALF_OPEN (timeout alcanzado)")
                return True
            return False
        if self.state == "HALF_OPEN":
            return True
        return False

    def get_status(self) -> Dict:
        return {
            "name": self.name,
            "state": self.state,
            "failure_count": self.failure_count,
            "last_failure": self.last_failure_time,
            "threshold": self.failure_threshold,
            "timeout": self.timeout
        }
