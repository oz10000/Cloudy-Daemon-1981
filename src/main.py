#!/usr/bin/env python3
import asyncio
import argparse
import os
import sys
from src.core.daemon import Daemon1981
from src.utils.config_loader import load_config
from src.utils.logger import setup_logger, get_logger
from src.utils.file_manager import ensure_directories

async def main():
    parser = argparse.ArgumentParser(description="1981 DAEMON Ω V4")
    parser.add_argument('--mode', default='standalone', choices=['standalone', 'live'])
    parser.add_argument('--config', default='./config/config.yaml')
    parser.add_argument('--log-level', default='INFO')
    args = parser.parse_args()

    config = load_config(args.config)
    config['mode'] = args.mode
    log_config = config.get('logging', {})
    log_config['level'] = args.log_level
    logger = setup_logger(log_config)

    ensure_directories(['./data/logs', './data/state', './data/snapshots'])

    logger.info("BOOT", "1981 DAEMON Ω V4 iniciando...")
    if args.mode == 'live':
        confirmation = input("⚠️  MODO LIVE. ¿Estás seguro? (yes/no): ")
        if confirmation.lower() != 'yes':
            sys.exit(0)

    daemon = Daemon1981(config)
    try:
        await daemon.run()
    except KeyboardInterrupt:
        logger.info("BOOT", "Interrupción por teclado")
    except Exception as e:
        logger.error("BOOT", f"Error fatal: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
