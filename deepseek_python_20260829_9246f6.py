"""
Logger — Sistema de logging estructurado con rotación
"""

import logging
import logging.handlers
import json
import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any

_LOG_LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}

_LOGGER_INSTANCES: Dict[str, logging.Logger] = {}

class StructuredFormatter(logging.Formatter):
    """Formatter que produce logs en formato JSON estructurado."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "module": record.name,
            "message": record.getMessage()
        }
        
        if hasattr(record, 'extra_data'):
            log_entry["extra"] = record.extra_data
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry)

class ConsoleFormatter(logging.Formatter):
    """Formatter para salida en consola con colores."""
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m'  # Magenta
    }
    RESET = '\033[0m'

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, '')
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        return f"{color}{timestamp} | {record.levelname:<8} | {record.name:>15} | {record.getMessage()}{self.RESET}"

def setup_logger(config: Dict[str, Any]) -> logging.Logger:
    """
    Configura el logger global según la configuración.
    """
    global _LOGGER_INSTANCES
    
    level_name = config.get('level', 'INFO').upper()
    level = _LOG_LEVELS.get(level_name, logging.INFO)
    log_file = config.get('file', './data/logs/daemon.log')
    log_format = config.get('format', 'json')
    max_bytes = config.get('max_bytes', 10 * 1024 * 1024)  # 10MB
    backup_count = config.get('backup_count', 5)
    console = config.get('console', True)

    # Crear directorio si no existe
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    # Obtener logger raíz
    logger = logging.getLogger('1981_daemon')
    logger.setLevel(level)
    logger.handlers.clear()

    # Handler para archivo con rotación
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count
        )
        if log_format == 'json':
            file_handler.setFormatter(StructuredFormatter())
        else:
            file_handler.setFormatter(logging.Formatter('%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'))
        logger.addHandler(file_handler)

    # Handler para consola
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(ConsoleFormatter())
        logger.addHandler(console_handler)

    # Evitar propagación al logger raíz
    logger.propagate = False

    _LOGGER_INSTANCES['root'] = logger
    return logger

def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Obtiene una instancia de logger.
    Si no existe, retorna un logger básico.
    """
    if 'root' in _LOGGER_INSTANCES:
        base_logger = _LOGGER_INSTANCES['root']
        if name:
            return base_logger.getChild(name)
        return base_logger
    
    # Fallback: logger básico
    logging.basicConfig(level=logging.INFO)
    return logging.getLogger(name or '1981_daemon')

def log_extra(extra_data: Dict[str, Any]) -> Dict[str, Any]:
    """Helper para añadir datos extra al log."""
    return {'extra_data': extra_data}