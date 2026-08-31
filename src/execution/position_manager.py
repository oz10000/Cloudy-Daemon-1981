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
    direction: str  # 'LONG' or 'SHORT'
    amount: float
    entry_price: float
    mark_price: float
    tp: float = 0.0
    sl: float = 0.0
    trailing_distance: float = 0.0
    trailing_activation: float = 0.0
    breakeven_activation: float = 0.0
    state: str = 'OPEN'  # OPEN, CLOSED, PARTIAL
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    highest_price: float = 0.0
    lowest_price: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    closed_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

class PositionManager:
    """Administrador de posiciones con cálculos avanzados."""

    def __init__(self):
        self.positions: Dict[str, Position] = {}
        self.logger = get_logger()

    def add(self, symbol: str, direction: str, amount: float,
            entry_price: float, tp: float = 0.0, sl: float = 0.0,
            trailing_distance: float = 0.0,
            metadata: Optional[Dict] = None) -> Position:
        """Abre una nueva posición."""
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
            trailing_distance=trailing_distance,
            highest_price=entry_price,
            lowest_price=entry_price,
            metadata=metadata or {}
        )
        self.positions[pos_id] = position
        self.logger.info("POSITION", f"Posición abierta: {pos_id} {symbol} {direction} @ {entry_price}")
        return position

    async def update_prices(self, symbol: str, mark_price: float, exchange=None) -> None:
        """Actualiza el mark price de TODAS las posiciones del símbolo con trailing híbrido."""
        positions = [p for p in self.positions.values() if p.symbol == symbol and p.state == 'OPEN']
        if not positions:
            return

        # Calcular ATR una sola vez para el símbolo
        atr = None
        if exchange and hasattr(exchange, 'fetch_candles'):
            try:
                candles = await exchange.fetch_candles(symbol, bar='5m', limit=15)
                if len(candles) >= 15:
                    tr_list = []
                    for i in range(1, 15):
                        high = candles[i]['high']
                        low = candles[i]['low']
                        prev_close = candles[i-1]['close']
                        tr = max(high-low, abs(high-prev_close), abs(low-prev_close))
                        tr_list.append(tr)
                    atr = sum(tr_list) / 14
            except Exception:
                pass

        for pos in positions:
            pos.mark_price = mark_price
            # Actualizar highest/lowest
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

            # Calcular PnL
            if pos.direction == 'LONG':
                pos.unrealized_pnl = (mark_price - pos.entry_price) * pos.amount
            else:
                pos.unrealized_pnl = (pos.entry_price - mark_price) * pos.amount

            # Trailing Stop híbrido (ATR + beneficio)
            if pos.trailing_distance > 0:
                if atr is not None:
                    volatility_factor = atr / (0.01 * mark_price)
                    dynamic_distance = pos.trailing_distance * (1 + 0.5 * volatility_factor)
                else:
                    dynamic_distance = pos.trailing_distance

                # Reducir distancia si PnL > 5% del capital invertido
                if pos.unrealized_pnl > pos.entry_price * pos.amount * 0.05:
                    dynamic_distance *= 0.5

                if pos.direction == 'LONG':
                    new_sl = mark_price * (1 - dynamic_distance)
                    if new_sl > pos.sl:
                        pos.sl = new_sl
                else:
                    new_sl = mark_price * (1 + dynamic_distance)
                    if new_sl < pos.sl or pos.sl == 0:
                        pos.sl = new_sl

    def close(self, position_id: str, reason: str = "manual") -> Optional[Position]:
        """Cierra una posición."""
        pos = self.positions.get(position_id)
        if not pos or pos.state == 'CLOSED':
            return None

        pos.state = 'CLOSED'
        pos.closed_at = datetime.now().isoformat()
        pos.realized_pnl = pos.unrealized_pnl
        pos.unrealized_pnl = 0.0
        self.logger.info("POSITION", f"Posición cerrada: {position_id} (razón: {reason})")
        return pos

    def get_position(self, position_id: str) -> Optional[Position]:
        return self.positions.get(position_id)

    def get_all(self) -> List[Position]:
        return list(self.positions.values())

    def get_open(self) -> List[Position]:
        return [p for p in self.positions.values() if p.state == 'OPEN']

    def get_closed(self) -> List[Position]:
        return [p for p in self.positions.values() if p.state == 'CLOSED']

    async def restore(self, positions_data: List[Dict]) -> None:
        """Restaura posiciones desde datos guardados."""
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
                trailing_distance=data.get('trailing_distance', 0.0),
                trailing_activation=data.get('trailing_activation', 0.0),
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
        self.logger.info("POSITION", f"Restauradas {len(positions_data)} posiciones")

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
                'trailing_distance': p.trailing_distance,
                'trailing_activation': p.trailing_activation,
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
