"""
Bybit Adapter — Adaptador para Bybit API
"""

import asyncio
import hashlib
import hmac
import json
import time
from typing import Optional, Dict, List, Any
from datetime import datetime
import aiohttp

from .base import (
    ExchangeAdapter, ExchangeHealth, ExchangeCapabilities,
    OrderSide, OrderType, OrderStatus
)
from src.utils.logger import get_logger

class BybitAdapter(ExchangeAdapter):
    """
    Adaptador para Bybit API (V5).
    Documentación: https://bybit-exchange.github.io/docs/v5/intro
    """
    
    BASE_URL = "https://api.bybit.com"
    TESTNET_URL = "https://api-testnet.bybit.com"
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = get_logger()
        
        self.api_key = config.get('api_key', '')
        self.api_secret = config.get('api_secret', '')
        self.testnet = config.get('testnet', True)
        self.base_url = self.TESTNET_URL if self.testnet else self.BASE_URL
        
        self.session: Optional[aiohttp.ClientSession] = None
        self._recv_window = config.get('recv_window', 5000)
        
        self.logger.info("BYBIT", f"Inicializado en {'TESTNET' if self.testnet else 'MAINNET'}")

    async def _ensure_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
            self.logger.debug("BYBIT", "Sesión HTTP creada")

    def _generate_signature(self, params: Dict, timestamp: str) -> str:
        """Genera firma para Bybit."""
        query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
        signature_payload = f"{timestamp}{self.api_key}{self._recv_window}{query_string}"
        return hmac.new(
            self.api_secret.encode('utf-8'),
            signature_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    async def _request(self, method: str, endpoint: str,
                       params: Optional[Dict] = None,
                       signed: bool = False) -> Dict:
        await self._ensure_session()
        
        url = f"{self.base_url}{endpoint}"
        headers = {
            'Content-Type': 'application/json'
        }
        
        if signed and self.api_key:
            timestamp = str(int(time.time() * 1000))
            params = params or {}
            signature = self._generate_signature(params, timestamp)
            headers.update({
                'X-BAPI-API-KEY': self.api_key,
                'X-BAPI-TIMESTAMP': timestamp,
                'X-BAPI-SIGN': signature,
                'X-BAPI-RECV-WINDOW': str(self._recv_window)
            })
        
        try:
            async with self.session.request(method, url, params=params if method == 'GET' else None,
                                          json=params if method == 'POST' else None,
                                          headers=headers) as resp:
                data = await resp.json()
                if data.get('retCode') != 0:
                    self.logger.error("BYBIT", f"Error: {data.get('retMsg')}")
                    raise Exception(f"Bybit API error: {data.get('retMsg')}")
                return data.get('result', {})
        except aiohttp.ClientError as e:
            self.logger.error("BYBIT", f"Error de conexión: {e}")
            raise

    async def get_price(self, symbol: str) -> float:
        result = await self._request('GET', '/v5/market/tickers', {'symbol': symbol})
        if result and result.get('list'):
            return float(result['list'][0].get('lastPrice', 0))
        return 0

    async def get_balance(self, asset: Optional[str] = None) -> Dict[str, float]:
        result = await self._request('GET', '/v5/account/wallet-balance', 
                                   {'accountType': 'UNIFIED'}, signed=True)
        balances = {}
        if result and result.get('list'):
            for item in result['list']:
                for coin in item.get('coin', []):
                    balances[coin['coin']] = float(coin.get('walletBalance', 0))
        if asset:
            return {asset: balances.get(asset, 0)}
        return balances

    async def get_positions(self) -> List[Dict]:
        result = await self._request('GET', '/v5/position/list', {'category': 'linear'}, signed=True)
        positions = []
        if result and result.get('list'):
            for pos in result['list']:
                if float(pos.get('size', 0)) != 0:
                    positions.append({
                        'symbol': pos['symbol'],
                        'side': 'LONG' if float(pos.get('side', 0)) > 0 else 'SHORT',
                        'amount': abs(float(pos.get('size', 0))),
                        'entry_price': float(pos.get('avgPrice', 0)),
                        'mark_price': float(pos.get('markPrice', 0)),
                        'unrealized_pnl': float(pos.get('unrealisedPnl', 0)),
                        'leverage': int(pos.get('leverage', 1))
                    })
        return positions

    async def create_order(self, symbol: str, side: OrderSide, order_type: OrderType,
                           amount: float, price: Optional[float] = None,
                           stop_price: Optional[float] = None) -> Dict:
        params = {
            'category': 'linear',
            'symbol': symbol,
            'side': side.value.upper(),
            'orderType': order_type.value.upper(),
            'qty': str(amount),
            'timeInForce': 'GTC'
        }
        
        if order_type in [OrderType.LIMIT, OrderType.STOP]:
            if price is None:
                raise ValueError("Price required for LIMIT orders")
            params['price'] = str(price)
        
        if order_type in [OrderType.STOP, OrderType.STOP_MARKET]:
            if stop_price is None:
                raise ValueError("Stop price required for STOP orders")
            params['triggerPrice'] = str(stop_price)
        
        result = await self._request('POST', '/v5/order/create', params, signed=True)
        return {
            'orderId': result.get('orderId'),
            'symbol': result.get('symbol'),
            'side': result.get('side'),
            'type': result.get('orderType'),
            'amount': float(result.get('qty', 0)),
            'price': float(result.get('price', 0)),
            'status': result.get('orderStatus'),
            'filled': float(result.get('executedQty', 0)),
            'avgPrice': float(result.get('avgPrice', 0))
        }

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        params = {
            'category': 'linear',
            'symbol': symbol,
            'orderId': order_id
        }
        await self._request('POST', '/v5/order/cancel', params, signed=True)
        return True

    async def set_stop_loss(self, symbol: str, side: OrderSide, amount: float,
                            stop_price: float) -> Dict:
        return await self.create_order(
            symbol=symbol,
            side=OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY,
            order_type=OrderType.STOP_MARKET,
            amount=amount,
            stop_price=stop_price
        )

    async def set_take_profit(self, symbol: str, side: OrderSide, amount: float,
                              price: float) -> Dict:
        return await self.create_order(
            symbol=symbol,
            side=OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY,
            order_type=OrderType.TAKE_PROFIT,
            amount=amount,
            price=price
        )

    async def set_trailing_stop(self, symbol: str, side: OrderSide, amount: float,
                                activation: float, distance: float) -> Dict:
        params = {
            'category': 'linear',
            'symbol': symbol,
            'side': side.value.upper(),
            'orderType': 'TRAILING_STOP',
            'qty': str(amount),
            'triggerPrice': str(activation),
            'trailingDistance': str(distance)
        }
        return await self._request('POST', '/v5/order/create', params, signed=True)

    async def reconcile(self) -> Dict[str, Any]:
        positions = await self.get_positions()
        balance = await self.get_balance()
        return {
            'positions': positions,
            'balance': balance,
            'timestamp': datetime.now().isoformat()
        }

    async def health_check(self) -> ExchangeHealth:
        try:
            start = time.perf_counter()
            await self.get_price('BTCUSDT')
            latency_ms = (time.perf_counter() - start) * 1000
            return ExchangeHealth(
                latency_ms=latency_ms,
                error_rate=0.0,
                is_connected=True,
                last_success=datetime.now().isoformat(),
                score=100.0
            )
        except Exception as e:
            self.logger.error("BYBIT", f"Health check falló: {e}")
            return ExchangeHealth(0, 1.0, False, "", 0)

    def get_capabilities(self) -> ExchangeCapabilities:
        return ExchangeCapabilities(
            supports_market_orders=True,
            supports_limit_orders=True,
            supports_stop_orders=True,
            supports_take_profit=True,
            supports_trailing_stop=True,
            supports_websocket=True,
            rate_limit_per_minute=600
        )

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
