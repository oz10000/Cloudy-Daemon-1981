# src/repair/repair_engine.py
from typing import Dict, List, Any
from datetime import datetime, timedelta
from src.utils.logger import get_logger


class RepairEngine:
    def __init__(self, config: Dict):
        self.config = config
        self.logger = get_logger()
        self.repairs = []

    async def detect(self, position_manager, order_manager, exchange) -> List[Dict]:
        issues = []
        positions = position_manager.get_all()
        for pos in positions:
            if pos.state == 'OPEN':
                if pos.sl == 0:
                    issues.append({'type': 'missing_sl', 'position': pos})
                if pos.tp == 0:
                    issues.append({'type': 'missing_tp', 'position': pos})
        orders = order_manager.get_open_orders()
        for order in orders:
            if order.status == 'PENDING' and order.created_at < (datetime.now() - timedelta(minutes=5)).isoformat():
                issues.append({'type': 'stale_order', 'order': order})
        return issues

    async def repair(self, issue: Dict, position_manager, order_manager, exchange):
        pos = issue.get('position')
        if issue['type'] == 'missing_sl':
            self.logger.info(f"REPAIR — Reparando SL faltante para {pos.symbol}")
            if pos.direction == 'LONG':
                sl_price = pos.entry_price * 0.98
            else:
                sl_price = pos.entry_price * 1.02
            await exchange.set_stop_loss(pos.symbol, 'SELL' if pos.direction == 'LONG' else 'BUY',
                                         pos.amount, sl_price)
            pos.sl = sl_price
            self.repairs.append({'type': 'sl_added', 'symbol': pos.symbol, 'sl': sl_price})
        elif issue['type'] == 'missing_tp':
            self.logger.info(f"REPAIR — Reparando TP faltante para {pos.symbol}")
            if pos.direction == 'LONG':
                tp_price = pos.entry_price * 1.05
            else:
                tp_price = pos.entry_price * 0.95
            await exchange.set_take_profit(pos.symbol, 'SELL' if pos.direction == 'LONG' else 'BUY',
                                           pos.amount, tp_price)
            pos.tp = tp_price
            self.repairs.append({'type': 'tp_added', 'symbol': pos.symbol, 'tp': tp_price})
        elif issue['type'] == 'stale_order':
            self.logger.info(f"REPAIR — Cancelando orden huérfana {issue['order'].id}")
            await exchange.cancel_order(issue['order'].id, issue['order'].symbol)
            order_manager.update_order(issue['order'].id, status='CANCELLED')
            self.repairs.append({'type': 'order_cancelled', 'order_id': issue['order'].id})
