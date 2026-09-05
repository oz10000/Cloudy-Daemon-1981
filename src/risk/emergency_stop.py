"""Parada de emergencia para cancelar todas las órdenes y posiciones."""
from src.utils.logger import get_logger
from src.exchanges.base import ExchangeAdapter

logger = get_logger("emergency_stop")

class EmergencyStop:
    def __init__(self, exchange: ExchangeAdapter):
        """
        Inicializa la parada de emergencia con el adaptador de exchange.
        
        :param exchange: Adaptador del exchange para cancelar órdenes.
        """
        self.exchange = exchange
        self._activated = False
        self.logger = logger

    async def activate(self) -> bool:
        """Activa la parada de emergencia: cancela todas las órdenes."""
        self.logger.warning("EMERGENCY — ACTIVANDO PARADA DE EMERGENCIA")
        try:
            # Intentar cancelar todas las órdenes abiertas
            result = await self.exchange.cancel_all_orders()
            if result:
                self._activated = True
                self.logger.info("EMERGENCY — Parada de emergencia completada")
                return True
            else:
                self.logger.error("EMERGENCY — Falló la cancelación de órdenes")
                return False
        except Exception as e:
            self.logger.error(f"EMERGENCY — Error: {e}")
            return False

    def reset(self) -> None:
        """Resetea el estado de emergencia."""
        self._activated = False
        self.logger.info("EMERGENCY — Reset")

    def is_active(self) -> bool:
        """Retorna si la parada de emergencia está activa."""
        return self._activated
