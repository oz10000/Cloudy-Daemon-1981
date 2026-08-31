#!/usr/bin/env python3
"""
1981 DAEMON Ω V3 — Punto de entrada principal
"""

import sys
import os
# Añadir el directorio raíz al PYTHONPATH para resolver imports absolutos
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import argparse
from src.core.daemon import Daemon1981Omega
from src.utils.config_loader import load_config
from src.utils.logger import setup_logger

async def main() -> None:
    parser = argparse.ArgumentParser(description="1981 DAEMON Ω V3")
    parser.add_argument('--mode', default='standalone',
                        choices=['standalone', 'demo', 'live', 'simulation'])
    parser.add_argument('--config', default='./config/config.yaml')
    parser.add_argument('--log-level', default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'])
    args = parser.parse_args()

    config = load_config(args.config)
    config['mode'] = args.mode
    if 'logging' not in config:
        config['logging'] = {}
    config['logging']['level'] = args.log_level

    logger = setup_logger(config.get('logging', {}))
    logger.info("BOOT — 1981 DAEMON Ω V3 iniciando...")
    logger.info(f"BOOT — Modo: {args.mode}")

    if args.mode == 'live':
        confirmation = input("⚠️  MODO LIVE DETECTADO. ¿Estás seguro? (yes/no): ")
        if confirmation.lower() != 'yes':
            logger.info("BOOT — Abortando inicio en modo live")
            sys.exit(0)

    try:
        daemon = Daemon1981Omega(config)
        await daemon.run()
    except KeyboardInterrupt:
        logger.info("BOOT — Interrupción por teclado")
    except Exception as e:
        logger.error(f"BOOT — Error fatal: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
