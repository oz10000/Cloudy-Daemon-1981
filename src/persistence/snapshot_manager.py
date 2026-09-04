"""
Snapshot Manager — Gestión de snapshots periódicos
"""
import json
import os
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
from src.utils.logger import get_logger
from src.persistence.sqlite_store import SQLiteStore
from src.persistence.json_backup import JSONBackup

class SnapshotManager:
    def __init__(self, store: SQLiteStore, backup_dir: str = './data/snapshots'):
        self.store = store
        self.backup_dir = backup_dir
        self.logger = get_logger()
        self.backup = JSONBackup(backup_dir)
        os.makedirs(backup_dir, exist_ok=True)

    async def save_snapshot(self, positions: List, orders: List) -> bool:
        data = {
            'timestamp': datetime.now().isoformat(),
            'positions': positions,
            'orders': orders
        }
        success = await self.store.save_state(data)
        if success:
            filename = f"snapshot_{int(time.time())}.json"
            await self.backup.save(data, filename)
            self.logger.debug(f"Snapshot guardado: {len(positions)} pos, {len(orders)} ord")
        return success

    async def load_latest_snapshot(self) -> Optional[Dict]:
        state = await self.store.load_state()
        if state:
            # CORREGIDO: se usa un solo argumento en logger
            self.logger.info(f"SNAPSHOT: Snapshot cargado desde SQLite (timestamp: {state.get('timestamp')})")
            return state
        latest = await self.backup.load_latest()
        if latest:
            self.logger.info("SNAPSHOT: Snapshot cargado desde JSON backup")
            return latest
        return None

    async def list_snapshots(self) -> List[str]:
        return await self.backup.list_files()
