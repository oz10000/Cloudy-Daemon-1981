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
    """Crea y restaura snapshots del sistema."""
    
    def __init__(self, store: SQLiteStore, backup_dir: str = './data/snapshots'):
        self.store = store
        self.backup_dir = backup_dir
        self.logger = get_logger()
        self.backup = JSONBackup(backup_dir)
        os.makedirs(backup_dir, exist_ok=True)

    async def save_snapshot(self, positions: List, orders: List) -> bool:
        """Guarda un snapshot del estado actual."""
        data = {
            'timestamp': datetime.now().isoformat(),
            'positions': positions,
            'orders': orders
        }
        
        # Guardar en SQLite
        success = await self.store.save_state(data)
        if success:
            # Guardar backup en JSON
            filename = f"snapshot_{int(time.time())}.json"
            await self.backup.save(data, filename)
            self.logger.debug("SNAPSHOT", f"Snapshot guardado: {len(positions)} pos, {len(orders)} ord")
        
        return success

    async def load_latest_snapshot(self) -> Optional[Dict]:
        """Carga el snapshot más reciente."""
        # Intentar cargar desde SQLite primero
        state = await self.store.load_state()
        if state:
            self.logger.info("SNAPSHOT", f"Snapshot cargado desde SQLite (timestamp: {state.get('timestamp')})")
            return state
        
        # Fallback: cargar último JSON
        latest = await self.backup.load_latest()
        if latest:
            self.logger.info("SNAPSHOT", "Snapshot cargado desde JSON backup")
            return latest
        
        return None

    async def list_snapshots(self) -> List[str]:
        """Lista todos los snapshots disponibles."""
        return await self.backup.list_files()