# src/risk/leverage_manager.py
from typing import Dict
from src.utils.logger import get_logger

class LeverageManager:
    def __init__(self, config: Dict):
        self.base_leverage = config.get('base_leverage', 3)
        self.max_leverage = config.get('max_leverage', 5)
        self.min_leverage = config.get('min_leverage', 1)
        self.logger = get_logger()

    def get_optimal_leverage(self, signal: Dict) -> int:
        level = signal.get('level', 'B-TIER')
        regime = signal.get('regime', 'Chop')
        atr_pct = signal.get('atr_pct', 0.02)
        confidence = signal.get('confidence', 50)

        base = {
            'S-TIER': 4,
            'A-TIER': 3,
            'B-TIER': 2,
            'NO-TIER': 0
        }
        leverage = base.get(level, 1)

        if regime == 'Chop':
            leverage = min(leverage, 1)
        elif regime == 'Tendencia Débil':
            leverage = min(leverage, 2)
        elif regime == 'Tendencia Fuerte':
            leverage = min(leverage, 4)
        elif regime == 'Expansión':
            leverage = min(leverage, 5)

        if atr_pct > 0.03:  # Volatilidad alta
            leverage = max(1, leverage - 1)
        elif atr_pct < 0.01:  # Volatilidad baja
            leverage = min(self.max_leverage, leverage + 1)

        if confidence < 60:
            leverage = max(1, leverage - 1)
        elif confidence > 80:
            leverage = min(self.max_leverage, leverage + 1)

        final_leverage = max(self.min_leverage, min(self.max_leverage, leverage))
        self.logger.debug(f"LEVERAGE — Nivel: {level}, Régimen: {regime}, ATR: {atr_pct:.2%} → Leverage: {final_leverage}x")
        return final_leverage
