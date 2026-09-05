"""
Simulator Exchange — Simulador de exchange para pruebas
"""
import asyncio
import random
import uuid
from typing import Optional, Dict, List, Any
from datetime import datetime

from .base import ExchangeAdapter, ExchangeHealth, ExchangeCapabilities, OrderSide, OrderType
from src.utils.logger import get_logger

class SimulatorExchange(ExchangeAdapter):
    def __init__(self, config: Dict):
        self.config = config
        self.logger = get_logger()
        self.balance = {'USDT': config.get('initial_balance', 10000.0)}
        self.positions = []
        self.orders = []
        self.order_counter = 0
        self.symbols = {'BTCUSDT': 62000.0, 'ETHUSDT': 3100.0, 'XRPUSDT': 1.46}
        self.volatility = config.get('volatility', 0.0005)
        self.latency_ms = config.get('latency_ms', 10)
        self._running = True

    # ─── Propiedades abstractas ──────────────────────────────────────────────
    @property
    def name(self) -> str:
        return "simulator"

    @property
    def version(self) -> str:
        return "1.0.0"

    # ─── Métodos abstractos ──────────────────────────────────────────────────
    async def health(self) -> Dict[str, Any]:
        """Retorna el estado de salud del simulador."""
        health = await self.health_check()
        return {
            "status": "ok" if health.is_connected else "error",
            "latency_ms": health.latency_ms,
            "is_connected": health.is_connected
        }

    async def start(self) -> bool:
        """Inicia el simulador (no hace nada, ya está listo)."""
        self._running = True
        return True

    async def stop(self) -> bool:
        """Detiene el simulador."""
        await self.close()
        return True

    async def test(self) -> Dict[str, Any]:
        """Prueba básica del simulador."""
        try:
            price = await self.get_price("BTCUSDT")
            return {"passed": True, "message": f"Test OK, price={price}"}
        except Exception as e:
            return {"passed": False, "message": str(e)}

    # ─── Métodos de ExchangeAdapter ──────────────────────────────────────────
    async def _simulate_latency(self):
        await asyncio.sleep(self.latency_ms / 1000)

    async def _update_prices(self):
        for symbol in self.symbols:
            change = random.uniform(-self.volatility, self.volatility)
            self.symbols[symbol] *= (1 + change)
            self.symbols[symbol] = max(self.symbols[symbol], 0.01)

    async def get_price(self, symbol: str) -> float:
        await self._simulate_latency()
        await self._update_prices()
        norm_symbol = symbol.replace('/', '')
        return self.symbols.get(norm_symbol, 0.0)

    async def get_balance(self, asset: Optional[str] = None) -> Dict[str, float]:
        await self._simulate_latency()
        if asset:
            return {asset: self.balance.get(asset, 0)}
        return self.balance.copy()

    async def get_positions(self) -> List[Dict]:
        await self._simulate_latency()
        return self.positions

    async def create_order(self, symbol: str, side: OrderSide, order_type: OrderType,
                           amount: float, price: Optional[float] = None,
                           stop_price: Optional[float] = None) -> Dict:
        await self._simulate_latency()
        await self._update_prices()

        norm_symbol = symbol.replace('/', '')
        entry_price = self.symbols.get(norm_symbol, 0.0)

        if entry_price <= 0:
            return {'status': 'REJECTED', 'reason': 'invalid_price'}

        slippage = random.uniform(-0.001, 0.001)
        execution_price = entry_price * (1 + slippage)

        order_id = f"sim_{self.order_counter}_{uuid.uuid4().hex[:8]}"
        self.order_counter += 1

        if side == OrderSide.BUY:
            required = amount * execution_price
            if self.balance.get('USDT', 0) < required:
                return {'status': 'REJECTED', 'reason': 'insufficient_balance'}

        order = {
            'orderId': order_id,
            'symbol': symbol,
            'side': side.value,
            'type': order_type.value,
            'amount': amount,
            'price': execution_price,
            'status': 'FILLED',
            'filled': amount,
            'avgPrice': execution_price,
            'created_at': datetime.now().isoformat()
        }
        self.orders.append(order)

        if order_type == OrderType.MARKET:
            if side == OrderSide.BUY:
                self.balance['USDT'] -= amount * execution_price
            else:
                self.balance['USDT'] += amount * execution_price

            self.positions.append({
                'id': order_id,
                'symbol': symbol,
                'direction': 'LONG' if side == OrderSide.BUY else 'SHORT',
                'amount': amount,
                'entry_price': execution_price,
                'mark_price': execution_price,
                'state': 'OPEN',
                'created_at': datetime.now().isoformat()
            })

        return order

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        await self._simulate_latency()
        for order in self.orders:
            if order['orderId'] == order_id:
                order['status'] = 'CANCELLED'
                return True
        return False

    async def set_stop_loss(self, symbol: str, side: OrderSide, amount: float, stop_price: float) -> Dict:
        await self._simulate_latency()
        return {'status': 'ok', 'stop_price': stop_price}

    async def set_take_profit(self, symbol: str, side: OrderSide, amount: float, price: float) -> Dict:
        await self._simulate_latency()
        return {'status': 'ok', 'price': price}

    async def set_trailing_stop(self, symbol: str, side: OrderSide, amount: float,
                                activation: float, distance: float) -> Dict:
        await self._simulate_latency()
        return {'status': 'ok', 'activation': activation, 'distance': distance}

    async def reconcile(self) -> Dict[str, Any]:
        await self._simulate_latency()
        return {'positions': self.positions, 'balance': self.balance, 'orders': self.orders}

    async def health_check(self) -> ExchangeHealth:
        await self._simulate_latency()
        return ExchangeHealth(10.0, 0.0, True, datetime.now().isoformat(), 100.0)

    def get_capabilities(self) -> ExchangeCapabilities:
        return ExchangeCapabilities(
            supports_market_orders=True,
            supports_limit_orders=True,
            supports_stop_orders=True,
            supports_take_profit=True,
            supports_trailing_stop=True,
            rate_limit_per_minute=99999
        )

    async def close(self):
        self._running = False
        self.logger.info("Simulador cerrado")
