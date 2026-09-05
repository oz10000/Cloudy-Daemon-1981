"""
Retry Exceptions — Excepciones específicas para el sistema de reintentos
"""

class RetryableError(Exception):
    """Error que merece reintento (transitorio, recuperable)."""
    pass

class NonRetryableError(Exception):
    """Error que NO merece reintento (error lógico, permanente)."""
    pass

class CircuitBreakerOpenError(Exception):
    """Error cuando el circuit breaker está abierto."""
    pass
