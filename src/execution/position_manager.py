"""Gestión de posiciones con trailing stop."""
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime
from src.utils.logger import get_logger

logger = get_logger("position_manager")

class Position:
    def __init__(self, data: Dict):
        self.id = data.get('id', str(uuid.uuid4()))
        self.symbol = data.get('symbol')
        self.side = data.get('side')
        self.entry_price = data.get('entry_price', 0.0)
        self.amount = data.get('amount', 0.0)
        self.leverage = data.get('leverage', 1)
        self.stop_loss = data.get('stop_loss')
        self.take_profit = data.get('take_profit')
        self.trailing_distance = data.get('trailing_distance', 0.0)
        self.trailing_activation = data.get('trailing_activation', 0.0)
        self.highest_price = data.get('highest_price', self.entry_price)
        self.lowest_price = data.get('lowest_price', self.entry_price)
        self.entry_time = data.get('entry_time', datetime.now().isoformat())
        self.current_price = self.entry_price
        self.pnl = 0.0
        self.extra = data

class PositionManager:
    def __init__(self, exchange, store):
        self.exchange = exchange
        self.store = store
        self._positions: Dict[str, Position] = {}
        self.logger = logger

    async def add_position(self, order_data: Dict, signal: Dict) -> Optional[Position]:
        pos_data = {
            'id': order_data.get('id'),
            'symbol': signal.get('symbol'),
            'side': signal.get('direction', '').lower(),
            'entry_price': signal.get('entry_price') or order_data.get('price'),
            'amount': order_data.get('amount'),
            'leverage': signal.get('leverage', 1),
            'stop_loss': signal.get('sl_price'),
            'take_profit': signal.get('tp_price'),
            'trailing_distance': signal.get('trailing_distance'),
            'trailing_activation': signal.get('entry_price', 0.0),
            'highest_price': signal.get('entry_price', 0.0),
            'lowest_price': signal.get('entry_price', 0.0),
            'entry_time': datetime.now().isoformat()
        }
        pos = Position(pos_data)
        self._positions[pos.id] = pos
        await self.store.save_position(pos_data)
        self.logger.info(f"POSITION — Posición {pos.id} abierta para {pos.symbol}")
        return pos

    def update_price(self, pos_id: str, price: float) -> None:
        pos = self._positions.get(pos_id)
        if not pos:
            return
        pos.current_price = price
        if pos.side == 'long':
            pos.pnl = (price - pos.entry_price) * pos.amount
            if price > pos.highest_price:
                pos.highest_price = price
        else:
            pos.pnl = (pos.entry_price - price) * pos.amount
            if price < pos.lowest_price:
                pos.lowest_price = price

    async def close_position(self, pos_id: str) -> bool:
        if pos_id in self._positions:
            del self._positions[pos_id]
            await self.store.delete_position(pos_id)
            self.logger.info(f"POSITION — Posición {pos_id} cerrada")
            return True
        return False

    def get_all(self) -> List[Dict]:
        return [{
            'id': p.id,
            'symbol': p.symbol,
            'side': p.side,
            'entry_price': p.entry_price,
            'amount': p.amount,
            'leverage': p.leverage,
            'stop_loss': p.stop_loss,
            'take_profit': p.take_profit,
            'trailing_distance': p.trailing_distance,
            'current_price': p.current_price,
            'pnl': p.pnl
        } for p in self._positions.values()]

    def __getitem__(self, key):
        return self._positions.get(key)
