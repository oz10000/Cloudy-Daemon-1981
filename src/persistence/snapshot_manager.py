"""Gestión de snapshots con reintentos."""
from typing import Dict, Any, Optional
from datetime import datetime
from src.utils.logger import get_logger
from src.utils.retry import retry

logger = get_logger("snapshot_manager")

class SnapshotManager:
    def __init__(self, store):
        self.store = store
        self.logger = logger
        self._last_key = "last_snapshot"

    @retry(max_attempts=3, delay=0.5, backoff=2.0, exceptions=(Exception,))
    async def save(self, state: Dict[str, Any]) -> bool:
        state['timestamp'] = datetime.now().isoformat()
        self.logger.info(f"SNAPSHOT — Guardando snapshot (timestamp: {state['timestamp']})")
        return await self.store.save_state(self._last_key, state)

    @retry(max_attempts=3, delay=0.5, backoff=2.0, exceptions=(Exception,))
    async def load_latest(self) -> Optional[Dict]:
        state = await self.store.load_state(self._last_key)
        if state:
            self.logger.info(f"SNAPSHOT — Snapshot cargado (timestamp: {state.get('timestamp')})")
        return state
