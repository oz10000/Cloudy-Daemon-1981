"""
Binance Futures Adapter — Adaptador para Binance Futures API
"""

import asyncio
import hashlib
import hmac
import json
import time
from typing import Optional, Dict, List, Any
from datetime import datetime
import aiohttp
import base64

from .base import (
    ExchangeAdapter, ExchangeHealth, ExchangeCapabilities,
    OrderSide, OrderType, OrderStatus
)
from src.utils.logger import get_logger

class BinanceFuturesAdapter(ExchangeAdapter):
    """
    Adaptador para Binance USD-M Futures API.
    Documentación: https://binance-docs.github.io/apidocs/futures/en/
    """
    
    BASE_URL = "https://fapi.binance.com"
    TESTNET_URL = "https://testnet.binancefuture.com"
    WS_URL = "wss://fstream.binance.com/ws"
    WS_TESTNET_URL = "wss://stream.binancefuture.com/ws"
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = get_logger()
        
        # Configuración
        self.api_key = config.get('api_key', '')
        self.api_secret = config.get('api_secret', '')
        self.testnet = config.get('testnet', True)
        self.base_url = self.TESTNET_URL if self.testnet else self.BASE_URL
        self.ws_url = self.WS_TESTNET_URL if self.testnet else self.WS_URL
        
        self.session: Optional[aiohttp.ClientSession] = None
        self._recv_window = config.get('recv_window', 5000)
        self._rate_limit_remaining = 1200
        self._rate_limit_reset = time.time() + 60
        
        self.logger.info("BINANCE", f"Inicializado en {'TESTNET' if self.testnet else 'MAINNET'}")

    async def _ensure_session(self):
        """Asegura que la sesión HTTP está creada."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
            self.logger.debug("BINANCE", "Sesión HTTP creada")

    def _generate_signature(self, params: Dict) -> str:
        """Genera firma HMAC SHA256 para autenticación."""
        query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    async def _request(self, method: str, endpoint: str, 
                       params: Optional[Dict] = None, 
                       signed: bool = False) -> Dict:
        """Realiza una solicitud HTTP a la API de Binance."""
        await self._ensure_session()
        
        url = f"{self.base_url}{endpoint}"
        headers = {}
        
        if signed and self.api_key:
            timestamp = int(time.time() * 1000)
            params = params or {}
            params['timestamp'] = timestamp
            params['recvWindow'] = self._recv_window
            params['signature'] = self._generate_signature(params)
            headers['X-MBX-APIKEY'] = self.api_key
        
        try:
            async with self.session.request(method, url, params=params, headers=headers) as resp:
                # Rate limiting
                self._rate_limit_remaining = int(resp.headers.get('X-MBX-USED-WEIGHT-1M', 1200))
                self._rate_limit_reset = time.time() + 60
                
                if resp.status == 200:
                    return await resp.json()
                else:
                    error = await resp.text()
                    self.logger.error("BINANCE", f"Error {resp.status}: {error}")
                    raise Exception(f"Binance API error: {resp.status} - {error}")
        except aiohttp.ClientError as e:
            self.logger.error("BINANCE", f"Error de conexión: {e}")
            raise

    async def get_price(self, symbol: str) -> float:
        """Obtiene el precio actual de un símbolo."""
        result = await self._request('GET', '/fapi/v1/ticker/price', {'symbol': symbol})
        return float(result.get('price', 0))

    async def get_balance(self, asset: Optional[str] = None) -> Dict[str, float]:
        """Obtiene el balance de la cuenta."""
        result = await self._request('GET', '/fapi/v2/account', signed=True)
        balances = {}
        for item in result.get('assets', []):
            asset_name = item['asset']
            free = float(item.get('availableBalance', 0))
            locked = float(item.get('initialMargin', 0))
            balances[asset_name] = free + locked
        
        if asset:
            return {asset: balances.get(asset, 0)}
        return balances

    async def get_positions(self) -> List[Dict]:
        """Obtiene las posiciones abiertas."""
        result = await self._request('GET', '/fapi/v2/account', signed=True)
        positions = []
        for pos in result.get('positions', []):
            if float(pos.get('positionAmt', 0)) != 0:
                positions.append({
                    'symbol': pos['symbol'],
                    'side': 'LONG' if float(pos.get('positionAmt', 0)) > 0 else 'SHORT',
                    'amount': abs(float(pos.get('positionAmt', 0))),
                    'entry_price': float(pos.get('entryPrice', 0)),
                    'mark_price': float(pos.get('markPrice', 0)),
                    'unrealized_pnl': float(pos.get('unRealizedProfit', 0)),
                    'leverage': int(pos.get('leverage', 1)),
                    'liquidation_price': float(pos.get('liquidationPrice', 0))
                })
        return positions

    async def create_order(self, symbol: str, side: OrderSide, order_type: OrderType,
                           amount: float, price: Optional[float] = None,
                           stop_price: Optional[float] = None) -> Dict:
        """Crea una orden en Binance Futures."""
        params = {
            'symbol': symbol,
            'side': side.value.upper(),
            'type': order_type.value.upper(),
            'quantity': amount,
            'newOrderRespType': 'FULL'
        }
        
        if order_type in [OrderType.LIMIT, OrderType.STOP]:
            if price is None:
                raise ValueError("Price required for LIMIT orders")
            params['price'] = price
            params['timeInForce'] = 'GTC'
        
        if order_type in [OrderType.STOP, OrderType.STOP_MARKET]:
            if stop_price is None:
                raise ValueError("Stop price required for STOP orders")
            params['stopPrice'] = stop_price
        
        if order_type == OrderType.TRAILING_STOP:
            if stop_price is None:
                raise ValueError("Stop price required for TRAILING_STOP")
            params['callbackRate'] = stop_price  # Binance usa callbackRate para trailing
        
        result = await self._request('POST', '/fapi/v1/order', params, signed=True)
        return {
            'orderId': result.get('orderId'),
            'symbol': result.get('symbol'),
            'side': result.get('side'),
            'type': result.get('type'),
            'amount': float(result.get('origQty', 0)),
            'price': float(result.get('price', 0)),
            'status': result.get('status'),
            'filled': float(result.get('executedQty', 0)),
            'avgPrice': float(result.get('avgPrice', 0))
        }

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancela una orden existente."""
        params = {
            'symbol': symbol,
            'orderId': order_id
        }
        result = await self._request('DELETE', '/fapi/v1/order', params, signed=True)
        return result.get('status') == 'CANCELED'

    async def set_stop_loss(self, symbol: str, side: OrderSide, amount: float,
                            stop_price: float) -> Dict:
        """Establece un Stop Loss."""
        # Binance usa STOP_MARKET para stop loss
        return await self.create_order(
            symbol=symbol,
            side=OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY,
            order_type=OrderType.STOP_MARKET,
            amount=amount,
            stop_price=stop_price
        )

    async def set_take_profit(self, symbol: str, side: OrderSide, amount: float,
                              price: float) -> Dict:
        """Establece un Take Profit."""
        # Binance usa TAKE_PROFIT para take profit
        return await self.create_order(
            symbol=symbol,
            side=OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY,
            order_type=OrderType.TAKE_PROFIT,
            amount=amount,
            price=price
        )

    async def set_trailing_stop(self, symbol: str, side: OrderSide, amount: float,
                                activation: float, distance: float) -> Dict:
        """Establece un Trailing Stop."""
        # Binance usa TRAILING_STOP_MARKET
        return await self.create_order(
            symbol=symbol,
            side=OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY,
            order_type=OrderType.TRAILING_STOP,
            amount=amount,
            stop_price=distance  # Binance usa callbackRate
        )

    async def reconcile(self) -> Dict[str, Any]:
        """Reconcilia el estado local con Binance."""
        positions = await self.get_positions()
        account = await self._request('GET', '/fapi/v2/account', signed=True)
        
        open_orders = await self._request('GET', '/fapi/v1/openOrders', signed=True)
        
        return {
            'positions': positions,
            'balance': await self.get_balance(),
            'open_orders': open_orders,
            'timestamp': datetime.now().isoformat(),
            'account_info': {
                'total_margin': float(account.get('totalInitialMargin', 0)),
                'total_pnl': float(account.get('totalUnrealizedProfit', 0)),
                'available_balance': float(account.get('availableBalance', 0))
            }
        }

    async def health_check(self) -> ExchangeHealth:
        """Verifica la salud del exchange."""
        try:
            start = time.perf_counter()
            await self.get_price('BTCUSDT')
            latency_ms = (time.perf_counter() - start) * 1000
            
            # Verificar rate limit
            error_rate = 0.0
            if self._rate_limit_remaining < 10:
                error_rate = 0.1
            
            return ExchangeHealth(
                latency_ms=latency_ms,
                error_rate=error_rate,
                is_connected=True,
                last_success=datetime.now().isoformat(),
                score=100.0 - (error_rate * 100)
            )
        except Exception as e:
            self.logger.error("BINANCE", f"Health check falló: {e}")
            return ExchangeHealth(
                latency_ms=0.0,
                error_rate=1.0,
                is_connected=False,
                last_success="",
                score=0.0
            )

    def get_capabilities(self) -> ExchangeCapabilities:
        """Retorna las capacidades del exchange."""
        return ExchangeCapabilities(
            supports_market_orders=True,
            supports_limit_orders=True,
            supports_stop_orders=True,
            supports_take_profit=True,
            supports_trailing_stop=True,
            supports_websocket=True,
            rate_limit_per_minute=1200
        )

    async def close(self):
        """Cierra la sesión HTTP."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.logger.debug("BINANCE", "Sesión HTTP cerrada")