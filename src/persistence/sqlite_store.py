"""Almacenamiento persistente SQLite con WAL, checksum y reintentos."""
import sqlite3
import json
import hashlib
import os
from typing import Dict, Any, Optional
from datetime import datetime
from src.utils.logger import get_logger
from src.utils.retry import retry

logger = get_logger("sqlite_store")

class SQLiteStore:
    def __init__(self, config: Dict):
        self.path = config.get('path', './data/state/daemon.db')
        self.logger = logger
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
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                id TEXT PRIMARY KEY,
                data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

    @retry(max_attempts=3, delay=0.5, backoff=2.0, exceptions=(sqlite3.OperationalError,))
    async def save_state(self, key: str, value: Dict) -> bool:
        conn = sqlite3.connect(self.path)
        cursor = conn.cursor()
        json_data = json.dumps(value)
        checksum = hashlib.sha256(json_data.encode()).hexdigest()
        cursor.execute(
            "INSERT OR REPLACE INTO state (id, data, checksum, updated_at) VALUES (1, ?, ?, ?)",
            (json_data, checksum, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        return True

    @retry(max_attempts=3, delay=0.5, backoff=2.0, exceptions=(sqlite3.OperationalError,))
    async def load_state(self, key: str) -> Optional[Dict]:
        conn = sqlite3.connect(self.path)
        cursor = conn.cursor()
        cursor.execute("SELECT data, checksum FROM state WHERE id = 1")
        row = cursor.fetchone()
        conn.close()
        if row:
            data, checksum = row
            if hashlib.sha256(data.encode()).hexdigest() == checksum:
                return json.loads(data)
            else:
                self.logger.warning("Checksum no coincide, estado corrupto")
        return None

    @retry(max_attempts=3, delay=0.5, backoff=2.0, exceptions=(sqlite3.OperationalError,))
    async def save_position(self, position: Dict) -> bool:
        conn = sqlite3.connect(self.path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO positions (id, data) VALUES (?, ?)",
            (position.get('id'), json.dumps(position))
        )
        conn.commit()
        conn.close()
        return True

    @retry(max_attempts=3, delay=0.5, backoff=2.0, exceptions=(sqlite3.OperationalError,))
    async def delete_position(self, pos_id: str) -> bool:
        conn = sqlite3.connect(self.path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM positions WHERE id = ?", (pos_id,))
        conn.commit()
        conn.close()
        return True
