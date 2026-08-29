# src/daps/validation.py
"""Validación de métricas para DAPS"""

from typing import Dict, Any

def validate_metrics(metrics: Dict) -> bool:
    """Valida que las métricas tengan los campos necesarios."""
    required = ['error_rate', 'latency_ms', 'win_rate', 'sharpe', 'drawdown',
                'avg_confidence', 'connected', 'pending_repairs']
    for field in required:
        if field not in metrics:
            return False
    # Validar rangos
    if not (0 <= metrics['win_rate'] <= 1):
        return False
    if not (0 <= metrics['avg_confidence'] <= 1):
        return False
    if not (0 <= metrics['error_rate'] <= 1):
        return False
    return True
