# src/exchanges/okx.py
"""
OKX Adapter — Adaptador para OKX API V5

Mejoras integradas desde Ku-Klux-Klan:
- Timeout de 60 segundos
- Reintentos con backoff exponencial (3 intentos)
- Sincronización horaria automática (_sync_time)
- Cache de instrumentos y apalancamiento
- Órdenes algorítmicas (TP/SL) con create_algo_order
- Cierre de posiciones por posId
- Obtención de velas OHLCV
- Manejo robusto de errores
"""

import asyncio
import base64
import hashlib
import hmac
import json
import time
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, timedelta
import aiohttp
from aiohttp import ClientTimeout, ClientResponseError

from .base import (
    ExchangeAdapter, ExchangeHealth, ExchangeCapabilities,
    OrderSide, OrderType, OrderStatus
)
from src.utils.logger import get_logger


class OKXAdapter(ExchangeAdapter):
    """
    Adaptador para OKX API V5.
    Documentación: https://www.okx.com/docs-v5/en/
    """

    BASE_URL = "https://www.okx.com"
    TESTNET_URL = "https://www.okx.com"  # OKX usa header 'x-simulated-trading: 1' para demo

    def __init__(self, config: Dict):
        self.config = config
        self.logger = get_logger()

        # Credenciales
        self.api_key = config.get('api_key', '')
        self.api_secret = config.get('api_secret', '')
        self.passphrase = config.get('passphrase', '')
        self.testnet = config.get('testnet', True)  # True = modo demo

        # URLs
        self.base_url = self.TESTNET_URL if self.testnet else self.BASE_URL

        # Timeout de 60 segundos (mejor que el predeterminado de aiohttp)
        self.timeout = ClientTimeout(total=60.0)

        # Sesión HTTP persistente
        self.session: Optional[aiohttp.ClientSession] = None

        # Cachés para reducir llamadas API
        self._instrument_cache: Dict[str, Dict] = {}
        self._leverage_cache: Dict[str, Dict] = {}
        self._last_time_sync: float = 0.0
        self._time_offset: int = 0  # Diferencia con el servidor OKX (ms)

        # Control de reintentos
        self.max_retries = config.get('max_retries', 3)
        self.retry_backoff = config.get('retry_backoff', 1.0)  # segundos base

        self.logger.info("OKX", f"Inicializado en {'DEMO' if self.testnet else 'MAINNET'}")

    # ──────────────────────────────────────────────────────────────
    #  Gestión de sesión y autenticación
    # ──────────────────────────────────────────────────────────────

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Asegura que la sesión HTTP está creada y activa."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=self.timeout)
            self.logger.debug("OKX", "Sesión HTTP creada (timeout=60s)")
        return self.session

    async def _sync_time(self) -> None:
        """
        Sincroniza el reloj local con el servidor OKX.
        La diferencia se usa en la firma para evitar errores de timestamp.
        """
        now = int(time.time() * 1000)
        try:
            session = await self._ensure_session()
            async with session.get(f"{self.base_url}/api/v5/public/time") as resp:
                data = await resp.json()
                if data.get('code') == '0':
                    server_time = int(data['data'][0]['ts'])
                    self._time_offset = server_time - now
                    self._last_time_sync = time.time()
                    self.logger.debug("OKX", f"Tiempo sincronizado: offset={self._time_offset}ms")
                else:
                    self.logger.warning("OKX", f"Falló sync de tiempo: {data.get('msg')}")
        except Exception as e:
            self.logger.warning("OKX", f"Error en sync de tiempo: {e}")

    async def _ensure_time_synced(self) -> None:
        """Verifica y sincroniza el tiempo si ha pasado más de 1 hora."""
        if time.time() - self._last_time_sync > 3600:
            await self._sync_time()

    def _generate_signature(self, timestamp: str, method: str, request_path: str,
                            body: str = '') -> str:
        """Genera firma HMAC-SHA256 para OKX."""
        message = timestamp + method.upper() + request_path + body
        mac = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        )
        return base64.b64encode(mac.digest()).decode('utf-8')

    # ──────────────────────────────────────────────────────────────
    #  Request con reintentos y backoff exponencial
    # ──────────────────────────────────────────────────────────────

    async def _request(self, method: str, endpoint: str,
                       params: Optional[Dict] = None,
                       signed: bool = False,
                       retry_count: int = 0) -> Dict:
        """
        Realiza una solicitud HTTP a la API de OKX con reintentos y backoff.
        """
        await self._ensure_time_synced()
        session = await self._ensure_session()

        url = f"{self.base_url}{endpoint}"
        headers = {'Content-Type': 'application/json'}

        # Modo demo (simulación)
        if self.testnet:
            headers['x-simulated-trading'] = '1'

        # Autenticación si es necesario
        if signed and self.api_key:
            timestamp = str(int(time.time() * 1000) + self._time_offset)
            body = json.dumps(params) if params else ''
            signature = self._generate_signature(timestamp, method, endpoint, body)
            headers.update({
                'OK-ACCESS-KEY': self.api_key,
                'OK-ACCESS-SIGN': signature,
                'OK-ACCESS-TIMESTAMP': timestamp,
                'OK-ACCESS-PASSPHRASE': self.passphrase
            })

        try:
            async with session.request(
                method, url,
                params=params if method == 'GET' else None,
                json=params if method == 'POST' else None,
                headers=headers
            ) as resp:
                # Verificar límite de tasa (rate limit)
                if resp.status == 429:
                    retry_after = int(resp.headers.get('Retry-After', 5))
                    self.logger.warning("OKX", f"Rate limit (429), esperando {retry_after}s")
                    await asyncio.sleep(retry_after)
                    if retry_count < self.max_retries:
                        return await self._request(method, endpoint, params, signed, retry_count + 1)
                    raise Exception("Rate limit excedido")

                data = await resp.json()

                # Errores de la API
                if data.get('code') != '0':
                    code = data.get('code')
                    msg = data.get('msg', 'Unknown error')
                    self.logger.error("OKX", f"Error API {code}: {msg}")

                    # Errores recuperables (reintentar)
                    if code in ['50000', '50001', '50002', '50010'] and retry_count < self.max_retries:
                        wait = self.retry_backoff * (2 ** retry_count)
                        self.logger.warning("OKX", f"Error recuperable, reintentando en {wait:.1f}s")
                        await asyncio.sleep(wait)
                        return await self._request(method, endpoint, params, signed, retry_count + 1)

                    raise Exception(f"OKX API error: {code} - {msg}")

                # Éxito
                return data.get('data', [{}])[0] if data.get('data') else {}

        except aiohttp.ClientError as e:
            if retry_count < self.max_retries:
                wait = self.retry_backoff * (2 ** retry_count)
                self.logger.warning("OKX", f"Error de conexión, reintentando en {wait:.1f}s: {e}")
                await asyncio.sleep(wait)
                return await self._request(method, endpoint, params, signed, retry_count + 1)
            raise

    # ──────────────────────────────────────────────────────────────
    #  Caché de instrumentos y apalancamiento
    # ──────────────────────────────────────────────────────────────

    async def _get_instrument_info(self, symbol: str) -> Dict:
        """
        Obtiene información del instrumento (minSz, lotSz, tickSz, ctVal, etc.)
        con caché de 1 hora.
        """
        if symbol in self._instrument_cache:
            cached = self._instrument_cache[symbol]
            if time.time() - cached['_timestamp'] < 3600:
                return cached

        result = await self._request('GET', '/api/v5/public/instruments',
                                     {'instType': 'SWAP', 'instId': symbol})
        if result:
            self._instrument_cache[symbol] = {**result, '_timestamp': time.time()}
            return self._instrument_cache[symbol]

        raise ValueError(f"No se encontró instrumento: {symbol}")

    async def _get_leverage(self, symbol: str, side: str = 'long') -> int:
        """
        Obtiene el apalancamiento actual para un símbolo y lado.
        """
        cache_key = f"{symbol}:{side}"
        if cache_key in self._leverage_cache:
            cached = self._leverage_cache[cache_key]
            if time.time() - cached['_timestamp'] < 300:  # 5 minutos
                return cached['leverage']

        result = await self._request('GET', '/api/v5/account/leverage-info',
                                     {'instId': symbol, 'mgnMode': 'isolated'}, signed=True)
        leverage = 1
        if result and isinstance(result, list):
            for item in result:
                if item.get('instId') == symbol:
                    if side == 'long':
                        leverage = int(item.get('lever', 1))
                    else:
                        leverage = int(item.get('lever', 1))
                    break

        self._leverage_cache[cache_key] = {'leverage': leverage, '_timestamp': time.time()}
        return leverage

    async def set_leverage(self, symbol: str, leverage: int, side: str = 'long') -> bool:
        """Configura el apalancamiento para un símbolo."""
        params = {
            'instId': symbol,
            'lever': str(leverage),
            'mgnMode': 'isolated',
            'side': side
        }
        result = await self._request('POST', '/api/v5/account/set-leverage', params, signed=True)
        if result:
            self._leverage_cache[f"{symbol}:{side}"] = {'leverage': leverage, '_timestamp': time.time()}
            self.logger.info("OKX", f"Apalancamiento {symbol} {side} = {leverage}x")
            return True
        return False

    # ──────────────────────────────────────────────────────────────
    #  Métodos públicos (ExchangeAdapter)
    # ──────────────────────────────────────────────────────────────

    async def get_price(self, symbol: str) -> float:
        """Obtiene el precio de mercado actual."""
        result = await self._request('GET', '/api/v5/market/ticker', {'instId': symbol})
        if result:
            return float(result.get('last', 0))
        return 0.0

    async def get_balance(self, asset: Optional[str] = None) -> Dict[str, float]:
        """Obtiene el balance de la cuenta."""
        result = await self._request('GET', '/api/v5/account/balance', signed=True)
        balances = {}
        if result and isinstance(result, list):
            for item in result:
                if item.get('details'):
                    for detail in item['details']:
                        ccy = detail.get('ccy', '')
                        avail = float(detail.get('availBal', 0))
                        frozen = float(detail.get('frozenBal', 0))
                        balances[ccy] = avail + frozen

        if asset:
            return {asset: balances.get(asset, 0.0)}
        return balances

    async def get_positions(self) -> List[Dict]:
        """Obtiene todas las posiciones abiertas."""
        result = await self._request('GET', '/api/v5/account/positions', signed=True)
        positions = []
        if result and isinstance(result, list):
            for pos in result:
                if float(pos.get('pos', 0)) != 0:
                    positions.append({
                        'symbol': pos.get('instId', ''),
                        'side': 'LONG' if float(pos.get('pos', 0)) > 0 else 'SHORT',
                        'amount': abs(float(pos.get('pos', 0))),
                        'entry_price': float(pos.get('avgPx', 0)),
                        'mark_price': float(pos.get('markPx', 0)),
                        'unrealized_pnl': float(pos.get('upl', 0)),
                        'leverage': int(pos.get('lever', 1)),
                        'liquidation_price': float(pos.get('liqPx', 0)),
                        'pos_id': pos.get('posId', ''),
                        'margin': float(pos.get('margin', 0))
                    })
        return positions

    async def create_order(self, symbol: str, side: OrderSide, order_type: OrderType,
                           amount: float, price: Optional[float] = None,
                           stop_price: Optional[float] = None,
                           tp: Optional[float] = None,
                           sl: Optional[float] = None) -> Dict:
        """
        Crea una orden en OKX.
        Soporta MARKET, LIMIT, STOP, STOP_MARKET, TAKE_PROFIT.
        """
        params = {
            'instId': symbol,
            'tdMode': 'isolated',
            'side': side.value.upper(),
            'ordType': order_type.value.upper(),
            'sz': str(amount),
        }

        # Price para LIMIT
        if order_type in [OrderType.LIMIT, OrderType.STOP, OrderType.TAKE_PROFIT]:
            if price is None:
                raise ValueError("Price requerido para órdenes LIMIT/STOP/TAKE_PROFIT")
            params['px'] = str(price)

        # Stop price para STOP y STOP_MARKET
        if order_type in [OrderType.STOP, OrderType.STOP_MARKET]:
            if stop_price is None:
                raise ValueError("Stop price requerido para STOP/STOP_MARKET")
            params['triggerPx'] = str(stop_price)
            params['triggerPxType'] = 'last'

        # TP/SL adjuntos (usando órdenes algorítmicas)
        if tp or sl:
            algo_params = []
            if tp:
                algo_params.append({
                    'algoOrdType': 'take_profit',
                    'tpTriggerPx': str(tp),
                    'tpOrdPx': '-1'  # mercado
                })
            if sl:
                algo_params.append({
                    'algoOrdType': 'stop_loss',
                    'slTriggerPx': str(sl),
                    'slOrdPx': '-1'  # mercado
                })
            params['attachAlgoOrds'] = json.dumps(algo_params)

        result = await self._request('POST', '/api/v5/trade/order', params, signed=True)

        return {
            'orderId': result.get('ordId', ''),
            'symbol': result.get('instId', symbol),
            'side': result.get('side', side.value),
            'type': result.get('ordType', order_type.value),
            'amount': float(result.get('sz', amount)),
            'price': float(result.get('px', price or 0)),
            'status': result.get('state', 'PENDING'),
            'filled': float(result.get('fillSz', 0)),
            'avgPrice': float(result.get('avgPx', 0)),
            'algoIds': result.get('algoIds', [])
        }

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancela una orden existente."""
        params = {
            'instId': symbol,
            'ordId': order_id
        }
        result = await self._request('POST', '/api/v5/trade/cancel-order', params, signed=True)
        return bool(result)

    async def set_stop_loss(self, symbol: str, side: OrderSide, amount: float,
                            stop_price: float) -> Dict:
        """Establece un Stop Loss usando orden algorítmica."""
        return await self.create_order(
            symbol=symbol,
            side=OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY,
            order_type=OrderType.STOP_MARKET,
            amount=amount,
            stop_price=stop_price
        )

    async def set_take_profit(self, symbol: str, side: OrderSide, amount: float,
                              price: float) -> Dict:
        """Establece un Take Profit usando orden algorítmica."""
        return await self.create_order(
            symbol=symbol,
            side=OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY,
            order_type=OrderType.TAKE_PROFIT,
            amount=amount,
            price=price
        )

    async def set_trailing_stop(self, symbol: str, side: OrderSide, amount: float,
                                activation: float, distance: float) -> Dict:
        """
        Establece un Trailing Stop usando orden algorítmica de OKX.
        """
        params = {
            'instId': symbol,
            'tdMode': 'isolated',
            'side': side.value.upper(),
            'ordType': 'TRIGGER',
            'sz': str(amount),
            'triggerPx': str(activation),
            'triggerPxType': 'last',
            'callbackRatio': str(distance * 100),  # OKX usa porcentaje
            'triggerPxType': 'last'
        }
        return await self._request('POST', '/api/v5/trade/order-algo', params, signed=True)

    async def reconcile(self) -> Dict[str, Any]:
        """Reconcilia el estado local con OKX."""
        positions = await self.get_positions()
        balance = await self.get_balance()
        return {
            'positions': positions,
            'balance': balance,
            'timestamp': datetime.now().isoformat()
        }

    async def health_check(self) -> ExchangeHealth:
        """Verifica la salud del exchange."""
        try:
            start = time.perf_counter()
            await self.get_price('BTC-USDT')
            latency_ms = (time.perf_counter() - start) * 1000
            return ExchangeHealth(
                latency_ms=latency_ms,
                error_rate=0.0,
                is_connected=True,
                last_success=datetime.now().isoformat(),
                score=100.0
            )
        except Exception as e:
            self.logger.error("OKX", f"Health check falló: {e}")
            return ExchangeHealth(
                latency_ms=0.0,
                error_rate=1.0,
                is_connected=False,
                last_success='',
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
            rate_limit_per_minute=600
        )

    async def close(self):
        """Cierra la sesión HTTP y limpia cachés."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.logger.debug("OKX", "Sesión HTTP cerrada")
        self._instrument_cache.clear()
        self._leverage_cache.clear()

    # ──────────────────────────────────────────────────────────────
    #  Métodos extendidos (desde Ku-Klux-Klan)
    # ──────────────────────────────────────────────────────────────

    async def get_order_details(self, order_id: str, symbol: str) -> Optional[Dict]:
        """Obtiene detalles de una orden específica."""
        params = {'instId': symbol, 'ordId': order_id}
        result = await self._request('GET', '/api/v5/trade/order', params, signed=True)
        if result and isinstance(result, list) and len(result) > 0:
            return result[0]
        return None

    async def close_position(self, symbol: str, pos_id: Optional[str] = None,
                             amount: Optional[float] = None) -> Dict:
        """
        Cierra una posición por símbolo o posId.
        Si se proporciona posId, se usa ese método (más preciso).
        """
        params = {
            'instId': symbol,
            'mgnMode': 'isolated',
        }
        if pos_id:
            params['posId'] = pos_id
        if amount:
            params['sz'] = str(amount)

        result = await self._request('POST', '/api/v5/trade/close-position', params, signed=True)
        self.logger.info("OKX", f"Posición cerrada: {symbol} (posId={pos_id})")
        return result

    async def get_algo_orders(self, symbol: Optional[str] = None,
                              algo_type: str = 'stop_order') -> List[Dict]:
        """
        Obtiene órdenes algorítmicas (TP/SL/trailing) pendientes.
        """
        params = {'algoOrdType': algo_type}
        if symbol:
            params['instId'] = symbol
        result = await self._request('GET', '/api/v5/trade/orders-algo-pending', params, signed=True)
        if result and isinstance(result, list):
            return result
        return []

    async def amend_algo_order(self, algo_id: str, symbol: str,
                               tp: Optional[float] = None,
                               sl: Optional[float] = None) -> Dict:
        """
        Modifica TP/SL de una orden algorítmica existente.
        """
        params = {
            'algoId': algo_id,
            'instId': symbol,
        }
        if tp is not None:
            params['tpTriggerPx'] = str(tp)
        if sl is not None:
            params['slTriggerPx'] = str(sl)
        return await self._request('POST', '/api/v5/trade/amend-algos', params, signed=True)

    async def fetch_candles(self, symbol: str, bar: str = '1m',
                            limit: int = 100) -> List[Dict]:
        """
        Obtiene velas OHLCV para análisis.
        bar: '1m', '5m', '1h', '1d', etc.
        """
        params = {
            'instId': symbol,
            'bar': bar,
            'limit': str(min(limit, 300))
        }
        result = await self._request('GET', '/api/v5/market/candles', params)
        candles = []
        if result and isinstance(result, list):
            for c in result:
                if len(c) >= 6:
                    candles.append({
                        'timestamp': int(c[0]),
                        'open': float(c[1]),
                        'high': float(c[2]),
                        'low': float(c[3]),
                        'close': float(c[4]),
                        'volume': float(c[5])
                    })
        return candles

    async def self_test(self) -> Dict[str, Any]:
        """
        Autodiagnóstico completo del adaptador OKX.
        Verifica: conexión, tiempo, balance, instrumentos y posiciones.
        """
        results = {
            'status': 'ok',
            'checks': {},
            'errors': []
        }

        # 1. Health check
        health = await self.health_check()
        results['checks']['health'] = {
            'connected': health.is_connected,
            'latency_ms': health.latency_ms,
            'score': health.score
        }
        if not health.is_connected:
            results['errors'].append('Health check falló')

        # 2. Sincronización de tiempo
        await self._sync_time()
        results['checks']['time_sync'] = {
            'offset_ms': self._time_offset,
            'synced': abs(self._time_offset) < 1000
        }

        # 3. Balance
        try:
            balance = await self.get_balance()
            results['checks']['balance'] = {
                'has_usdt': 'USDT' in balance and balance['USDT'] > 0,
                'total_assets': len(balance)
            }
        except Exception as e:
            results['errors'].append(f'Balance check falló: {e}')

        # 4. Instrumentos
        try:
            instrument = await self._get_instrument_info('BTC-USDT')
            results['checks']['instrument'] = {
                'symbol': instrument.get('instId'),
                'min_sz': instrument.get('minSz'),
                'lot_sz': instrument.get('lotSz'),
                'ct_val': instrument.get('ctVal')
            }
        except Exception as e:
            results['errors'].append(f'Instrument check falló: {e}')

        # 5. Posiciones
        try:
            positions = await self.get_positions()
            results['checks']['positions'] = {
                'count': len(positions),
                'open': len([p for p in positions if p.get('state') != 'CLOSED'])
            }
        except Exception as e:
            results['errors'].append(f'Positions check falló: {e}')

        if results['errors']:
            results['status'] = 'degraded'

        return results
