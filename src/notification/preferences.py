"""
Notification Preferences - Per-thread notification preference storage.

GREEN Phase: Implementation to make tests pass.
"""

import asyncio
import aiosqlite
import structlog
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional
from src.notification.types import UrgencyLevel

logger = structlog.get_logger(__name__)


# Default notification preferences by urgency level
DEFAULT_PREFERENCES = {
    UrgencyLevel.URGENT: True,        # Always notify by default
    UrgencyLevel.IMPORTANT: True,     # Notify by default
    UrgencyLevel.INFORMATIONAL: False,  # Don't notify by default
    UrgencyLevel.SILENT: False,       # Never notify
}


class NotificationPreferences:
    """
    Manages per-thread notification preferences with SQLite persistence.

    Provides CRUD operations for notification preferences that survive process restarts.
    Uses WAL mode for concurrent access safety.
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

        Creates database directory if needed.
        Enables WAL mode for concurrent access.
        Creates tables and indexes if not exist.
        """
        # Create directory if needed
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        # Open connection
        self._connection = await aiosqlite.connect(self.db_path)

        # Enable WAL mode for concurrent access
        await self._connection.execute("PRAGMA journal_mode=WAL")

        # Load and execute schema
        schema_path = Path(__file__).parent / "schema.sql"
        schema_sql = schema_path.read_text()
        await self._connection.executescript(schema_sql)
        await self._connection.commit()

        self._log.info("initialized", wal_mode=True)

    async def close(self):
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def get_preference(self, thread_id: str, event_type: str) -> Optional[bool]:
        """
        Get notification preference for thread and event type.

        Args:
            thread_id: Signal thread identifier
            event_type: Event type name (e.g., "completion", "error")

        Returns:
            True if enabled, False if disabled, None if not set
        """
        async with self._lock:
            cursor = await self._connection.execute(
                "SELECT enabled FROM notification_preferences WHERE thread_id = ? AND event_type = ?",
                (thread_id, event_type)
            )
            row = await cursor.fetchone()

            if row is None:
                return None

            # SQLite stores boolean as INTEGER (0 or 1)
            return bool(row[0])

    async def set_preference(self, thread_id: str, event_type: str, enabled: bool) -> None:
        """
        Set notification preference for thread and event type.

        Uses upsert (INSERT OR REPLACE) for idempotent updates.

        Args:
            thread_id: Signal thread identifier
            event_type: Event type name (e.g., "completion", "error")
            enabled: Whether notifications are enabled
        """
        async with self._lock:
            now = datetime.now(UTC).isoformat()
            await self._connection.execute(
                """
                INSERT INTO notification_preferences (thread_id, event_type, enabled, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(thread_id, event_type) DO UPDATE SET
                    enabled = excluded.enabled,
                    updated_at = excluded.updated_at
                """,
                (thread_id, event_type, int(enabled), now)
            )
            await self._connection.commit()

            self._log.debug(
                "preference_set",
                thread_id=thread_id,
                event_type=event_type,
                enabled=enabled
            )

    async def get_all_preferences(self, thread_id: str) -> dict[str, bool]:
        """
        Get all notification preferences for a thread.

        Args:
            thread_id: Signal thread identifier

        Returns:
            Dictionary mapping event_type to enabled status
        """
        async with self._lock:
            cursor = await self._connection.execute(
                "SELECT event_type, enabled FROM notification_preferences WHERE thread_id = ?",
                (thread_id,)
            )
            rows = await cursor.fetchall()

            # Convert rows to dict, converting INTEGER to bool
            return {event_type: bool(enabled) for event_type, enabled in rows}

    async def should_notify(
        self,
        thread_id: str,
        event_type: str,
        urgency_level: UrgencyLevel
    ) -> bool:
        """
        Determine if notification should be sent based on preferences and urgency.

        Priority rules (override user preferences):
        1. URGENT urgency → always True (critical events)
        2. SILENT urgency → always False (internal events)

        For IMPORTANT/INFORMATIONAL:
        3. Use stored preference if exists
        4. Use default for urgency level

        Args:
            thread_id: Signal thread identifier
            event_type: Event type name
            urgency_level: Event urgency level

        Returns:
            True if notification should be sent
        """
        # Priority rule 1: URGENT always notifies
        if urgency_level == UrgencyLevel.URGENT:
            return True

        # Priority rule 2: SILENT never notifies
        if urgency_level == UrgencyLevel.SILENT:
            return False

        # Check for stored preference
        stored_preference = await self.get_preference(thread_id, event_type)
        if stored_preference is not None:
            return stored_preference

        # Fall back to default for urgency level
        return DEFAULT_PREFERENCES[urgency_level]
