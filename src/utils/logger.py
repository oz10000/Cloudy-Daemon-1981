"""Logger centralizado con formato unificado y rotación."""
import logging
import sys
from typing import Dict, Any, Optional

_LOGGERS = {}

def setup_logger(config: Dict[str, Any]) -> logging.Logger:
    """Configura el logger global con rotación de archivos."""
    level = config.get('level', 'INFO').upper()
    log_file = config.get('file', './data/logs/daemon.log')
    console = config.get('console', True)
    log_format = config.get('format', 'console')

    # Usar el nombre completo para evitar conflictos con la variable local
    logger = logging.getLogger('1981_daemon')
    logger.setLevel(getattr(logging, level, logging.INFO))

    # Limpiar handlers existentes
    logger.handlers.clear()

    # Handler de archivo con rotación
    if log_file:
        import logging.handlers
        fh = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10485760, backupCount=5
        )
        if log_format == 'json':
            fh.setFormatter(logging.Formatter(
                '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "module": "%(name)s", "message": "%(message)s"}'
            ))
        else:
            fh.setFormatter(logging.Formatter(
                '%(asctime)s | %(levelname)-8s | %(name)-15s | %(message)s'
            ))
        logger.addHandler(fh)

    # Handler de consola
    if console:
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)-15s | %(message)s'
        ))
        logger.addHandler(ch)

    logger.propagate = False
    _LOGGERS['root'] = logger
    return logger

def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Obtiene un logger hijo del logger raíz."""
    root = _LOGGERS.get('root')
    if root is None:
        # Fallback: crear un logger básico
        root = logging.getLogger('1981_daemon')
        root.setLevel(logging.INFO)
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)-15s | %(message)s'
        ))
        root.addHandler(ch)
        _LOGGERS['root'] = root
    if name:
        return root.getChild(name)
    return root
