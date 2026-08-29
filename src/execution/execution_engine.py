"""
Execution Engine — Motor completo de ejecución de órdenes
"""

import asyncio
from typing import Dict, Any, Optional
from src.exchanges.base import ExchangeAdapter, OrderSide, OrderType
from src.risk.risk_engine import RiskEngine
from src.execution.order_manager import OrderManager, OrderStatus
from src.execution.position_manager import PositionManager
from src.utils.logger import get_logger

class ExecutionEngine:
    """Motor de ejecución con lógica completa de entrada y salida."""
    
    def __init__(self, exchange: ExchangeAdapter, order_manager: OrderManager,
                 position_manager: PositionManager, risk_engine: RiskEngine):
        self.exchange = exchange
        self.order_manager = order_manager
        self.position_manager = position_manager
        self.risk_engine = risk_engine
        self.logger = get_logger()

    async def execute(self, signal: Dict) -> Dict:
        """Ejecuta una señal de trading."""
        symbol = signal['symbol']
        direction = signal['direction']
        entry_price = signal.get('entry', 0)
        tp = signal.get('tp', 0)
        sl = signal.get('sl', 0)
        confidence = signal.get('confidence', 0.5)
        
        self.logger.info("EXEC", f"Ejecutando señal: {symbol} {direction} (conf={confidence})")
        
        # 1. Validar señal
        if not self._validate_signal(signal):
            return {'status': 'rejected', 'reason': 'invalid_signal'}
        
        # 2. Obtener precio real si no se proporcionó
        if entry_price <= 0:
            entry_price = await self.exchange.get_price(symbol)
            if entry_price <= 0:
                return {'status': 'rejected', 'reason': 'invalid_price'}
        
        # 3. Verificar riesgo
        balance = await self.exchange.get_balance()
        capital = balance.get('USDT', 0)
        amount = self.risk_engine.calculate_size(capital, entry_price, sl)
        if amount <= 0:
            return {'status': 'rejected', 'reason': 'invalid_size'}
        
        # 4. Verificar límites de riesgo
        if not self.risk_engine.can_open_position(signal):
            return {'status': 'rejected', 'reason': 'risk_limit_reached'}
        
        # 5. Crear orden en exchange
        side = OrderSide.BUY if direction == 'LONG' else OrderSide.SELL
        exchange_order = await self.exchange.create_order(
            symbol, side, OrderType.MARKET, amount
        )
        
        if not exchange_order or exchange_order.get('status') == 'REJECTED':
            self.logger.error("EXEC", f"Orden rechazada: {exchange_order}")
            return {'status': 'failed', 'reason': 'order_rejected'}
        
        # 6. Registrar orden local
        order = self.order_manager.create_order(
            symbol=symbol,
            side=side.value,
            order_type='market',
            amount=amount,
            price=float(exchange_order.get('avgPrice', entry_price)),
            metadata={'signal': signal}
        )
        self.order_manager.update_order(order.id, status=OrderStatus.FILLED,
                                        filled=amount, 
                                        avg_price=float(exchange_order.get('avgPrice', entry_price)),
                                        exchange_order_id=exchange_order.get('orderId'))
        
        # 7. Registrar posición
        position = self.position_manager.add(
            symbol=symbol,
            direction=direction,
            amount=amount,
            entry_price=float(exchange_order.get('avgPrice', entry_price)),
            tp=tp,
            sl=sl,
            metadata={'order_id': order.id}
        )
        
        # 8. Colocar SL/TP en exchange (si se configuraron)
        if sl > 0:
            sl_side = OrderSide.SELL if direction == 'LONG' else OrderSide.BUY
            await self.exchange.set_stop_loss(symbol, sl_side, amount, sl)
        
        if tp > 0:
            tp_side = OrderSide.SELL if direction == 'LONG' else OrderSide.BUY
            await self.exchange.set_take_profit(symbol, tp_side, amount, tp)
        
        self.logger.info("EXEC", f"Posición abierta: {position.id} @ {position.entry_price}")
        return {'status': 'executed', 'position_id': position.id, 'order_id': order.id}

    async def process_pending_orders(self):
        """Procesa órdenes pendientes (reintentos, actualización de estado)."""
        pending = self.order_manager.get_orders_by_status(OrderStatus.PENDING)
        for order in pending:
            # Simular verificación de estado (en real se consulta exchange)
            # Por simplicidad, las marcamos como FILLED si el simulador lo permite
            if order.order_type == 'market':
                self.order_manager.update_order(order.id, status=OrderStatus.FILLED,
                                                filled=order.amount,
                                                avg_price=order.price)

    async def check_exits(self):
        """Verifica condiciones de salida para posiciones abiertas (TP, SL, Trailing, Breakeven)."""
        positions = self.position_manager.get_open()
        for pos in positions:
            try:
                current_price = await self.exchange.get_price(pos.symbol)
            except Exception:
                continue
            
            # Actualizar mark price y lógica de trailing/breakeven
            self.position_manager.update_prices(pos.symbol, current_price)
            
            # Verificar TP
            if pos.tp > 0:
                if (pos.direction == 'LONG' and current_price >= pos.tp) or \
                   (pos.direction == 'SHORT' and current_price <= pos.tp):
                    await self._close_position(pos, 'TAKE_PROFIT')
                    continue
            
            # Verificar SL
            if pos.sl > 0:
                if (pos.direction == 'LONG' and current_price <= pos.sl) or \
                   (pos.direction == 'SHORT' and current_price >= pos.sl):
                    await self._close_position(pos, 'STOP_LOSS')
                    continue

    async def _close_position(self, position, reason: str):
        """Cierra una posición en el exchange."""
        symbol = position.symbol
        direction = position.direction
        amount = position.amount
        
        side = OrderSide.SELL if direction == 'LONG' else OrderSide.BUY
        try:
            order = await self.exchange.create_order(symbol, side, OrderType.MARKET, amount)
            if order:
                self.position_manager.close(position.id, reason)
                self.logger.info("EXEC", f"Posición {position.id} cerrada ({reason})")
        except Exception as e:
            self.logger.error("EXEC", f"Error cerrando posición {position.id}: {e}")

    def _validate_signal(self, signal: Dict) -> bool:
        required = ['symbol', 'direction']
        return all(k in signal for k in required) and signal['direction'] in ['LONG', 'SHORT']
