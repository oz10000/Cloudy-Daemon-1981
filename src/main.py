#!/usr/bin/env python3
"""
1981 DAEMON Ω V3 — Punto de entrada principal
"""

import asyncio
import argparse
import sys
import os

from src.core.daemon import Daemon1981Omega
from src.utils.config_loader import load_config
from src.utils.logger import setup_logger, get_logger

async def main():
    parser = argparse.ArgumentParser(description="1981 DAEMON Ω V3")
    parser.add_argument('--mode', default='standalone', 
                        choices=['standalone', 'demo', 'live', 'simulation'],
                        help="Modo de ejecución")
    parser.add_argument('--config', default='./config/config.yaml',
                        help="Ruta al archivo de configuración")
    parser.add_argument('--log-level', default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        help="Nivel de logging")
    args = parser.parse_args()
    
    # Cargar configuración
    config = load_config(args.config)
    config['mode'] = args.mode
    if 'logging' not in config:
        config['logging'] = {}
    config['logging']['level'] = args.log_level
    
    # Configurar logger
    logger = setup_logger(config.get('logging', {}))
    logger.info("BOOT", "1981 DAEMON Ω V3 iniciando...")
    logger.info("BOOT", f"Modo: {args.mode}")
    
    # Verificar modo live (seguridad)
    if args.mode == 'live':
        confirmation = input("⚠️  MODO LIVE DETECTADO. ¿Estás seguro? (yes/no): ")
        if confirmation.lower() != 'yes':
            logger.info("BOOT", "Abortando inicio en modo live")
            sys.exit(0)
    
    # Iniciar daemon
    try:
        daemon = Daemon1981Omega(config)
        await daemon.run()
    except KeyboardInterrupt:
        logger.info("BOOT", "Interrupción por teclado")
    except Exception as e:
        logger.error("BOOT", f"Error fatal: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
