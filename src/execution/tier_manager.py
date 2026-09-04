"""
Tier Manager — Gestión dinámica de tiers permitidos (S/A/B)
"""
import os
import yaml
from typing import List, Set, Dict
from datetime import datetime
from src.utils.logger import get_logger

class TierManager:
    DEFAULT_TIERS = ['S-TIER', 'A-TIER']

    def __init__(self, config_path: str = './config/tiers.yaml'):
        self.config_path = config_path
        self.logger = get_logger()
        self._allowed_tiers: Set[str] = set(self.DEFAULT_TIERS)
        self._load()

    def _load(self):
        if not os.path.exists(self.config_path):
            self.logger.warning(f"Config de tiers no encontrada en {self.config_path}, usando defaults")
            return
        try:
            with open(self.config_path, 'r') as f:
                data = yaml.safe_load(f) or {}
                tiers = data.get('signals', {}).get('allowed_tiers', [])
                if tiers:
                    self._allowed_tiers = set(tiers)
                    # CORREGIDO: f-string
                    self.logger.info(f"Tiers cargados: {self._allowed_tiers}")
        except Exception as e:
            self.logger.error(f"Error cargando tiers: {e}")

    def save(self):
        data = {
            'signals': {
                'allowed_tiers': list(self._allowed_tiers),
                'updated_at': datetime.now().isoformat()
            }
        }
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False)
        self.logger.info(f"Tiers guardados: {self._allowed_tiers}")

    def get_allowed_tiers(self) -> List[str]:
        return list(self._allowed_tiers)

    def set_allowed_tiers(self, tiers: List[str]):
        self._allowed_tiers = set(tiers)
        self.save()

    def is_tier_allowed(self, tier: str) -> bool:
        return tier in self._allowed_tiers

    def filter_signals(self, signals: List[Dict]) -> List[Dict]:
        if not signals:
            return []
        filtered = [s for s in signals if self.is_tier_allowed(s.get('level', ''))]
        self.logger.info(f"Señales después de filtro de tiers: {len(filtered)} de {len(signals)}")
        return filtered
