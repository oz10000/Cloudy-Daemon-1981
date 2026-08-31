#!/usr/bin/env python3
"""
1981 DAEMON Ω V3 — Punto de entrada principal

Este archivo es el punto de arranque del sistema. Se encarga de:
- Configurar el PYTHONPATH para que 'src' sea reconocido.
- Parsear argumentos de línea de comandos.
- Cargar la configuración desde YAML y variables de entorno.
- Inicializar el logger.
- Validar el modo de ejecución (con confirmación para 'live').
- Instanciar y ejecutar el Daemon principal.
"""

import sys
import os

# ──────────────────────────────────────────────────────────────────────────────
#  Añadir el directorio raíz al PYTHONPATH para resolver imports absolutos
# ──────────────────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import argparse
from src.core.daemon import Daemon1981Omega
from src.utils.config_loader import load_config
from src.utils.logger import setup_logger


async def main() -> None:
    """
    Función principal asíncrona que orquesta el arranque del sistema.
    """
    parser = argparse.ArgumentParser(
        description="1981 DAEMON Ω V3 — Sistema autónomo de ejecución de señales"
    )
    parser.add_argument(
        '--mode',
        default='standalone',
        choices=['standalone', 'demo', 'live', 'simulation'],
        help="Modo de ejecución (standalone = simulación local, demo = exchange de prueba, live = capital real)"
    )
    parser.add_argument(
        '--config',
        default='./config/config.yaml',
        help="Ruta al archivo de configuración YAML"
    )
    parser.add_argument(
        '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help="Nivel de detalle del logging"
    )
    args = parser.parse_args()

    # ── Cargar configuración ──
    config = load_config(args.config)
    config['mode'] = args.mode
    if 'logging' not in config:
        config['logging'] = {}
    config['logging']['level'] = args.log_level

    # ── Configurar logger ──
    logger = setup_logger(config.get('logging', {}))
    logger.info("BOOT", "1981 DAEMON Ω V3 iniciando...")
    logger.info("BOOT", f"Modo: {args.mode}")

    # ── Validación de seguridad para modo LIVE ──
    if args.mode == 'live':
        confirmation = input("⚠️  MODO LIVE DETECTADO. ¿Estás seguro? (yes/no): ")
        if confirmation.lower() != 'yes':
            logger.info("BOOT", "Abortando inicio en modo live")
            sys.exit(0)

    # ── Arranque del Daemon ──
    try:
        daemon = Daemon1981Omega(config)
        await daemon.run()
    except KeyboardInterrupt:
        logger.info("BOOT", "Interrupción por teclado (KeyboardInterrupt)")
    except Exception as e:
        # CORRECCIÓN: logging con un solo mensaje y formato correcto
        logger.error(f"BOOT — Error fatal: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
