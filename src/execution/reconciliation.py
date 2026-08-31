# src/execution/reconciliation.py
from src.exchanges.base import ExchangeAdapter
from src.execution.position_manager import PositionManager
from src.execution.order_manager import OrderManager
from src.utils.logger import get_logger


class Reconciliation:
    def __init__(self, exchange: ExchangeAdapter, position_manager: PositionManager,
                 order_manager: OrderManager):
        self.exchange = exchange
        self.position_manager = position_manager
        self.order_manager = order_manager
        self.logger = get_logger()

    async def sync(self):
        try:
            exchange_positions = await self.exchange.get_positions()
            exchange_orders = await self.exchange.reconcile()
            self.logger.debug(f"RECONCILIATION — Sincronizado: {len(exchange_positions)} posiciones")
        except Exception as e:
            self.logger.error(f"RECONCILIATION — Error en sincronización: {e}")
