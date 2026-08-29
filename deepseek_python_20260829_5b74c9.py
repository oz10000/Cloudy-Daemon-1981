"""
OKX Adapter — Adaptador para OKX API
"""

import asyncio
import base64
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

class OKXAdapter(ExchangeAdapter):
    """
    Adaptador para OKX API (V5).
    Documentación: https://www.okx.com/docs-v5/en/
    """
    
    BASE_URL = "https://www.okx.com"
    TESTNET_URL = "https://www.okx.com"  # OKX no tiene testnet separado, usa simulador
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = get_logger()
        
        self.api_key = config.get('api_key', '')
        self.api_secret = config.get('api_secret', '')
        self.passphrase = config.get('passphrase', '')
        self.testnet = config.get('testnet', True)
        self.base_url = self.TESTNET_URL if self.testnet else self.BASE_URL
        
        self.session: Optional[aiohttp.ClientSession] = None
        
        self.logger.info("OKX", f"Inicializado en {'TESTNET' if self.testnet else 'MAINNET'}")

    async def _ensure_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
            self.logger.debug("OKX", "Sesión HTTP creada")

    def _generate_signature(self, timestamp: str, method: str, request_path: str,
                            body: str = '') -> str:
        """Genera firma para OKX."""
        message = timestamp + method.upper() + request_path + body
        mac = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        )
        return base64.b64encode(mac.digest()).decode('utf-8')

    async def _request(self, method: str, endpoint: str,
                       params: Optional[Dict] = None,
                       signed: bool = False) -> Dict:
        await self._ensure_session()
        
        url = f"{self.base_url}{endpoint}"
        headers = {
            'Content-Type': 'application/json'
        }
        
        if signed and self.api_key:
            timestamp = str(int(time.time()))
            body = json.dumps(params) if params else ''
            signature = self._generate_signature(timestamp, method, endpoint, body)
            headers.update({
                'OK-ACCESS-KEY': self.api_key,
                'OK-ACCESS-SIGN': signature,
                'OK-ACCESS-TIMESTAMP': timestamp,
                'OK-ACCESS-PASSPHRASE': self.passphrase
            })
        
        try:
            async with self.session.request(
                method, url, 
                params=params if method == 'GET' else None,
                json=params if method == 'POST' else None,
                headers=headers
            ) as resp:
                data = await resp.json()
                if data.get('code') != '0':
                    self.logger.error("OKX", f"Error: {data.get('msg')}")
                    raise Exception(f"OKX API error: {data.get('msg')}")
                return data.get('data', [{}])[0] if data.get('data') else {}
        except aiohttp.ClientError as e:
            self.logger.error("OKX", f"Error de conexión: {e}")
            raise

    async def get_price(self, symbol: str) -> float:
        result = await self._request('GET', '/api/v5/market/ticker', {'instId': symbol})
        if result:
            return float(result.get('last', 0))
        return 0

    async def get_balance(self, asset: Optional[str] = None) -> Dict[str, float]:
        result = await self._request('GET', '/api/v5/account/balance', signed=True)
        balances = {}
        if result and result.get('details'):
            for item in result['details']:
                balances[item['ccy']] = float(item.get('availBal', 0))
        if asset:
            return {asset: balances.get(asset, 0)}
        return balances

    async def get_positions(self) -> List[Dict]:
        result = await self._request('GET', '/api/v5/account/positions', signed=True)
        positions = []
        if result and isinstance(result, list):
            for pos in result:
                if float(pos.get('pos', 0)) != 0:
                    positions.append({
                        'symbol': pos['instId'],
                        'side': 'LONG' if float(pos.get('pos', 0)) > 0 else 'SHORT',
                        'amount': abs(float(pos.get('pos', 0))),
                        'entry_price': float(pos.get('avgPx', 0)),
                        'mark_price': float(pos.get('markPx', 0)),
                        'unrealized_pnl': float(pos.get('upl', 0)),
                        'leverage': int(pos.get('lever', 1))
                    })
        return positions

    async def create_order(self, symbol: str, side: OrderSide, order_type: OrderType,
                           amount: float, price: Optional[float] = None,
                           stop_price: Optional[float] = None) -> Dict:
        params = {
            'instId': symbol,
            'tdMode': 'isolated',
            'side': side.value.upper(),
            'ordType': order_type.value.upper(),
            'sz': str(amount)
        }
        
        if order_type in [OrderType.LIMIT, OrderType.STOP]:
            if price is None:
                raise ValueError("Price required for LIMIT orders")
            params['px'] = str(price)
        
        if order_type in [OrderType.STOP, OrderType.STOP_MARKET]:
            if stop_price is None:
                raise ValueError("Stop price required for STOP orders")
            params['triggerPx'] = str(stop_price)
        
        result = await self._request('POST', '/api/v5/trade/order', params, signed=True)
        return {
            'orderId': result.get('ordId'),
            'symbol': result.get('instId'),
            'side': result.get('side'),
            'type': result.get('ordType'),
            'amount': float(result.get('sz', 0)),
            'price': float(result.get('px', 0)),
            'status': result.get('state'),
            'filled': float(result.get('fillSz', 0)),
            'avgPrice': float(result.get('avgPx', 0))
        }

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        params = {
            'instId': symbol,
            'ordId': order_id
        }
        await self._request('POST', '/api/v5/trade/cancel-order', params, signed=True)
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
            'instId': symbol,
            'tdMode': 'isolated',
            'side': side.value.upper(),
            'ordType': 'TRIGGER',
            'sz': str(amount),
            'triggerPx': str(activation),
            'slTriggerPx': str(distance),
            'triggerPxType': 'last'
        }
        return await self._request('POST', '/api/v5/trade/order-algo', params, signed=True)

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
            await self.get_price('BTC-USDT')
            latency_ms = (time.perf_counter() - start) * 1000
            return ExchangeHealth(latency_ms, 0.0, True, datetime.now().isoformat(), 100.0)
        except Exception as e:
            self.logger.error("OKX", f"Health check falló: {e}")
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