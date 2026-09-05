"""OKX Adapter — Adaptador para OKX Futures con reintentos."""
import os
import time
import hmac
import base64
import hashlib
from typing import Optional, Dict, Any
import aiohttp
from src.exchanges.base import ExchangeAdapter, OrderSide, OrderType
from src.utils.logger import get_logger
from src.utils.retry import retry

logger = get_logger("okx")

class OKXAdapter(ExchangeAdapter):
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logger
        self.api_key = config.get('api_key', os.environ.get('OKX_API_KEY', ''))
        self.secret = config.get('secret', os.environ.get('OKX_SECRET', ''))
        self.passphrase = config.get('passphrase', os.environ.get('OKX_PASSPHRASE', ''))
        self.testnet = config.get('testnet', True)
        self.base_url = "https://www.okx.com"
        self.session = None

    async def _ensure_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    def _sign(self, timestamp: str, method: str, path: str, body: str = '') -> str:
        message = timestamp + method.upper() + path + body
        mac = hmac.new(self.secret.encode('utf-8'), message.encode('utf-8'), hashlib.sha256)
        return base64.b64encode(mac.digest()).decode('utf-8')

    @retry(max_attempts=3, delay=1.0, backoff=2.0, exceptions=(aiohttp.ClientError, TimeoutError))
    async def _request(self, method: str, path: str, params: Dict = None, signed: bool = False) -> Dict:
        await self._ensure_session()
        url = self.base_url + path
        headers = {'Content-Type': 'application/json'}
        if signed and self.api_key:
            timestamp = str(int(time.time()))
            body = ''
            if method == 'POST' and params:
                import json
                body = json.dumps(params)
            signature = self._sign(timestamp, method, path, body)
            headers.update({
                'OK-ACCESS-KEY': self.api_key,
                'OK-ACCESS-SIGN': signature,
                'OK-ACCESS-TIMESTAMP': timestamp,
                'OK-ACCESS-PASSPHRASE': self.passphrase
            })
        async with self.session.request(method, url, params=params if method == 'GET' else None, json=params if method == 'POST' else None, headers=headers) as resp:
            data = await resp.json()
            if data.get('code') != '0':
                self.logger.error(f"OKX error: {data.get('msg')}")
                raise Exception(f"OKX API error: {data.get('msg')}")
            return data.get('data', [{}])[0] if data.get('data') else {}

    @retry(max_attempts=3, delay=1.0, backoff=2.0, exceptions=(Exception,))
    async def get_price(self, symbol: str) -> float:
        result = await self._request('GET', '/api/v5/market/ticker', {'instId': symbol})
        return float(result.get('last', 0))

    @retry(max_attempts=3, delay=1.0, backoff=2.0, exceptions=(Exception,))
    async def get_balance(self, asset: Optional[str] = None) -> Dict[str, float]:
        result = await self._request('GET', '/api/v5/account/balance', signed=True)
        balances = {}
        if result and result.get('details'):
            for item in result['details']:
                balances[item['ccy']] = float(item.get('availBal', 0))
        if asset:
            return {asset: balances.get(asset, 0)}
        return balances

    @retry(max_attempts=3, delay=1.0, backoff=2.0, exceptions=(Exception,))
    async def create_order(self, symbol: str, side: OrderSide, order_type: OrderType,
                           amount: float, price: Optional[float] = None,
                           stop_price: Optional[float] = None) -> Dict:
        # Adaptar a la interfaz OKX
        params = {
            'instId': symbol,
            'tdMode': 'isolated',
            'side': side.value.upper(),
            'ordType': order_type.value.upper(),
            'sz': str(amount)
        }
        if price is not None and order_type != OrderType.MARKET:
            params['px'] = str(price)
        if stop_price is not None:
            params['slTriggerPx'] = str(stop_price)
        # Para simplificar, no se maneja take_profit aquí; se haría en otra llamada
        result = await self._request('POST', '/api/v5/trade/order', params, signed=True)
        return {
            'orderId': result.get('ordId'),
            'symbol': result.get('instId'),
            'side': result.get('side'),
            'type': result.get('ordType'),
            'amount': float(result.get('sz', 0)),
            'price': float(result.get('px', 0)),
            'status': result.get('state'),
            'avgPrice': float(result.get('px', 0))
        }

    @retry(max_attempts=3, delay=1.0, backoff=2.0, exceptions=(Exception,))
    async def cancel_order(self, order_id: str) -> bool:
        params = {'ordId': order_id}
        await self._request('POST', '/api/v5/trade/cancel-order', params, signed=True)
        return True

    @retry(max_attempts=3, delay=1.0, backoff=2.0, exceptions=(Exception,))
    async def cancel_all_orders(self) -> bool:
        # OKX no tiene cancel_all directo; en producción se listan y cancelan
        return True

    # ─── Contrato CertifiableModule (opcional) ──────────────────────────
    @property
    def name(self) -> str:
        return "okx"
    @property
    def version(self) -> str:
        return "1.0.0"
    async def health(self) -> Dict:
        try:
            await self.get_price('BTC-USDT')
            return {"status": "healthy", "exchange": "okx"}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    async def start(self) -> bool:
        await self._ensure_session()
        return True
    async def stop(self) -> bool:
        await self.close()
        return True
    async def test(self) -> Dict:
        try:
            price = await self.get_price('BTC-USDT')
            return {"passed": True, "message": f"OKX test OK, price={price}"}
        except Exception as e:
            return {"passed": False, "message": str(e)}
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
    async def get_position(self, symbol: str) -> Optional[Dict]:
        return None
