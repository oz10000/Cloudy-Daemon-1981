# src/persistence/sqlite_store.py
"""SQLite Store — Persistencia con integridad"""

import sqlite3
import json
import hashlib
import os
from typing import Dict, Any, Optional
from datetime import datetime

class SQLiteStore:
    def __init__(self, config: Dict):
        self.path = config.get('path', './data/state/daemon.db')
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.path)
        cursor = conn.cursor()
        cursor.execute('PRAGMA journal_mode=WAL')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                data TEXT NOT NULL,
                checksum TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()

    async def save_state(self, data: Dict) -> bool:
        conn = sqlite3.connect(self.path)
        cursor = conn.cursor()
        json_data = json.dumps(data)
        checksum = hashlib.sha256(json_data.encode()).hexdigest()
        cursor.execute('''
            INSERT OR REPLACE INTO state (id, data, checksum, updated_at)
            VALUES (1, ?, ?, ?)
        ''', (json_data, checksum, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return True

    async def load_state(self) -> Optional[Dict]:
        conn = sqlite3.connect(self.path)
        cursor = conn.cursor()
        cursor.execute('SELECT data, checksum FROM state WHERE id = 1')
        row = cursor.fetchone()
        conn.close()
        if row:
            data, checksum = row
            if hashlib.sha256(data.encode()).hexdigest() == checksum:
                return json.loads(data)
        return None