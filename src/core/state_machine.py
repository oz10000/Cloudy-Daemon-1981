"""Máquina de estados del daemon con transiciones validadas."""
from enum import Enum, auto
from typing import Set, Tuple
from src.utils.logger import get_logger

logger = get_logger("state_machine")

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
    """Máquina de estados con transiciones predefinidas y logging."""

    def __init__(self):
        self.current_state = DaemonState.SLEEPING
        self._transitions: Set[Tuple[DaemonState, DaemonState]] = {
            (DaemonState.SLEEPING, DaemonState.WAITING_EVENT),
            (DaemonState.WAITING_EVENT, DaemonState.SLEEPING),
            (DaemonState.WAITING_EVENT, DaemonState.EVENT_RECEIVED),
            (DaemonState.EVENT_RECEIVED, DaemonState.VALIDATING),
            # ✅ AÑADIDA: transición directa a SLEEPING después de procesar
            (DaemonState.EVENT_RECEIVED, DaemonState.SLEEPING),
            (DaemonState.VALIDATING, DaemonState.RISK_APPROVAL),
            (DaemonState.RISK_APPROVAL, DaemonState.EXECUTING),
            (DaemonState.EXECUTING, DaemonState.POSITION_ACTIVE),
            (DaemonState.POSITION_ACTIVE, DaemonState.MONITORING),
            (DaemonState.MONITORING, DaemonState.SLEEPING),
            (DaemonState.MONITORING, DaemonState.CERTIFICATION),
            (DaemonState.CERTIFICATION, DaemonState.SLEEPING),
            (DaemonState.ERROR, DaemonState.SLEEPING),
            (DaemonState.ERROR, DaemonState.SHUTDOWN),
            (DaemonState.SLEEPING, DaemonState.ERROR),
            (DaemonState.WAITING_EVENT, DaemonState.ERROR),
            (DaemonState.EXECUTING, DaemonState.ERROR),
        }

    def transition(self, from_state: DaemonState, to_state: DaemonState) -> None:
        if (from_state, to_state) not in self._transitions:
            raise ValueError(f"Transición inválida: {from_state.name} → {to_state.name}")
        old = self.current_state
        self.current_state = to_state
        logger.info(f"STATE: {old.name} → {to_state.name}")

    def is_valid_transition(self, from_state: DaemonState, to_state: DaemonState) -> bool:
        return (from_state, to_state) in self._transitions
