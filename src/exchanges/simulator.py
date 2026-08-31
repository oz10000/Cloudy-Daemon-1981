# src/exchanges/simulator.py
"""
Simulator Exchange — Simulador de exchange para pruebas y desarrollo
"""

import asyncio
import random
import time
import uuid
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta

from .base import (
    ExchangeAdapter, ExchangeHealth, ExchangeCapabilities,
    OrderSide, OrderType, OrderStatus
)
from src.utils.logger import get_logger


class SimulatorExchange(ExchangeAdapter):
    """
    Simulador de exchange con lógica realista de mercado.
    """

    def __init__(self, config: Dict):
        self.config = config
        self.logger = get_logger()  # <--- Import correcto

        # Balance inicial
        self.balance = {
            'USDT': config.get('initial_balance', 10000.0),
            'BTC': 0.0,
            'ETH': 0.0
        }

        # Posiciones
        self.positions: List[Dict] = []
        self.orders: List[Dict] = []
        self.order_counter = 0

        # Simulación de mercado
        self.symbols: Dict[str, float] = {
            'BTCUSDT': config.get('initial_btc_price', 60000.0),
            'ETHUSDT': config.get('initial_eth_price', 3000.0)
        }
        self.volatility = config.get('volatility', 0.0005)
        self.latency_ms = config.get('latency_ms', 10)
        self._running = True

        # Historial de precios
        self.price_history: Dict[str, List[float]] = {}

        # CORRECCIÓN: usar un solo argumento en logger.info
        self.logger.info(f"SIMULATOR — Simulador iniciado con balance: {self.balance['USDT']} USDT")

    async def _simulate_latency(self):
        await asyncio.sleep(self.latency_ms / 1000)

    async def _update_prices(self):
        """Actualiza los precios simulados."""
        for symbol in self.symbols:
            change = random.uniform(-self.volatility, self.volatility)
            self.symbols[symbol] *= (1 + change)
            self.symbols[symbol] = max(self.symbols[symbol], 100.0)

            if symbol not in self.price_history:
                self.price_history[symbol] = []
            self.price_history[symbol].append(self.symbols[symbol])
            if len(self.price_history[symbol]) > 1000:
                self.price_history[symbol].pop(0)

    async def get_price(self, symbol: str) -> float:
        await self._simulate_latency()
        await self._update_prices()
        return self.symbols.get(symbol, 0)

    async def get_balance(self, asset: Optional[str] = None) -> Dict[str, float]:
        await self._simulate_latency()
        if asset:
            return {asset: self.balance.get(asset, 0)}
        return self.balance.copy()

    async def get_positions(self) -> List[Dict]:
        await self._simulate_latency()
        for pos in self.positions:
            if pos.get('state') == 'OPEN':
                price = self.symbols.get(pos['symbol'], 0)
                pos['mark_price'] = price
                if pos['direction'] == 'LONG':
                    pos['unrealized_pnl'] = (price - pos['entry_price']) * pos['amount']
                else:
                    pos['unrealized_pnl'] = (pos['entry_price'] - price) * pos['amount']
        return self.positions

    async def create_order(self, symbol: str, side: OrderSide, order_type: OrderType,
                           amount: float, price: Optional[float] = None,
                           stop_price: Optional[float] = None) -> Dict:
        await self._simulate_latency()
        await self._update_prices()

        self.order_counter += 1
        entry_price = self.symbols.get(symbol, 0)
        slippage = random.uniform(-0.001, 0.001)
        execution_price = entry_price * (1 + slippage)

        order_id = f"sim_{self.order_counter}_{uuid.uuid4().hex[:8]}"

        required = amount * execution_price
        if side == OrderSide.BUY:
            if self.balance.get('USDT', 0) < required:
                self.logger.warning(f"SIMULATOR — Balance insuficiente para comprar {amount} {symbol}")
                return {
                    'orderId': order_id,
                    'status': 'REJECTED',
                    'reason': 'insufficient_balance'
                }
        else:
            pos = next((p for p in self.positions if p['symbol'] == symbol and p['state'] == 'OPEN'), None)
            if not pos or pos['amount'] < amount:
                self.logger.warning(f"SIMULATOR — Posición insuficiente para vender {amount} {symbol}")
                return {
                    'orderId': order_id,
                    'status': 'REJECTED',
                    'reason': 'insufficient_position'
                }

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
                self.balance[symbol.replace('USDT', '')] = self.balance.get(symbol.replace('USDT', ''), 0) + amount
            else:
                self.balance['USDT'] += amount * execution_price
                self.balance[symbol.replace('USDT', '')] = self.balance.get(symbol.replace('USDT', ''), 0) - amount

            self.positions.append({
                'id': order_id,
                'symbol': symbol,
                'direction': 'LONG' if side == OrderSide.BUY else 'SHORT',
                'amount': amount,
                'entry_price': execution_price,
                'mark_price': execution_price,
                'unrealized_pnl': 0,
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

    async def set_stop_loss(self, symbol: str, side: OrderSide, amount: float,
                            stop_price: float) -> Dict:
        await self._simulate_latency()
        order_id = f"sl_{uuid.uuid4().hex[:8]}"
        self.orders.append({
            'orderId': order_id,
            'symbol': symbol,
            'type': 'STOP_LOSS',
            'stop_price': stop_price,
            'status': 'PENDING'
        })
        return {'status': 'ok', 'orderId': order_id, 'stop_price': stop_price}

    async def set_take_profit(self, symbol: str, side: OrderSide, amount: float,
                              price: float) -> Dict:
        await self._simulate_latency()
        order_id = f"tp_{uuid.uuid4().hex[:8]}"
        self.orders.append({
            'orderId': order_id,
            'symbol': symbol,
            'type': 'TAKE_PROFIT',
            'price': price,
            'status': 'PENDING'
        })
        return {'status': 'ok', 'orderId': order_id, 'price': price}

    async def set_trailing_stop(self, symbol: str, side: OrderSide, amount: float,
                                activation: float, distance: float) -> Dict:
        await self._simulate_latency()
        order_id = f"ts_{uuid.uuid4().hex[:8]}"
        self.orders.append({
            'orderId': order_id,
            'symbol': symbol,
            'type': 'TRAILING_STOP',
            'activation': activation,
            'distance': distance,
            'status': 'PENDING'
        })
        return {'status': 'ok', 'orderId': order_id, 'activation': activation, 'distance': distance}

    async def reconcile(self) -> Dict[str, Any]:
        await self._simulate_latency()
        return {
            'positions': await self.get_positions(),
            'balance': self.balance.copy(),
            'orders': self.orders,
            'timestamp': datetime.now().isoformat()
        }

    async def health_check(self) -> ExchangeHealth:
        await self._simulate_latency()
        await self._update_prices()
        return ExchangeHealth(
            latency_ms=self.latency_ms,
            error_rate=0.0,
            is_connected=True,
            last_success=datetime.now().isoformat(),
            score=100.0
        )

    def get_capabilities(self) -> ExchangeCapabilities:
        return ExchangeCapabilities(
            supports_market_orders=True,
            supports_limit_orders=True,
            supports_stop_orders=True,
            supports_take_profit=True,
            supports_trailing_stop=True,
            supports_websocket=False,
            rate_limit_per_minute=99999
        )

    async def close(self):
        self._running = False
        self.logger.info("SIMULATOR — Simulador cerrado")
