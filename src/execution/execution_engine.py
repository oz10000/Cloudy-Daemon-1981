"""Ejecución de órdenes y monitoreo de posiciones."""
import asyncio
from typing import Dict, Any, Optional
from src.exchanges.base import ExchangeAdapter, OrderSide, OrderType
from src.risk.risk_engine import RiskEngine
from src.execution.order_manager import OrderManager
from src.execution.position_manager import PositionManager
from src.utils.logger import get_logger

logger = get_logger("execution_engine")

class ExecutionEngine:
    def __init__(self, exchange: ExchangeAdapter, risk_engine: RiskEngine, order_manager: OrderManager, position_manager: PositionManager):
        self.exchange = exchange
        self.risk_engine = risk_engine
        self.order_manager = order_manager
        self.position_manager = position_manager
        self.logger = logger

    async def _validate_signal(self, signal: Dict) -> bool:
        required = ['symbol', 'direction', 'entry_price', 'sl_price', 'tp_price']
        for field in required:
            if field not in signal:
                self.logger.warning(f"Señal inválida: falta '{field}'")
                return False
        if signal.get('entry_price', 0) <= 0:
            return False
        if signal.get('sl_price', 0) <= 0:
            return False
        if signal.get('tp_price', 0) <= 0:
            return False
        return signal.get('direction') in ['LONG', 'SHORT']

    async def execute(self, signal: Dict) -> Dict:
        if not await self._validate_signal(signal):
            return {'status': 'rejected', 'reason': 'invalid_signal'}

        symbol = signal['symbol']
        direction = signal['direction']
        entry_price = signal['entry_price']
        sl = signal['sl_price']
        tp = signal['tp_price']
        confidence = signal.get('confidence', 0)
        trailing_distance = signal.get('trailing_distance', 0)

        self.logger.info(f"EXEC — Ejecutando: {symbol} {direction} (confianza={confidence})")

        if entry_price <= 0:
            entry_price = await self.exchange.get_price(symbol)
            if entry_price <= 0:
                return {'status': 'rejected', 'reason': 'invalid_price'}

        balance = await self.exchange.get_balance()
        capital = balance.get('USDT', 0)
        # Usar el risk_engine para calcular el tamaño (cantidad)
        amount = await self.risk_engine.calculate_size(symbol, confidence, leverage=1)
        if amount <= 0:
            return {'status': 'rejected', 'reason': 'invalid_size'}

        side = OrderSide.BUY if direction == 'LONG' else OrderSide.SELL
        # Crear orden usando la interfaz original (OrderSide, OrderType, amount, stop_price)
        order = await self.exchange.create_order(symbol, side, OrderType.MARKET, amount)
        if not order or order.get('status') == 'REJECTED':
            return {'status': 'failed', 'reason': 'order_rejected'}

        avg_price = float(order.get('avgPrice', entry_price))
        if avg_price <= 0:
            avg_price = entry_price

        pos = await self.position_manager.add_position(order, signal)
        if not pos:
            return {'status': 'failed', 'reason': 'position_failed'}

        # Colocar SL y TP
        if sl > 0:
            sl_side = OrderSide.SELL if direction == 'LONG' else OrderSide.BUY
            await self.exchange.set_stop_loss(symbol, sl_side, amount, sl)
        if tp > 0:
            tp_side = OrderSide.SELL if direction == 'LONG' else OrderSide.BUY
            await self.exchange.set_take_profit(symbol, tp_side, amount, tp)

        if trailing_distance > 0:
            pos.trailing_distance = trailing_distance
            pos.trailing_activation = entry_price

        self.logger.info(f"Posición abierta: {pos.id} @ {pos.entry_price}")
        return {'status': 'executed', 'position_id': pos.id, 'order_id': order.get('orderId')}

    async def check_exits(self):
        positions = self.position_manager.get_all()
        for pos in positions:
            try:
                current_price = await self.exchange.get_price(pos.symbol)
                self.position_manager.update_price(pos.id, current_price)
                # Verificar SL/TP
                if pos.get('take_profit') and current_price >= pos['take_profit']:
                    await self._close_position(pos, 'TAKE_PROFIT')
                elif pos.get('stop_loss') and current_price <= pos['stop_loss']:
                    await self._close_position(pos, 'STOP_LOSS')
                # Trailing stop
                if pos.get('trailing_distance'):
                    p = self.position_manager._positions.get(pos['id'])
                    if p:
                        if p.side == 'long' and current_price > p.highest_price:
                            p.highest_price = current_price
                            new_sl = current_price * (1 - p.trailing_distance)
                            if new_sl > p.stop_loss:
                                p.stop_loss = new_sl
                        elif p.side == 'short' and current_price < p.lowest_price:
                            p.lowest_price = current_price
                            new_sl = current_price * (1 + p.trailing_distance)
                            if new_sl < p.stop_loss:
                                p.stop_loss = new_sl
            except Exception as e:
                self.logger.error(f"Error monitoreando {pos.get('symbol')}: {e}")

    async def _close_position(self, position, reason: str):
        self.logger.info(f"Cerrando posición {position.get('id')} por {reason}")
        await self.position_manager.close_position(position.get('id'))
