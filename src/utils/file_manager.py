"""
File Manager — Utilidades para manejo de archivos y directorios
"""
import os
from pathlib import Path

def ensure_directories(dirs: list):
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)

def read_yaml_file(path: str) -> dict:
    import yaml
    if not os.path.exists(path):
        return {}
    with open(path, 'r') as f:
        return yaml.safe_load(f) or {}

def write_yaml_file(path: str, data: dict):
    import yaml
    Path(os.path.dirname(path)).mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        yaml.dump(data, f, default_flow_style=False)
