# src/monitoring/metrics.py
"""Metrics Collector — Recolección de métricas de trading"""

from typing import Dict, Any, List
import numpy as np

class MetricsCollector:
    def __init__(self):
        self.history = []

    async def collect(self, position_manager, order_manager) -> Dict[str, Any]:
        """Recolecta métricas del sistema."""
        positions = position_manager.get_all()
        closed = [p for p in positions if p.state == 'CLOSED']
        open_positions = [p for p in positions if p.state == 'OPEN']

        # Cálculo de win rate
        wins = sum(1 for p in closed if p.realized_pnl > 0)
        total = len(closed) or 1
        win_rate = wins / total

        # PnL promedio
        avg_pnl = np.mean([p.realized_pnl for p in closed]) if closed else 0.0

        # Drawdown (simplificado)
        if closed:
            max_pnl = max(p.realized_pnl for p in closed)
            min_pnl = min(p.realized_pnl for p in closed)
            drawdown = (max_pnl - min_pnl) / (max_pnl + 1e-6)
        else:
            drawdown = 0.0

        # Sharpe ratio (simplificado)
        returns = [p.realized_pnl for p in closed]
        if len(returns) > 1:
            sharpe = np.mean(returns) / (np.std(returns) + 1e-6)
        else:
            sharpe = 0.0

        return {
            'win_rate': win_rate,
            'avg_pnl': avg_pnl,
            'drawdown': drawdown,
            'sharpe': sharpe,
            'total_trades': total,
            'open_positions': len(open_positions),
            'pending_repairs': 0,  # se actualiza desde repair_engine
            'error_rate': 0.0,
            'latency_ms': 100,
            'avg_confidence': 0.5,
            'connected': True
        }