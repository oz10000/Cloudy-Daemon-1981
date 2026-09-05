"""Recuperación de estado con reintentos."""
from typing import Optional, Dict, Any
from src.utils.logger import get_logger
from src.utils.retry import retry

logger = get_logger("recovery")

class RecoveryManager:
    def __init__(self, snapshot_manager):
        self.snapshot_manager = snapshot_manager
        self.logger = logger

    @retry(max_attempts=3, delay=1.0, backoff=2.0, exceptions=(Exception,))
    async def recover(self) -> Optional[Dict[str, Any]]:
        self.logger.info("RECOVERY — Intentando recuperar estado")
        state = await self.snapshot_manager.load_latest()
        if state:
            self.logger.info(f"RECOVERY — Estado recuperado: {state.get('timestamp')}")
        else:
            self.logger.info("RECOVERY — No hay estado previo")
        return state
