"""
Config Loader — Carga de configuración desde YAML + variables de entorno
"""

import os
import yaml
from typing import Dict, Any, Optional
from dotenv import load_dotenv

def load_config(config_path: str = './config/config.yaml') -> Dict[str, Any]:
    """
    Carga la configuración desde un archivo YAML y la sobrescribe
    con variables de entorno que comiencen con 'DAEMON_'.
    """
    # Cargar .env si existe
    load_dotenv()
    
    # Cargar YAML
    config: Dict[str, Any] = {}
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f) or {}
    
    # Sobrescribir con variables de entorno (DAEMON_*)
    for key, value in os.environ.items():
        if key.startswith('DAEMON_'):
            # Convertir DAEMON_RISK_MAX_POSITIONS -> risk.max_positions
            path_parts = key[7:].lower().split('_')
            target = config
            for part in path_parts[:-1]:
                if part not in target:
                    target[part] = {}
                target = target[part]
            
            # Convertir valor (bool, int, float, str)
            env_value = value
            if env_value.lower() == 'true':
                env_value = True
            elif env_value.lower() == 'false':
                env_value = False
            else:
                try:
                    if '.' in env_value:
                        env_value = float(env_value)
                    else:
                        env_value = int(env_value)
                except ValueError:
                    pass  # mantener como string
            
            target[path_parts[-1]] = env_value
    
    return config

def get_exchange_config(exchange_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Obtiene la configuración específica para un exchange."""
    exchanges = config.get('exchanges', {})
    exchange_config = exchanges.get(exchange_name, {})
    
    # Cargar variables específicas del exchange
    prefix = f"DAEMON_EXCHANGE_{exchange_name.upper()}_"
    for key, value in os.environ.items():
        if key.startswith(prefix):
            env_key = key[len(prefix):].lower()
            exchange_config[env_key] = value
    
    return exchange_config