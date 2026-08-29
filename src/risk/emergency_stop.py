"""
Emergency Stop — Circuit breaker global
"""

import asyncio
from typing import Optional
from datetime import datetime
from enum import Enum
from src.utils.logger import get_logger

class EmergencyStopReason(Enum):
    MANUAL = "manual"
    DAPS_CRITICAL = "daps_critical"
    DRAWDOWN_LIMIT = "drawdown_limit"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    EXCHANGE_DISCONNECTED = "exchange_disconnected"
    SYSTEM_ERROR = "system_error"

class EmergencyStop:
    """Circuit breaker que detiene toda la operación."""
    
    def __init__(self):
        self.logger = get_logger()
        self._active = False
        self._reason: Optional[EmergencyStopReason] = None
        self._activated_at: Optional[datetime] = None
        self._cooldown_until: Optional[datetime] = None
        self._cooldown_seconds = 300  # 5 minutos por defecto

    def activate(self, reason: EmergencyStopReason, cooldown_seconds: Optional[int] = None):
        """Activa el emergency stop."""
        if self._active:
            self.logger.warning("EMERGENCY", "Emergency stop ya activo")
            return
        
        self._active = True
        self._reason = reason
        self._activated_at = datetime.now()
        if cooldown_seconds:
            self._cooldown_seconds = cooldown_seconds
        self._cooldown_until = datetime.now().timestamp() + self._cooldown_seconds
        
        self.logger.critical("EMERGENCY", f"STOP ACTIVADO! Razón: {reason.value}. Cooldown: {self._cooldown_seconds}s")
        # Llamar a callbacks externos si se configuran (ej: enviar alerta)
        asyncio.create_task(self._auto_release())

    async def _auto_release(self):
        """Auto-libera el stop después del cooldown."""
        await asyncio.sleep(self._cooldown_seconds)
        if self._active:
            self.release("auto_release")

    def release(self, reason: str = "manual_release"):
        """Desactiva el emergency stop."""
        if not self._active:
            return
        
        self._active = False
        self._reason = None
        self._activated_at = None
        self._cooldown_until = None
        self.logger.info("EMERGENCY", f"STOP desactivado. Razón: {reason}")

    def is_active(self) -> bool:
        """Verifica si el emergency stop está activo."""
        return self._active

    def get_status(self) -> dict:
        """Retorna el estado actual."""
        return {
            'active': self._active,
            'reason': self._reason.value if self._reason else None,
            'activated_at': self._activated_at.isoformat() if self._activated_at else None,
            'cooldown_until': self._cooldown_until
        }
