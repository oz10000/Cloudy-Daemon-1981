"""
Lifecycle Manager — Gestión del ciclo de vida del sistema
"""

from enum import Enum, auto
from typing import List, Optional, Dict, Any
from datetime import datetime
from src.utils.logger import get_logger

class LifecycleState(Enum):
    BOOT = auto()
    INIT = auto()
    SELF_TEST = auto()
    CERTIFY = auto()
    STANDALONE = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    LIVE = auto()
    RECOVERY = auto()
    SHUTDOWN = auto()
    ERROR = auto()
    PAUSED = auto()
    MAINTENANCE = auto()
    UNKNOWN = auto()

class LifecycleManager:
    """
    Administrador del ciclo de vida con estados, transiciones,
    historial y callbacks de eventos.
    """
    
    def __init__(self):
        self.logger = get_logger()
        self._state = LifecycleState.BOOT
        self._history: List[LifecycleState] = []
        self._callbacks: Dict[LifecycleState, List[callable]] = {}
        self._state_data: Dict[str, Any] = {}
        self._last_transition: Optional[datetime] = None
        self._transition_count: int = 0
        
        # Definir transiciones válidas
        self._transitions = {
            LifecycleState.BOOT: [LifecycleState.INIT, LifecycleState.ERROR],
            LifecycleState.INIT: [LifecycleState.SELF_TEST, LifecycleState.ERROR],
            LifecycleState.SELF_TEST: [LifecycleState.CERTIFY, LifecycleState.RECOVERY, LifecycleState.ERROR],
            LifecycleState.CERTIFY: [LifecycleState.STANDALONE, LifecycleState.ERROR],
            LifecycleState.STANDALONE: [LifecycleState.CONNECTING, LifecycleState.PAUSED, LifecycleState.SHUTDOWN, LifecycleState.ERROR],
            LifecycleState.CONNECTING: [LifecycleState.CONNECTED, LifecycleState.RECOVERY, LifecycleState.ERROR],
            LifecycleState.CONNECTED: [LifecycleState.LIVE, LifecycleState.PAUSED, LifecycleState.RECOVERY, LifecycleState.ERROR],
            LifecycleState.LIVE: [LifecycleState.PAUSED, LifecycleState.RECOVERY, LifecycleState.SHUTDOWN, LifecycleState.ERROR],
            LifecycleState.RECOVERY: [LifecycleState.INIT, LifecycleState.SHUTDOWN, LifecycleState.ERROR],
            LifecycleState.ERROR: [LifecycleState.RECOVERY, LifecycleState.SHUTDOWN],
            LifecycleState.PAUSED: [LifecycleState.CONNECTED, LifecycleState.LIVE, LifecycleState.SHUTDOWN],
            LifecycleState.MAINTENANCE: [LifecycleState.STANDALONE, LifecycleState.SHUTDOWN],
            LifecycleState.SHUTDOWN: [],
            LifecycleState.UNKNOWN: [LifecycleState.BOOT]
        }

    def register_callback(self, state: LifecycleState, callback: callable):
        """Registra un callback para un estado específico."""
        if state not in self._callbacks:
            self._callbacks[state] = []
        self._callbacks[state].append(callback)
        self.logger.debug("LIFECYCLE", f"Callback registrado para {state.name}")

    async def transition_to(self, new_state: LifecycleState, data: Optional[Dict] = None) -> bool:
        """Transiciona a un nuevo estado."""
        if not self.can_transition(new_state):
            self.logger.warning("LIFECYCLE", f"Transición inválida: {self._state.name} -> {new_state.name}")
            return False

        old_state = self._state
        self._history.append(old_state)
        self._state = new_state
        self._last_transition = datetime.now()
        self._transition_count += 1

        if data:
            self._state_data = data

        self.logger.info("LIFECYCLE", f"Transición: {old_state.name} -> {new_state.name} (count={self._transition_count})")

        # Ejecutar callbacks
        if new_state in self._callbacks:
            for callback in self._callbacks[new_state]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(self, data)
                    else:
                        callback(self, data)
                except Exception as e:
                    self.logger.error("LIFECYCLE", f"Callback falló para {new_state.name}: {e}")

        return True

    def can_transition(self, new_state: LifecycleState) -> bool:
        """Verifica si la transición es válida."""
        return new_state in self._transitions.get(self._state, [])

    def get_state(self) -> LifecycleState:
        """Retorna el estado actual."""
        return self._state

    def get_state_name(self) -> str:
        """Retorna el nombre del estado actual."""
        return self._state.name

    def get_history(self) -> List[str]:
        """Retorna el historial de estados."""
        return [s.name for s in self._history]

    def get_status(self) -> Dict[str, Any]:
        """Retorna el estado completo del lifecycle."""
        return {
            'current_state': self._state.name,
            'history': self.get_history(),
            'last_transition': self._last_transition.isoformat() if self._last_transition else None,
            'transition_count': self._transition_count,
            'state_data': self._state_data,
            'is_boot': self._state == LifecycleState.BOOT,
            'is_live': self._state == LifecycleState.LIVE,
            'is_error': self._state == LifecycleState.ERROR,
            'is_shutdown': self._state == LifecycleState.SHUTDOWN,
            'is_recovery': self._state == LifecycleState.RECOVERY,
            'is_standalone': self._state == LifecycleState.STANDALONE,
        }

    def is_operational(self) -> bool:
        """Verifica si el sistema está en estado operativo."""
        return self._state in [LifecycleState.LIVE, LifecycleState.CONNECTED, LifecycleState.STANDALONE]

    def is_safe_to_shutdown(self) -> bool:
        """Verifica si es seguro apagar."""
        return self._state not in [LifecycleState.LIVE, LifecycleState.RECOVERY, LifecycleState.CONNECTING]