"""
Safety Module - Protection mechanisms for trading system

Components:
- CircuitBreaker: Protects against consecutive losses, daily limits, errors
- Notifier: Sends alerts via Telegram/Discord
"""

from .circuit_breaker import CircuitBreaker, CircuitState, CircuitBreakerType
from .notifier import Notifier, NotificationType

__all__ = [
    "CircuitBreaker",
    "CircuitState",
    "CircuitBreakerType",
    "Notifier",
    "NotificationType",
]
