# src/persistence/recovery.py
"""Recovery Manager — Recuperación ante fallos"""

from typing import Dict, Any, Optional
from src.persistence.sqlite_store import SQLiteStore
from src.persistence.snapshot_manager import SnapshotManager

class RecoveryManager:
    def __init__(self, store: SQLiteStore, snapshot_manager: SnapshotManager):
        self.store = store
        self.snapshot_manager = snapshot_manager

    async def recover(self) -> Optional[Dict]:
        """Intenta recuperar el estado desde el último snapshot válido."""
        return await self.snapshot_manager.load_latest_snapshot()
