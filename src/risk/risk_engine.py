"""
Risk Engine — Validación de riesgo (posición única, límites)
"""
from typing import Dict, Any
from src.utils.logger import get_logger

class RiskEngine:
    def __init__(self, config: Dict, position_manager):
        self.config = config
        self.position_manager = position_manager
        self.logger = get_logger()
        self.max_positions = config.get('max_positions', 1)
        self.risk_per_trade = config.get('risk_per_trade', 0.02)

    def can_open_position(self, signal: Dict) -> bool:
        open_positions = self.position_manager.get_open()
        if len(open_positions) >= self.max_positions:
            self.logger.warning(f"Límite de posiciones alcanzado ({self.max_positions})")
            return False
        return True

    def calculate_size(self, capital: float, entry: float, stop_loss: float) -> float:
        if stop_loss <= 0 or entry <= 0:
            return 0.0
        risk_amount = capital * self.risk_per_trade
        risk_per_unit = abs(entry - stop_loss) / entry
        if risk_per_unit <= 0:
            return 0.0
        size = risk_amount / (risk_per_unit * entry)
        return round(size, 3)
