#!/usr/bin/env python3
"""
Simulador end-to-end del Daemon (sin dinero real)
"""
import asyncio
import json
import os
from src.core.daemon import Daemon1981
from src.utils.config_loader import load_config
from src.utils.logger import setup_logger

async def main():
    config = load_config('./config/config.yaml')
    config['mode'] = 'standalone'
    config['exchange']['name'] = 'simulator'
    config['signal_source']['check_interval'] = 10

    logger = setup_logger({'level': 'INFO', 'console': True})
    logger.info("SIM", "Iniciando simulación...")

    daemon = Daemon1981(config)
    # Ejecutar solo una iteración para prueba
    await daemon._restore_state()
    await daemon._check_for_signal()
    logger.info("SIM", "Simulación completada")

if __name__ == "__main__":
    asyncio.run(main())
