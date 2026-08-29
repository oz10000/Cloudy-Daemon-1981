# src/repair/diagnosis.py
"""Diagnóstico del sistema"""

from typing import Dict, Any

def diagnose(daemon) -> Dict[str, Any]:
    """Genera un diagnóstico completo del sistema."""
    return {
        'state': daemon.state_machine.get_state_name(),
        'lifecycle': daemon.lifecycle.get_state_name(),
        'supervisor_health': daemon.supervisor.get_status(),
        'positions': len(daemon.position_manager.get_open()),
        'orders': len(daemon.order_manager.get_open_orders()),
        'exchange_connected': daemon.exchange.health_check().is_connected,
        'emergency_stop': daemon.emergency_stop.is_active()
    }