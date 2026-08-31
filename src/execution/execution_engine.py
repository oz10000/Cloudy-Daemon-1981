# src/execution/execution_engine.py
import asyncio
from typing import Dict, Any
from src.exchanges.base import ExchangeAdapter, OrderSide, OrderType, OrderStatus
from src.risk.risk_engine import RiskEngine
from src.execution.order_manager import OrderManager
from src.execution.position_manager import PositionManager
from src.utils.logger import get_logger

class ExecutionEngine:
    @property
    def name(self) -> str:
        return "ExecutionEngine"

    @property
    def version(self) -> str:
        return "1.0.0"

    def __init__(self, exchange: ExchangeAdapter, order_manager: OrderManager,
                 position_manager: PositionManager, risk_engine: RiskEngine):
        self.exchange = exchange
        self.order_manager = order_manager
        self.position_manager = position_manager
        self.risk_engine = risk_engine
        self.logger = get_logger()
        self._healthy = True

    async def health(self) -> Dict[str, Any]:
        return {
            'status': 'ok' if self._healthy else 'error',
            'exchange_connected': hasattr(self.exchange, 'health_check') and (await self.exchange.health_check()).is_connected,
            'pending_orders': len(self.order_manager.get_open_orders())
        }

    async def test(self) -> Dict[str, Any]:
        passed = 0
        total = 2
        try:
            valid_signal = {'symbol': 'BTCUSDT', 'direction': 'LONG', 'entry_price': 60000, 'sl_price': 59000, 'tp_price': 61000}
            if self._validate_signal(valid_signal):
                passed += 1
            health = await self.health()
            if health.get('status') == 'ok':
                passed += 1
        except Exception:
            pass
        return {'passed': passed, 'total': total, 'errors': [] if passed == total else ['Alguna prueba falló']}

    async def execute(self, signal: Dict) -> Dict:
        symbol = signal['symbol']
        direction = signal['direction']
        entry_price = signal.get('entry_price', 0)
        tp = signal.get('tp_price', 0)
        sl = signal.get('sl_price', 0)
        confidence = signal.get('confidence', 0)
        leverage = signal.get('leverage', 1)

        self.logger.info(f"EXEC — Ejecutando: {symbol} {direction} (confianza={confidence}, leverage={leverage}x)")

        if not self._validate_signal(signal):
            return {'status': 'rejected', 'reason': 'invalid_signal'}

        balance = await self.exchange.get_balance()
        capital = balance.get('USDT', 0)
        amount = self.risk_engine.calculate_size(capital, entry_price, sl)

        if amount <= 0:
            self.logger.warning(f"EXEC — Tamaño inválido para {symbol}")
            return {'status': 'rejected', 'reason': 'invalid_size'}

        side = OrderSide.BUY if direction == 'LONG' else OrderSide.SELL
        order = await self.exchange.create_order(symbol, side, OrderType.MARKET, amount)

        if not order or order.get('status') in ['REJECTED', 'CANCELLED']:
            self.logger.error(f"EXEC — Orden falló: {order}")
            return {'status': 'failed', 'reason': 'order_rejected'}

        position = await self.position_manager.add(
            symbol=symbol,
            direction=direction,
            amount=amount,
            entry_price=order.get('price', entry_price),
            tp=tp,
            sl=sl,
            trailing_distance=signal.get('trailing_distance', 0.0),
            metadata={'order_id': order.get('orderId')}
        )

        if tp:
            side_tp = OrderSide.SELL if direction == 'LONG' else OrderSide.BUY
            await self.exchange.set_take_profit(symbol, side_tp, amount, tp)

        if sl:
            side_sl = OrderSide.SELL if direction == 'LONG' else OrderSide.BUY
            await self.exchange.set_stop_loss(symbol, side_sl, amount, sl)

        self.logger.info(f"EXEC — Posición abierta: {symbol} {direction} @ {position.entry_price}")
        return {'status': 'executed', 'position_id': position.id, 'order_id': order.get('orderId')}

    async def _validate_signal(self, signal: Dict) -> bool:
        required = ['symbol', 'direction', 'entry_price', 'sl_price', 'tp_price']
        for field in required:
            if field not in signal:
                return False
        if signal['entry_price'] <= 0 or signal['tp_price'] <= 0 or signal['sl_price'] <= 0:
            return False
        if signal['direction'] not in ['LONG', 'SHORT']:
            return False
        return True

    async def process_pending_orders(self):
        pending = self.order_manager.get_orders_by_status(OrderStatus.PENDING)
        for order in pending:
            if order.order_type == 'market':
                self.order_manager.update_order(order.id, status=OrderStatus.FILLED,
                                                filled=order.amount,
                                                avg_price=order.price)

    async def check_exits(self):
        positions = self.position_manager.get_open()
        for pos in positions:
            try:
                current_price = await self.exchange.get_price(pos.symbol)
            except Exception:
                continue
            await self.position_manager.update_prices(pos.symbol, current_price, self.exchange)
            if pos.tp > 0:
                if (pos.direction == 'LONG' and current_price >= pos.tp) or \
                   (pos.direction == 'SHORT' and current_price <= pos.tp):
                    await self._close_position(pos, 'TAKE_PROFIT')
                    continue
            if pos.sl > 0:
                if (pos.direction == 'LONG' and current_price <= pos.sl) or \
                   (pos.direction == 'SHORT' and current_price >= pos.sl):
                    await self._close_position(pos, 'STOP_LOSS')
                    continue

    async def _close_position(self, position, reason: str):
        symbol = position.symbol
        direction = position.direction
        amount = position.amount
        side = OrderSide.SELL if direction == 'LONG' else OrderSide.BUY
        try:
            order = await self.exchange.create_order(symbol, side, OrderType.MARKET, amount)
            if order:
                self.position_manager.close(position.id, reason)
                self.logger.info(f"EXEC — Posición {position.id} cerrada ({reason})")
        except Exception as e:
            self.logger.error(f"EXEC — Error cerrando posición {position.id}: {e}")
