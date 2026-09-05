"""Gestión de órdenes (creación, seguimiento, cancelación)."""
from typing import Dict, Any, Optional, List
from src.utils.logger import get_logger
from src.exchanges.base import ExchangeAdapter

logger = get_logger("order_manager")

class Order:
    def __init__(self, data: Dict):
        self.id = data.get('id')
        self.symbol = data.get('symbol')
        self.side = data.get('side')
        self.size = data.get('size')
        self.price = data.get('price')
        self.status = data.get('status', 'new')
        self.extra = data

class OrderManager:
    def __init__(self, exchange: ExchangeAdapter):
        """Inicializa el gestor de órdenes con el adaptador de exchange."""
        self.exchange = exchange
        self._orders: Dict[str, Order] = {}

    async def create_order(self, symbol: str, side: str, size: float,
                           order_type: str = 'MARKET', price: float = None,
                           leverage: int = 1, stop_loss: float = None,
                           take_profit: float = None) -> Optional[Dict]:
        """Crea una orden en el exchange."""
        logger.info(f"ORDER — Creando orden {symbol} {side} {size}@{price or 'market'}")
        try:
            # Llamar al exchange usando sus propios tipos
            result = await self.exchange.create_order(
                symbol, side, order_type, size, price, stop_loss
            )
            if result and result.get('orderId'):
                order = Order(result)
                self._orders[order.id] = order
                logger.info(f"ORDER — Orden creada: {order.id}")
                return result
            else:
                logger.error(f"ORDER — Falló creación de orden para {symbol}")
                return None
        except Exception as e:
            logger.error(f"ORDER — Error: {e}")
            return None

    async def cancel_order(self, order_id: str) -> bool:
        """Cancela una orden."""
        logger.info(f"ORDER — Cancelando orden {order_id}")
        try:
            result = await self.exchange.cancel_order(order_id)
            if result:
                self._orders.pop(order_id, None)
                logger.info(f"ORDER — Orden {order_id} cancelada")
                return True
            return False
        except Exception as e:
            logger.error(f"ORDER — Error cancelando orden: {e}")
            return False

    def get_order(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)
