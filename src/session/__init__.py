"""
Session management module for durable execution.

Provides persistent session storage with SQLite backend.
"""

from .manager import SessionManager, Session, SessionStatus
from .lifecycle import SessionLifecycle, StateTransitionError

__all__ = ["SessionManager", "Session", "SessionStatus", "SessionLifecycle", "StateTransitionError"]
