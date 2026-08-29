"""
State Machine — Máquina de estados mejorada con history y events
"""

from enum import Enum, auto
from typing import List, Optional, Dict, Any, Set
from datetime import datetime
from src.utils.logger import get_logger

class State(Enum):
    BOOT = auto()
    INIT = auto()
    SELF_TEST = auto()
    CERTIFY = auto()
    STANDALONE = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    LIVE = auto()
    PAUSED = auto()
    RECOVERY = auto()
    ERROR = auto()
    SHUTDOWN = auto()
    MAINTENANCE = auto()
    UNKNOWN = auto()

class StateEvent(Enum):
    """Eventos que disparan transiciones."""
    START = "start"
    STOP = "stop"
    PAUSE = "pause"
    RESUME = "resume"
    FAIL = "fail"
    RECOVER = "recover"
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    CERTIFY = "certify"
    SHUTDOWN = "shutdown"
    RESET = "reset"

class StateMachine:
    """
    Máquina de estados con transiciones validadas, historial,
    callbacks y soporte para eventos.
    """
    
    def __init__(self):
        self.logger = get_logger()
        self._state = State.BOOT
        self._previous_state = State.UNKNOWN
        self._history: List[State] = []
        self._transition_map = self._build_transition_map()
        self._callbacks: Dict[State, List[callable]] = {}
        self._timestamp = datetime.now()
        self._state_data: Dict[str, Any] = {}
        self._event_handlers: Dict[StateEvent, List[callable]] = {}

    def _build_transition_map(self) -> Dict[State, Set[State]]:
        """Construye el mapa de transiciones válidas."""
        return {
            State.BOOT: {State.INIT, State.SELF_TEST, State.ERROR},
            State.INIT: {State.SELF_TEST, State.STANDALONE, State.ERROR},
            State.SELF_TEST: {State.CERTIFY, State.STANDALONE, State.RECOVERY, State.ERROR},
            State.CERTIFY: {State.STANDALONE, State.ERROR},
            State.STANDALONE: {State.CONNECTING, State.PAUSED, State.SHUTDOWN, State.ERROR, State.MAINTENANCE},
            State.CONNECTING: {State.CONNECTED, State.RECOVERY, State.ERROR, State.SHUTDOWN},
            State.CONNECTED: {State.LIVE, State.PAUSED, State.RECOVERY, State.ERROR, State.SHUTDOWN},
            State.LIVE: {State.PAUSED, State.RECOVERY, State.ERROR, State.SHUTDOWN, State.CONNECTING},
            State.PAUSED: {State.CONNECTED, State.LIVE, State.SHUTDOWN, State.ERROR, State.RECOVERY},
            State.RECOVERY: {State.INIT, State.STANDALONE, State.SHUTDOWN, State.ERROR},
            State.ERROR: {State.RECOVERY, State.SHUTDOWN, State.INIT},
            State.SHUTDOWN: set(),
            State.MAINTENANCE: {State.STANDALONE, State.SHUTDOWN, State.ERROR},
            State.UNKNOWN: {State.BOOT}
        }

    def register_callback(self, state: State, callback: callable):
        """Registra un callback para entrada a un estado."""
        if state not in self._callbacks:
            self._callbacks[state] = []
        self._callbacks[state].append(callback)

    def register_event_handler(self, event: StateEvent, handler: callable):
        """Registra un handler para un evento."""
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)

    def transition_to(self, new_state: State, data: Optional[Dict] = None) -> bool:
        """Transiciona a un nuevo estado."""
        if new_state == self._state:
            self.logger.debug("STATE", f"Ya en {new_state.name}, ignorando")
            return True

        if not self.can_transition(new_state):
            self.logger.warning("STATE", f"Transición inválida: {self._state.name} -> {new_state.name}")
            return False

        old_state = self._state
        self._previous_state = old_state
        self._state = new_state
        self._timestamp = datetime.now()
        if data:
            self._state_data = data

        self._history.append(old_state)
        if len(self._history) > 100:
            self._history.pop(0)

        self.logger.info("STATE", f"Transición: {old_state.name} -> {new_state.name}")

        # Ejecutar callbacks
        if new_state in self._callbacks:
            for callback in self._callbacks[new_state]:
                try:
                    callback(self, old_state, new_state, data)
                except Exception as e:
                    self.logger.error("STATE", f"Callback falló para {new_state.name}: {e}")

        return True

    def handle_event(self, event: StateEvent, data: Optional[Dict] = None) -> bool:
        """Maneja un evento y realiza la transición correspondiente."""
        self.logger.debug("STATE", f"Evento: {event.value}")

        # Mapeo de eventos a estados
        event_map = {
            StateEvent.START: State.CONNECTING,
            StateEvent.STOP: State.SHUTDOWN,
            StateEvent.PAUSE: State.PAUSED,
            StateEvent.RESUME: State.LIVE,
            StateEvent.FAIL: State.ERROR,
            StateEvent.RECOVER: State.RECOVERY,
            StateEvent.CONNECT: State.CONNECTED,
            StateEvent.DISCONNECT: State.STANDALONE,
            StateEvent.CERTIFY: State.CERTIFY,
            StateEvent.SHUTDOWN: State.SHUTDOWN,
            StateEvent.RESET: State.BOOT
        }

        new_state = event_map.get(event)
        if not new_state:
            self.logger.warning("STATE", f"Evento no mapeado: {event}")
            return False

        result = self.transition_to(new_state, data)

        # Ejecutar handlers de eventos
        if event in self._event_handlers:
            for handler in self._event_handlers[event]:
                try:
                    handler(self, event, data)
                except Exception as e:
                    self.logger.error("STATE", f"EventHandler falló para {event.value}: {e}")

        return result

    def can_transition(self, new_state: State) -> bool:
        """Verifica si la transición es válida."""
        return new_state in self._transition_map.get(self._state, set())

    def get_state(self) -> State:
        return self._state

    def get_state_name(self) -> str:
        return self._state.name

    def get_previous_state(self) -> Optional[State]:
        return self._previous_state

    def get_history(self) -> List[str]:
        return [s.name for s in self._history]

    def get_status(self) -> Dict[str, Any]:
        return {
            'state': self._state.name,
            'previous_state': self._previous_state.name if self._previous_state else 'NONE',
            'history': self.get_history(),
            'timestamp': self._timestamp.isoformat(),
            'state_data': self._state_data
        }

    def is_operational(self) -> bool:
        return self._state in [State.LIVE, State.CONNECTED, State.STANDALONE]

    def is_safe(self) -> bool:
        return self._state not in [State.ERROR, State.RECOVERY, State.SHUTDOWN]