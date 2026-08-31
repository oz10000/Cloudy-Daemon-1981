# src/execution/order_manager.py
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from src.utils.logger import get_logger


class OrderStatus(Enum):
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class Order:
    id: str
    symbol: str
    side: str
    order_type: str
    amount: float
    price: float
    status: OrderStatus
    filled: float = 0.0
    avg_price: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    exchange_order_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class OrderManager:
    def __init__(self):
        self.orders: Dict[str, Order] = {}
        self.logger = get_logger()

    def create_order(self, symbol: str, side: str, order_type: str,
                     amount: float, price: float = 0.0,
                     metadata: Optional[Dict] = None) -> Order:
        order_id = f"ord_{uuid.uuid4().hex[:12]}"
        order = Order(
            id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            amount=amount,
            price=price,
            status=OrderStatus.PENDING,
            metadata=metadata or {}
        )
        self.orders[order_id] = order
        self.logger.debug(f"ORDER — Orden creada: {order_id} ({symbol} {side} {amount})")
        return order

    def update_order(self, order_id: str, **kwargs) -> Optional[Order]:
        order = self.orders.get(order_id)
        if not order:
            return None

        for key, value in kwargs.items():
            if hasattr(order, key):
                setattr(order, key, value)

        order.updated_at = datetime.now().isoformat()

        if 'status' in kwargs:
            self.logger.info(f"ORDER — Orden {order_id} -> {kwargs['status']}")

        return order

    def get_order(self, order_id: str) -> Optional[Order]:
        return self.orders.get(order_id)

    def get_all_orders(self) -> List[Order]:
        return list(self.orders.values())

    def get_orders_by_symbol(self, symbol: str) -> List[Order]:
        return [o for o in self.orders.values() if o.symbol == symbol]

    def get_open_orders(self) -> List[Order]:
        return [o for o in self.orders.values() if o.status in [OrderStatus.OPEN, OrderStatus.PENDING]]

    def get_orders_by_status(self, status: OrderStatus) -> List[Order]:
        return [o for o in self.orders.values() if o.status == status]

    async def restore(self, orders_data: List[Dict]) -> None:
        for data in orders_data:
            order = Order(
                id=data['id'],
                symbol=data['symbol'],
                side=data['side'],
                order_type=data['order_type'],
                amount=data['amount'],
                price=data['price'],
                status=OrderStatus(data['status']),
                filled=data.get('filled', 0.0),
                avg_price=data.get('avg_price', 0.0),
                created_at=data.get('created_at', datetime.now().isoformat()),
                updated_at=data.get('updated_at', datetime.now().isoformat()),
                exchange_order_id=data.get('exchange_order_id'),
                metadata=data.get('metadata', {})
            )
            self.orders[order.id] = order
        self.logger.info(f"ORDER — Restauradas {len(orders_data)} órdenes")

    def to_dict(self) -> List[Dict]:
        return [
            {
                'id': o.id,
                'symbol': o.symbol,
                'side': o.side,
                'order_type': o.order_type,
                'amount': o.amount,
                'price': o.price,
                'status': o.status.value,
                'filled': o.filled,
                'avg_price': o.avg_price,
                'created_at': o.created_at,
                'updated_at': o.updated_at,
                'exchange_order_id': o.exchange_order_id,
                'metadata': o.metadata
            }
            for o in self.orders.values()
        ]
