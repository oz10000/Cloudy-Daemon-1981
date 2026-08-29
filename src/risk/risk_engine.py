# src/risk/risk_engine.py
"""Risk Engine — Gestión de riesgo real"""

from typing import Dict, Any, List
from datetime import datetime
from src.utils.logger import get_logger

class RiskEngine:
    def __init__(self, config: Dict):
        self.max_positions = config.get('max_positions', 3)
        self.risk_per_trade = config.get('risk_per_trade', 0.01)
        self.max_daily_loss = config.get('max_daily_loss', 0.05)
        self.max_drawdown = config.get('max_drawdown', 0.10)
        self.max_exposure = config.get('max_exposure', 0.20)
        self.daily_pnl = 0.0
        self.day_start = datetime.now().date()
        self.logger = get_logger()

    def can_open_position(self, signal: Dict) -> bool:
        """Verifica si se puede abrir una nueva posición según las reglas de riesgo."""
        # Aquí se implementaría la lógica real:
        # - Verificar número de posiciones abiertas
        # - Verificar exposición total
        # - Verificar drawdown y pérdida diaria
        # Por ahora devolvemos True, pero en producción debe ser riguroso.
        # NOTA: Se recomienda implementar completamente.
        return True

    def calculate_size(self, capital: float, entry: float, sl: float) -> float:
        """Calcula el tamaño de la posición basado en el riesgo por trade."""
        if sl >= entry:
            risk_per_unit = (sl - entry) / entry
        else:
            risk_per_unit = (entry - sl) / entry
        if risk_per_unit <= 0:
            return 0
        risk_amount = capital * self.risk_per_trade
        size = risk_amount / (risk_per_unit * entry)
        return round(size, 3)

    def record_pnl(self, pnl: float):
        """Registra el PnL para control de pérdida diaria."""
        today = datetime.now().date()
        if today != self.day_start:
            self.day_start = today
            self.daily_pnl = 0.0
        self.daily_pnl += pnl

    def is_exposure_allowed(self, current_exposure: float) -> bool:
        return current_exposure <= self.max_exposure

    def is_drawdown_allowed(self, current_drawdown: float) -> bool:
        return current_drawdown <= self.max_drawdown
