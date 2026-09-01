from enum import Enum, auto
from typing import Optional, Dict
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

    def get_state(self):
        return self._state

    def get_state_name(self):
        return self._state.name

    def transition_to(self, new_state: DaemonState, data: Optional[Dict] = None) -> bool:
        old = self._state
        self._state = new_state
        entry = {
            'from': old.name,
            'to': new_state.name,
            'timestamp': datetime.now().isoformat(),
            'data': data or {}
        }
        self._history.append(entry)
        self.logger.info("STATE", f"{old.name} → {new_state.name}")
        return True

    def get_history(self, limit=20):
        return self._history[-limit:]

    def get_status(self):
        return {
            'current_state': self._state.name,
            'last_transition': self._history[-1] if self._history else None,
            'total_transitions': len(self._history)
        }
