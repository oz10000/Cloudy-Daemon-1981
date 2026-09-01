#!/usr/bin/env python3
"""
Diagnóstico de conexión a OKX
"""
import asyncio
import os
from dotenv import load_dotenv
from src.exchanges.okx import OKXAdapter
from src.utils.logger import get_logger

load_dotenv()

async def main():
    logger = get_logger()
    config = {
        'api_key': os.environ.get('OKX_API_KEY', ''),
        'api_secret': os.environ.get('OKX_SECRET', ''),
        'passphrase': os.environ.get('OKX_PASSPHRASE', ''),
        'testnet': True,
        'futures': True
    }
    exchange = OKXAdapter(config)
    health = await exchange.health_check()
    print(f"Health: conectado={health.is_connected}, latencia={health.latency_ms:.2f}ms")
    if health.is_connected:
        price = await exchange.get_price('BTCUSDT')
        print(f"Precio BTCUSDT: {price}")
        balance = await exchange.get_balance('USDT')
        print(f"Balance USDT: {balance.get('USDT', 0)}")
    await exchange.close()

if __name__ == "__main__":
    asyncio.run(main())
