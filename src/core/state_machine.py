"""
State Machine — Máquina de estados con historial de transiciones
"""
from enum import Enum, auto
from typing import Optional, Dict, Any
from datetime import datetime
from src.utils.logger import get_logger

class DaemonState(Enum):
    SLEEPING = auto()
    WAITING_EVENT = auto()
    EVENT_RECEIVED = auto()
    VALIDATING = auto()
    RISK_APPROVAL = auto()
    EXECUTING = auto()
    POSITION_ACTIVE = auto()
    MONITORING = auto()
    CERTIFICATION = auto()
    ERROR = auto()
    SHUTDOWN = auto()

class StateMachine:
    def __init__(self):
        self.logger = get_logger()
        self._state = DaemonState.SLEEPING
        self._history = []
        self._state_data = {}

    def get_state(self) -> DaemonState:
        return self._state

    def get_state_name(self) -> str:
        return self._state.name

    def transition_to(self, new_state: DaemonState, data: Optional[Dict] = None) -> bool:
        old_state = self._state
        self._state = new_state
        if data:
            self._state_data = data
        entry = {
            'from': old_state.name,
            'to': new_state.name,
            'timestamp': datetime.now().isoformat(),
            'data': data or {}
        }
        self._history.append(entry)
        if len(self._history) > 1000:
            self._history = self._history[-500:]
        self.logger.info("STATE", f"{old_state.name} → {new_state.name}")
        return True

    def get_history(self, limit: int = 20) -> list:
        return self._history[-limit:]

    def get_status(self) -> Dict:
        return {
            'current_state': self._state.name,
            'last_transition': self._history[-1] if self._history else None,
            'total_transitions': len(self._history)
        }
