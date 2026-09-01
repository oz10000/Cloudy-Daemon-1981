"""
Signal Watcher — Vigila nuevas señales desde GitHub Artifact (hash-based)
"""
import os
import json
import hashlib
import yaml
from typing import List, Dict, Optional
from datetime import datetime
from src.utils.logger import get_logger
from src.execution.github_artifact_provider import GitHubArtifactProvider

class SignalWatcher:
    def __init__(self, repo: str, token: Optional[str] = None, state_file: str = "./data/state/last_signal.yaml"):
        self.provider = GitHubArtifactProvider(repo, token)
        self.state_file = state_file
        self.logger = get_logger()
        self._last_state = self._load_state()

    def _load_state(self) -> Dict:
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                self.logger.warning(f"Error cargando estado: {e}")
        return {}

    def _save_state(self, signals: List[Dict]):
        if not signals:
            return
        combined = json.dumps(signals, sort_keys=True).encode()
        hash_val = hashlib.sha256(combined).hexdigest()
        state = {
            'last_processed': {
                'timestamp': datetime.now().isoformat(),
                'hash': hash_val,
                'count': len(signals)
            }
        }
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        with open(self.state_file, 'w') as f:
            yaml.dump(state, f, default_flow_style=False)
        self._last_state = state

    def _has_changed(self, new_signals: List[Dict]) -> bool:
        if not new_signals:
            return False
        combined = json.dumps(new_signals, sort_keys=True).encode()
        new_hash = hashlib.sha256(combined).hexdigest()
        old_hash = self._last_state.get('last_processed', {}).get('hash')
        return new_hash != old_hash

    def _validate_signal(self, signal: Dict) -> bool:
        required = ['symbol', 'direction', 'level']
        return all(k in signal for k in required) and signal['direction'] in ['LONG', 'SHORT']

    async def check_and_fetch(self) -> List[Dict]:
        signals = await self.provider.fetch_latest()
        if not signals:
            return []
        valid = [s for s in signals if self._validate_signal(s)]
        if not valid:
            self.logger.warning("No hay señales válidas")
            return []
        if not self._has_changed(valid):
            self.logger.debug("No hay cambios en las señales (hash igual)")
            return []
        self._save_state(valid)
        self.logger.info(f"Nuevas señales detectadas: {len(valid)}")
        return valid
