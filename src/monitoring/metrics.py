# src/monitoring/metrics.py
import numpy as np
from typing import Dict, Any, List
from src.utils.logger import get_logger


class MetricsCollector:
    def __init__(self):
        self.history = []
        self.logger = get_logger()

    async def collect(self, position_manager, order_manager) -> Dict[str, Any]:
        positions = position_manager.get_all()
        closed = [p for p in positions if p.state == 'CLOSED']
        open_positions = [p for p in positions if p.state == 'OPEN']

        wins = sum(1 for p in closed if p.realized_pnl > 0)
        total = len(closed) or 1
        win_rate = wins / total

        avg_pnl = np.mean([p.realized_pnl for p in closed]) if closed else 0.0

        if closed:
            max_pnl = max(p.realized_pnl for p in closed)
            min_pnl = min(p.realized_pnl for p in closed)
            drawdown = (max_pnl - min_pnl) / (max_pnl + 1e-6)
        else:
            drawdown = 0.0

        returns = [p.realized_pnl for p in closed]
        if len(returns) > 1:
            sharpe = np.mean(returns) / (np.std(returns) + 1e-6)
        else:
            sharpe = 0.0

        metrics = {
            'win_rate': win_rate,
            'avg_pnl': avg_pnl,
            'drawdown': drawdown,
            'sharpe': sharpe,
            'total_trades': total,
            'open_positions': len(open_positions),
            'pending_repairs': 0,
            'error_rate': 0.0,
            'latency_ms': 100,
            'avg_confidence': 0.5,
            'connected': True
        }
        self.logger.debug(f"METRICS — WinRate={win_rate:.2%}, Sharpe={sharpe:.2f}")
        return metrics
