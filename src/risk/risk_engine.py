"""Gestión de riesgo y dimensionamiento de posiciones."""
from typing import Dict, Any
from src.utils.logger import get_logger

logger = get_logger("risk_engine")

class RiskEngine:
    def __init__(self,
                 max_risk_per_trade: float = 0.02,
                 max_position_size: float = 1000.0,
                 default_leverage: int = 1):
        """
        Inicializa el motor de riesgo.
        
        :param max_risk_per_trade: Riesgo máximo por operación (fracción del capital).
        :param max_position_size: Tamaño máximo de posición en USDT.
        :param default_leverage: Apalancamiento por defecto.
        """
        self.max_risk_per_trade = max_risk_per_trade
        self.max_position_size = max_position_size
        self.default_leverage = default_leverage
        self.logger = logger

    async def calculate_size(self, symbol: str, confidence: float, leverage: int = None) -> float:
        """
        Calcula el tamaño de la posición basado en riesgo y confianza.
        
        :param symbol: Símbolo (no usado en este cálculo básico).
        :param confidence: Confianza de la señal (0-1).
        :param leverage: Apalancamiento (si no se proporciona, usa el default).
        :return: Tamaño de la posición.
        """
        leverage = leverage or self.default_leverage
        base = 100.0 * confidence * leverage
        size = min(base, self.max_position_size)
        self.logger.info(f"RISK — Tamaño calculado para {symbol}: {size} (confianza {confidence})")
        return size

    async def get_max_risk(self) -> float:
        """Retorna el riesgo máximo por operación."""
        return self.max_risk_per_trade

    async def get_max_position_size(self) -> float:
        """Retorna el tamaño máximo de posición."""
        return self.max_position_size

    async def get_default_leverage(self) -> int:
        """Retorna el apalancamiento por defecto."""
        return self.default_leverage
