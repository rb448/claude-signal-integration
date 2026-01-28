"""
Notification Preferences - Per-thread notification preference storage.

RED Phase: Stub implementation that will fail tests.
"""

import asyncio
import aiosqlite
import structlog
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional
from src.notification.types import UrgencyLevel

logger = structlog.get_logger(__name__)


class NotificationPreferences:
    """
    Manages per-thread notification preferences with SQLite persistence.

    Stub implementation - tests will fail.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize NotificationPreferences.

        Args:
            db_path: Path to SQLite database. Defaults to Application Support location.
        """
        if db_path is None:
            db_path = str(
                Path.home() / "Library" / "Application Support" /
                "claude-signal-daemon" / "notification_prefs.db"
            )

        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()
        self._log = logger.bind(db_path=db_path)

    async def initialize(self):
        """
        Initialize database connection and schema.

        Stub - does nothing yet.
        """
        pass

    async def close(self):
        """Close database connection."""
        pass

    async def get_preference(self, thread_id: str, event_type: str) -> Optional[bool]:
        """
        Get notification preference for thread and event type.

        Stub - always returns None.
        """
        return None

    async def set_preference(self, thread_id: str, event_type: str, enabled: bool) -> None:
        """
        Set notification preference for thread and event type.

        Stub - does nothing.
        """
        pass

    async def get_all_preferences(self, thread_id: str) -> dict[str, bool]:
        """
        Get all notification preferences for a thread.

        Stub - always returns empty dict.
        """
        return {}

    async def should_notify(
        self,
        thread_id: str,
        event_type: str,
        urgency_level: UrgencyLevel
    ) -> bool:
        """
        Determine if notification should be sent based on preferences and urgency.

        Stub - always returns False.
        """
        return False
