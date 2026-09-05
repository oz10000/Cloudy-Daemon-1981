"""
Execution Engine — Motor de ejecución de órdenes
"""
import asyncio
from typing import Dict, Any, Optional
from src.exchanges.base import ExchangeAdapter, OrderSide, OrderType
from src.risk.risk_engine import RiskEngine
from src.execution.order_manager import OrderManager
from src.execution.position_manager import PositionManager
from src.utils.logger import get_logger

class ExecutionEngine:
    def __init__(self, exchange: ExchangeAdapter, order_manager: OrderManager,
                 position_manager: PositionManager, risk_engine: RiskEngine):
        self.exchange = exchange
        self.order_manager = order_manager
        self.position_manager = position_manager
        self.risk_engine = risk_engine
        self.logger = get_logger()

    async def _validate_signal(self, signal: Dict) -> bool:
        """Valida que la señal tenga los campos requeridos (formato DAPS)."""
        required = ['symbol', 'direction', 'entry_price', 'sl_price', 'tp_price']
        for field in required:
            if field not in signal:
                self.logger.warning(f"Señal inválida: falta '{field}'")
                return False
        if signal.get('entry_price', 0) <= 0:
            self.logger.warning("Señal inválida: entry_price <= 0")
            return False
        if signal.get('sl_price', 0) <= 0:
            self.logger.warning("Señal inválida: sl_price <= 0")
            return False
        if signal.get('tp_price', 0) <= 0:
            self.logger.warning("Señal inválida: tp_price <= 0")
            return False
        if signal.get('direction') not in ['LONG', 'SHORT']:
            self.logger.warning(f"Dirección inválida: {signal.get('direction')}")
            return False
        return True

    async def execute(self, signal: Dict) -> Dict:
        """Ejecuta una señal de trading."""
        # CORREGIDO: se añadió await
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

        # Si entry_price es 0, obtener precio actual
        if entry_price <= 0:
            entry_price = await self.exchange.get_price(symbol)
            if entry_price <= 0:
                return {'status': 'rejected', 'reason': 'invalid_price'}

        balance = await self.exchange.get_balance()
        capital = balance.get('USDT', 0)
        amount = self.risk_engine.calculate_size(capital, entry_price, sl)
        if amount <= 0:
            return {'status': 'rejected', 'reason': 'invalid_size'}

        if not self.risk_engine.can_open_position(signal):
            return {'status': 'rejected', 'reason': 'risk_limit_reached'}

        # CORREGIDO: usar Enum directamente (no strings)
        side = OrderSide.BUY if direction == 'LONG' else OrderSide.SELL
        exchange_order = await self.exchange.create_order(
            symbol, side, OrderType.MARKET, amount
        )

        if not exchange_order or exchange_order.get('status') == 'REJECTED':
            self.logger.error(f"Orden rechazada: {exchange_order}")
            return {'status': 'failed', 'reason': 'order_rejected'}

        # Asegurar que avgPrice no sea 0
        avg_price = float(exchange_order.get('avgPrice', entry_price))
        if avg_price <= 0:
            avg_price = entry_price

        order = self.order_manager.create_order(
            symbol=symbol,
            side=side.value,
            order_type='market',
            amount=amount,
            price=avg_price,
            metadata={'signal': signal}
        )
        self.order_manager.update_order(order.id, status='FILLED',
                                        filled=amount,
                                        avg_price=avg_price,
                                        exchange_order_id=exchange_order.get('orderId'))

        position = await self.position_manager.add(
            symbol=symbol,
            direction=direction,
            amount=amount,
            entry_price=avg_price,
            tp=tp,
            sl=sl,
            metadata={
                'order_id': order.id,
                'signal': signal,
                'trailing_distance': trailing_distance,
                'confidence': confidence
            }
        )

        # Colocar SL y TP en el exchange
        if sl > 0:
            sl_side = OrderSide.SELL if direction == 'LONG' else OrderSide.BUY
            await self.exchange.set_stop_loss(symbol, sl_side, amount, sl)

        if tp > 0:
            tp_side = OrderSide.SELL if direction == 'LONG' else OrderSide.BUY
            await self.exchange.set_take_profit(symbol, tp_side, amount, tp)

        # CORREGIDO: set_trailing_stop es síncrono → NO usar await
        if trailing_distance > 0:
            self.position_manager.set_trailing_stop(position.id, entry_price, trailing_distance)

        self.logger.info(f"Posición abierta: {position.id} @ {position.entry_price}")
        return {'status': 'executed', 'position_id': position.id, 'order_id': order.id}

    async def process_pending_orders(self):
        pending = self.order_manager.get_orders_by_status('PENDING')
        for order in pending:
            if order.order_type == 'market':
                self.order_manager.update_order(order.id, status='FILLED',
                                                filled=order.amount,
                                                avg_price=order.price)

    async def check_exits(self):
        positions = self.position_manager.get_open()
        for pos in positions:
            try:
                current_price = await self.exchange.get_price(pos.symbol)
            except Exception as e:
                self.logger.error(f"Error obteniendo precio para {pos.symbol}: {e}")
                continue

            self.position_manager.update_prices(pos.symbol, current_price)

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

        # CORREGIDO: usar Enum directamente
        side = OrderSide.SELL if direction == 'LONG' else OrderSide.BUY
        try:
            order = await self.exchange.create_order(symbol, side, OrderType.MARKET, amount)
            if order:
                self.position_manager.close(position.id, reason)
                self.logger.info(f"Posición {position.id} cerrada ({reason})")
        except Exception as e:
            self.logger.error(f"Error cerrando posición {position.id}: {e}")
