# src/monitoring/telemetry.py
"""Telemetry — Envío de métricas a sistemas externos"""

import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
from src.utils.logger import get_logger

class Telemetry:
    def __init__(self, config: Dict):
        self.config = config
        self.enabled = config.get('enabled', False)
        self.endpoint = config.get('endpoint', '')
        self.logger = get_logger()
        self.last_timestamp = None

    def record_event(self, event_name: str, data: Optional[Dict] = None):
        """Registra un evento en el log."""
        if self.enabled:
            self.logger.info("TELEMETRY", f"Evento: {event_name}", extra={'data': data})
        self.last_timestamp = datetime.now().isoformat()

    def record_heartbeat(self, pulse: Dict):
        self.record_event('heartbeat', pulse)

    def record_order(self, order_result: Dict):
        self.record_event('order', order_result)

    def record_metrics(self, metrics: Dict):
        self.record_event('metrics', metrics)

    def record_daps(self, score):
        self.record_event('daps', {'score': score.overall})

    def get_last_timestamp(self) -> str:
        return self.last_timestamp or datetime.now().isoformat()