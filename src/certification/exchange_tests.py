# src/certification/exchange_tests.py
"""Tests específicos para adaptadores de exchange"""

from src.exchanges.base import ExchangeAdapter

class ExchangeTests:
    @staticmethod
    async def run_all(exchange: ExchangeAdapter) -> dict:
        """Prueba las funcionalidades básicas de un exchange."""
        results = {'passed': 0, 'total': 0, 'errors': []}
        # Test 1: health check
        try:
            health = await exchange.health_check()
            if health.is_connected:
                results['passed'] += 1
            else:
                results['errors'].append('exchange not connected')
        except Exception as e:
            results['errors'].append(f'health check error: {e}')
        results['total'] += 1
        # Test 2: get_price
        try:
            price = await exchange.get_price('BTCUSDT')
            if price > 0:
                results['passed'] += 1
            else:
                results['errors'].append('invalid price')
        except Exception as e:
            results['errors'].append(f'get_price error: {e}')
        results['total'] += 1
        # Test 3: get_balance
        try:
            balance = await exchange.get_balance()
            if 'USDT' in balance:
                results['passed'] += 1
            else:
                results['errors'].append('balance missing USDT')
        except Exception as e:
            results['errors'].append(f'get_balance error: {e}')
        results['total'] += 1
        return results
