# src/exchanges/base.py
from abc import ABC, abstractmethod
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from enum import Enum

class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"

class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_MARKET = "stop_market"
    TAKE_PROFIT = "take_profit"
    TAKE_PROFIT_MARKET = "take_profit_market"
    TRAILING_STOP = "trailing_stop"

class OrderStatus(Enum):
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"

@dataclass
class ExchangeHealth:
    latency_ms: float = 0.0
    error_rate: float = 0.0
    is_connected: bool = False
    last_success: str = ""
    score: float = 100.0

@dataclass
class ExchangeCapabilities:
    supports_market_orders: bool = True
    supports_limit_orders: bool = True
    supports_stop_orders: bool = True
    supports_take_profit: bool = True
    supports_trailing_stop: bool = False
    supports_websocket: bool = False
    rate_limit_per_minute: int = 1200

class ExchangeAdapter(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        pass

    @abstractmethod
    async def get_price(self, symbol: str) -> float:
        pass

    @abstractmethod
    async def get_balance(self, asset: Optional[str] = None) -> Dict[str, float]:
        pass

    @abstractmethod
    async def get_positions(self) -> List[Dict]:
        pass

    @abstractmethod
    async def create_order(self, symbol: str, side: OrderSide, order_type: OrderType,
                           amount: float, price: Optional[float] = None,
                           stop_price: Optional[float] = None) -> Dict:
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        pass

    @abstractmethod
    async def set_stop_loss(self, symbol: str, side: OrderSide, amount: float,
                            stop_price: float) -> Dict:
        pass

    @abstractmethod
    async def set_take_profit(self, symbol: str, side: OrderSide, amount: float,
                              price: float) -> Dict:
        pass

    @abstractmethod
    async def set_trailing_stop(self, symbol: str, side: OrderSide, amount: float,
                                activation: float, distance: float) -> Dict:
        pass

    @abstractmethod
    async def reconcile(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def health_check(self) -> ExchangeHealth:
        pass

    @abstractmethod
    def get_capabilities(self) -> ExchangeCapabilities:
        pass

    @abstractmethod
    async def close(self):
        pass

class ExchangeFactory:
    @staticmethod
    def create(name: str, config: Dict) -> ExchangeAdapter:
        if name == 'binance':
            from .binance_futures import BinanceFuturesAdapter
            return BinanceFuturesAdapter(config)
        elif name == 'bybit':
            from .bybit import BybitAdapter
            return BybitAdapter(config)
        elif name == 'okx':
            from .okx import OKXAdapter
            return OKXAdapter(config)
        elif name == 'simulator':
            from .simulator import SimulatorExchange
            return SimulatorExchange(config)
        else:
            raise ValueError(f"Exchange no soportado: {name}")
