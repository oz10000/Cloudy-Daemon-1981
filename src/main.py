#!/usr/bin/env python3
"""
1981 DAEMON Ω V4 — Punto de entrada principal
Soporte: modo standalone, demo, live
"""
import asyncio
import argparse
import os
import sys
from pathlib import Path

# Asegurar que el directorio raíz esté en el PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.daemon import Daemon1981
from src.utils.config_loader import load_config
from src.utils.logger import setup_logger
from src.utils.file_manager import ensure_directories

async def main():
    parser = argparse.ArgumentParser(description="1981 DAEMON Ω V4")
    parser.add_argument(
        '--mode',
        default='standalone',
        choices=['standalone', 'demo', 'live'],
        help="Modo de ejecución: standalone, demo (simulador), live (real)"
    )
    parser.add_argument('--config', default='./config/config.yaml')
    parser.add_argument('--log-level', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'])
    args = parser.parse_args()

    # Cargar configuración
    config = load_config(args.config)
    config['mode'] = args.mode

    # Si es modo demo, forzar uso de simulador
    if args.mode == 'demo':
        config['exchange'] = {'name': 'simulator', 'testnet': True, 'leverage': 1}
        config['signal_source']['check_interval'] = 30
        print("🔬 MODO DEMO ACTIVADO — USANDO SIMULADOR")

    # Configurar logging
    log_config = config.get('logging', {})
    log_config['level'] = args.log_level
    logger = setup_logger(log_config)

    # Asegurar directorios
    ensure_directories([
        './data/logs',
        './data/state',
        './data/snapshots',
        './data/backups',
    ])

    # CORREGIDO: un solo argumento
    logger.info(f"BOOT: 1981 DAEMON Ω V4 iniciando en modo {args.mode}")

    # Advertencia para modo live
    if args.mode == 'live':
        confirmation = input("⚠️ MODO LIVE DETECTADO. ¿Estás seguro? (yes/no): ")
        if confirmation.lower() != 'yes':
            logger.info("BOOT: Abortado por seguridad")
            sys.exit(0)

    # Instanciar y ejecutar daemon
    daemon = Daemon1981(config)
    try:
        await daemon.run()
    except KeyboardInterrupt:
        logger.info("BOOT: Interrupción por teclado")
    except Exception as e:
        logger.error(f"BOOT: Error fatal: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
