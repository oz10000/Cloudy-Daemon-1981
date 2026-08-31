"""
Risk Engine — Gestión de riesgo real
"""

from typing import Dict, Any
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

    def can_open_position(self, signal: Dict, position_manager=None) -> bool:
        """Verifica si se puede abrir una nueva posición según las reglas de riesgo."""
        # 1. Verificar número de posiciones abiertas
        if position_manager:
            open_positions = position_manager.get_open()
            if len(open_positions) >= self.max_positions:
                self.logger.warning("RISK", f"Máximo de posiciones alcanzado: {self.max_positions}")
                return False

            # 2. Verificar exposición total
            total_exposure = sum(p.amount * p.mark_price for p in open_positions)
            balance = 10000  # En producción se obtiene del exchange
            exposure_pct = total_exposure / balance if balance > 0 else 0
            if exposure_pct > self.max_exposure:
                self.logger.warning("RISK", f"Exposición excedida: {exposure_pct:.2%} > {self.max_exposure:.2%}")
                return False

        # 3. Verificar drawdown (simplificado, se puede ampliar)
        current_drawdown = 0.0  # Se obtendría de métricas históricas
        if current_drawdown > self.max_drawdown:
            self.logger.warning("RISK", f"Drawdown excedido: {current_drawdown:.2%} > {self.max_drawdown:.2%}")
            return False

        # 4. Verificar pérdida diaria
        if abs(self.daily_pnl) > self.max_daily_loss * 10000:
            self.logger.warning("RISK", f"Pérdida diaria excedida: {self.daily_pnl:.2f}")
            return False

        # 5. Verificar calidad de la señal (score mínimo)
        score = signal.get('score', 0)
        if score < 0.3:
            self.logger.warning("RISK", f"Score bajo: {score:.2f}")
            return False

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
