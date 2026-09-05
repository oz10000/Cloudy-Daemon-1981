"""
Retry — Decorador para reintentos con backoff exponencial y jitter
"""
import asyncio
import random
import time
import functools
from typing import Type, Tuple, Optional, Callable, Any, Union
from src.utils.logger import get_logger

logger = get_logger()

def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    jitter: float = 0.1,
    exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = (Exception,),
    on_retry: Optional[Callable[[int, Exception], None]] = None,
    log_level: str = "WARNING"
):
    """Decorador para reintentar con backoff exponencial y jitter."""
    if not isinstance(exceptions, tuple):
        exceptions = (exceptions,)
    log_func = getattr(logger, log_level.lower(), logger.warning)

    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            attempt = 1
            current_delay = delay
            last_exception = None

            while attempt <= max_attempts:
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_attempts:
                        logger.error(f"❌ {func.__name__} falló después de {max_attempts} intentos: {e}")
                        raise
                    jitter_amount = random.uniform(-jitter * current_delay, jitter * current_delay)
                    wait_time = max(0.1, current_delay + jitter_amount)
                    if on_retry:
                        try:
                            on_retry(attempt, e)
                        except Exception as cb_err:
                            logger.debug(f"Callback on_retry falló: {cb_err}")
                    log_func(f"⚠️ {func.__name__} intento {attempt}/{max_attempts} falló: {e}. Reintentando en {wait_time:.2f}s...")
                    await asyncio.sleep(wait_time)
                    current_delay *= backoff
                    attempt += 1
            raise last_exception

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            attempt = 1
            current_delay = delay
            last_exception = None
            while attempt <= max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_attempts:
                        logger.error(f"❌ {func.__name__} falló después de {max_attempts} intentos: {e}")
                        raise
                    jitter_amount = random.uniform(-jitter * current_delay, jitter * current_delay)
                    wait_time = max(0.1, current_delay + jitter_amount)
                    if on_retry:
                        try:
                            on_retry(attempt, e)
                        except Exception as cb_err:
                            logger.debug(f"Callback on_retry falló: {cb_err}")
                    log_func(f"⚠️ {func.__name__} intento {attempt}/{max_attempts} falló: {e}. Reintentando en {wait_time:.2f}s...")
                    time.sleep(wait_time)
                    current_delay *= backoff
                    attempt += 1
            raise last_exception

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    return decorator
