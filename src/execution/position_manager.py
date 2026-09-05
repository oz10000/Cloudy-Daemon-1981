"""
Position Manager — Gestión de posiciones, PnL, Trailing Stop y Breakeven
"""
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
from src.utils.logger import get_logger

@dataclass
class Position:
    id: str
    symbol: str
    direction: str
    amount: float
    entry_price: float
    mark_price: float
    tp: float = 0.0
    sl: float = 0.0
    trailing_activation: float = 0.0
    trailing_distance: float = 0.0
    breakeven_activation: float = 0.0
    state: str = 'OPEN'
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    highest_price: float = 0.0
    lowest_price: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    closed_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

class PositionManager:
    def __init__(self):
        self.positions: Dict[str, Position] = {}
        self.logger = get_logger()

    async def add(self, symbol: str, direction: str, amount: float,
                  entry_price: float, tp: float = 0.0, sl: float = 0.0,
                  metadata: Optional[Dict] = None) -> Position:
        pos_id = f"pos_{uuid.uuid4().hex[:12]}"
        position = Position(
            id=pos_id,
            symbol=symbol,
            direction=direction,
            amount=amount,
            entry_price=entry_price,
            mark_price=entry_price,
            tp=tp,
            sl=sl,
            highest_price=entry_price,
            lowest_price=entry_price,
            metadata=metadata or {}
        )
        # Leer trailing_distance desde metadata
        if metadata and 'trailing_distance' in metadata:
            position.trailing_distance = metadata['trailing_distance']
        if metadata and 'trailing_activation' in metadata:
            position.trailing_activation = metadata['trailing_activation']

        self.positions[pos_id] = position
        self.logger.info(f"Posición abierta: {pos_id} {symbol} {direction} @ {entry_price}")
        return position

    def update_prices(self, symbol: str, mark_price: float) -> Optional[Position]:
        positions = [p for p in self.positions.values() if p.symbol == symbol and p.state == 'OPEN']
        for pos in positions:
            pos.mark_price = mark_price

            if pos.direction == 'LONG':
                if mark_price > pos.highest_price:
                    pos.highest_price = mark_price
                if mark_price < pos.lowest_price:
                    pos.lowest_price = mark_price
            else:
                if mark_price < pos.lowest_price:
                    pos.lowest_price = mark_price
                if mark_price > pos.highest_price:
                    pos.highest_price = mark_price

            if pos.direction == 'LONG':
                pos.unrealized_pnl = (mark_price - pos.entry_price) * pos.amount
            else:
                pos.unrealized_pnl = (pos.entry_price - mark_price) * pos.amount

            if pos.trailing_distance > 0:
                if pos.direction == 'LONG':
                    if pos.highest_price >= pos.trailing_activation:
                        new_sl = pos.highest_price * (1 - pos.trailing_distance)
                        if new_sl > pos.sl:
                            pos.sl = new_sl
                            self.logger.debug(f"Trailing SL actualizado a {new_sl:.2f} para {pos.id}")
                else:
                    if pos.lowest_price <= pos.trailing_activation:
                        new_sl = pos.lowest_price * (1 + pos.trailing_distance)
                        if new_sl < pos.sl or pos.sl == 0:
                            pos.sl = new_sl
                            self.logger.debug(f"Trailing SL actualizado a {new_sl:.2f} para {pos.id}")

            if pos.breakeven_activation > 0:
                profit_percent = abs((mark_price - pos.entry_price) / pos.entry_price)
                if profit_percent >= pos.breakeven_activation:
                    if pos.sl != pos.entry_price:
                        pos.sl = pos.entry_price
                        self.logger.debug(f"SL movido a breakeven para {pos.id}")

        return positions[0] if positions else None

    def close(self, position_id: str, reason: str = "manual") -> Optional[Position]:
        pos = self.positions.get(position_id)
        if not pos or pos.state == 'CLOSED':
            return None
        pos.state = 'CLOSED'
        pos.closed_at = datetime.now().isoformat()
        pos.realized_pnl = pos.unrealized_pnl
        pos.unrealized_pnl = 0.0
        self.logger.info(f"Posición cerrada: {position_id} (razón: {reason})")
        return pos

    def get_position(self, position_id: str) -> Optional[Position]:
        return self.positions.get(position_id)

    def get_all(self) -> List[Position]:
        return list(self.positions.values())

    def get_open(self) -> List[Position]:
        return [p for p in self.positions.values() if p.state == 'OPEN']

    def has_open_positions(self) -> bool:
        return any(p.state == 'OPEN' for p in self.positions.values())

    def get_closed(self) -> List[Position]:
        return [p for p in self.positions.values() if p.state == 'CLOSED']

    def set_trailing_stop(self, position_id: str, activation: float, distance: float) -> bool:
        pos = self.positions.get(position_id)
        if not pos:
            return False
        pos.trailing_activation = activation
        pos.trailing_distance = distance
        self.logger.info(f"Trailing activado para {position_id} (activation={activation}, dist={distance})")
        return True

    def set_breakeven(self, position_id: str, activation: float) -> bool:
        pos = self.positions.get(position_id)
        if not pos:
            return False
        pos.breakeven_activation = activation
        self.logger.info(f"Breakeven activado para {position_id} (activation={activation})")
        return True

    async def restore(self, positions_data: List[Dict]) -> None:
        for data in positions_data:
            pos = Position(
                id=data['id'],
                symbol=data['symbol'],
                direction=data['direction'],
                amount=data['amount'],
                entry_price=data['entry_price'],
                mark_price=data.get('mark_price', data['entry_price']),
                tp=data.get('tp', 0.0),
                sl=data.get('sl', 0.0),
                trailing_activation=data.get('trailing_activation', 0.0),
                trailing_distance=data.get('trailing_distance', 0.0),
                breakeven_activation=data.get('breakeven_activation', 0.0),
                state=data.get('state', 'OPEN'),
                realized_pnl=data.get('realized_pnl', 0.0),
                unrealized_pnl=data.get('unrealized_pnl', 0.0),
                highest_price=data.get('highest_price', data['entry_price']),
                lowest_price=data.get('lowest_price', data['entry_price']),
                created_at=data.get('created_at', datetime.now().isoformat()),
                closed_at=data.get('closed_at', ''),
                metadata=data.get('metadata', {})
            )
            self.positions[pos.id] = pos
        self.logger.info(f"Restauradas {len(positions_data)} posiciones")

    def to_dict(self) -> List[Dict]:
        return [
            {
                'id': p.id,
                'symbol': p.symbol,
                'direction': p.direction,
                'amount': p.amount,
                'entry_price': p.entry_price,
                'mark_price': p.mark_price,
                'tp': p.tp,
                'sl': p.sl,
                'trailing_activation': p.trailing_activation,
                'trailing_distance': p.trailing_distance,
                'breakeven_activation': p.breakeven_activation,
                'state': p.state,
                'realized_pnl': p.realized_pnl,
                'unrealized_pnl': p.unrealized_pnl,
                'highest_price': p.highest_price,
                'lowest_price': p.lowest_price,
                'created_at': p.created_at,
                'closed_at': p.closed_at,
                'metadata': p.metadata
            }
            for p in self.positions.values()
        ]
