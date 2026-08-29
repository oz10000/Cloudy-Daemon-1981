"""
JSON Backup — Guardado y recuperación de backups en JSON
"""

import json
import os
import glob
from typing import Dict, Any, Optional, List
from datetime import datetime

class JSONBackup:
    """Gestor de backups en JSON con rotación."""
    
    def __init__(self, backup_dir: str, max_files: int = 5):
        self.backup_dir = backup_dir
        self.max_files = max_files
        os.makedirs(backup_dir, exist_ok=True)

    async def save(self, data: Dict, filename: str) -> bool:
        """Guarda un backup."""
        filepath = os.path.join(self.backup_dir, filename)
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            await self._rotate()
            return True
        except Exception as e:
            print(f"Error guardando backup: {e}")
            return False

    async def load(self, filename: str) -> Optional[Dict]:
        """Carga un backup específico."""
        filepath = os.path.join(self.backup_dir, filename)
        if not os.path.exists(filepath):
            return None
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception:
            return None

    async def load_latest(self) -> Optional[Dict]:
        """Carga el backup más reciente."""
        files = glob.glob(os.path.join(self.backup_dir, "*.json"))
        if not files:
            return None
        latest = max(files, key=os.path.getctime)
        return await self.load(os.path.basename(latest))

    async def list_files(self) -> List[str]:
        """Lista los archivos de backup."""
        return sorted(glob.glob(os.path.join(self.backup_dir, "*.json")))

    async def _rotate(self):
        """Mantiene solo los N archivos más recientes."""
        files = glob.glob(os.path.join(self.backup_dir, "*.json"))
        if len(files) > self.max_files:
            files.sort(key=os.path.getctime)
            for f in files[:-self.max_files]:
                os.remove(f)
