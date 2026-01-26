"""
Session management module for durable execution.

Provides persistent session storage with SQLite backend.
"""

from .manager import SessionManager, Session, SessionStatus
from .lifecycle import SessionLifecycle, StateTransitionError
from .recovery import CrashRecovery
from .commands import SessionCommands

__all__ = ["SessionManager", "Session", "SessionStatus", "SessionLifecycle", "StateTransitionError", "CrashRecovery", "SessionCommands"]
