import logging
import sys
from typing import Dict, Any, Optional
import logging.handlers  # Importar explícitamente para evitar conflictos

_LOGGERS = {}

def setup_logger(config: Dict[str, Any]) -> logging.Logger:
    """Configura el logger global con rotación."""
    level = config.get('level', 'INFO').upper()
    log_file = config.get('file', './data/logs/daemon.log')
    console = config.get('console', True)
    log_format = config.get('format', 'console')

    # Crear logger raíz
    root_logger = logging.getLogger('1981_daemon')
    root_logger.setLevel(getattr(logging, level, logging.INFO))
    root_logger.handlers.clear()

    # Handler de archivo con rotación
    if log_file:
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
        root_logger.addHandler(fh)

    if console:
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)-15s | %(message)s'
        ))
        root_logger.addHandler(ch)

    root_logger.propagate = False
    _LOGGERS['root'] = root_logger
    return root_logger

def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Obtiene un logger hijo del logger raíz."""
    root = _LOGGERS.get('root')
    if root is None:
        # Fallback: configurar básico
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
