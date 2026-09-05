"""Utilidades para manejo de archivos y directorios."""
import os
from pathlib import Path

def ensure_directories(dirs: list) -> None:
    """Crea los directorios necesarios."""
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)

def safe_read_file(path: str) -> str:
    """Lee un archivo de forma segura, retorna vacío si no existe."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except (FileNotFoundError, PermissionError):
        return ""

def safe_write_file(path: str, content: str) -> bool:
    """Escribe un archivo atómicamente."""
    tmp_path = path + '.tmp'
    try:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            f.write(content)
        os.replace(tmp_path, path)
        return True
    except Exception:
        return False
