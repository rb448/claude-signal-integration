"""Emergency mode state machine with persistence."""
import aiosqlite
from datetime import datetime, UTC
from enum import IntEnum
from pathlib import Path
from typing import Optional


class EmergencyStatus(IntEnum):
    """Emergency mode status."""
    NORMAL = 0
    EMERGENCY = 1


class EmergencyMode:
    """
    Emergency mode state machine with SQLite persistence.

    Manages emergency mode activation/deactivation for streamlined incident response.
    Auto-approves safe operations (Read, Grep, Glob) and auto-commits changes.
    """

    VALID_TRANSITIONS = {
        (EmergencyStatus.NORMAL, EmergencyStatus.EMERGENCY),
        (EmergencyStatus.EMERGENCY, EmergencyStatus.NORMAL),
    }

    def __init__(self, db_path: str):
        """
        Initialize emergency mode manager.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path

    async def initialize(self):
        """Initialize database schema and default state."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        async with aiosqlite.connect(self.db_path) as db:
            # Enable WAL mode for concurrent access
            await db.execute("PRAGMA journal_mode=WAL")

            # Create schema
            await db.execute("""
                CREATE TABLE IF NOT EXISTS emergency_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    status INTEGER NOT NULL,
                    activated_at TEXT,
                    activated_by_thread TEXT
                )
            """)

            # Insert default state if not exists
            await db.execute("""
                INSERT OR IGNORE INTO emergency_state (id, status, activated_at, activated_by_thread)
                VALUES (1, ?, NULL, NULL)
            """, (EmergencyStatus.NORMAL.value,))

            await db.commit()

    async def activate(self, thread_id: str):
        """
        Activate emergency mode.

        Args:
            thread_id: Thread that activated emergency mode
        """
        async with aiosqlite.connect(self.db_path) as db:
            # Check current status
            async with db.execute("SELECT status FROM emergency_state WHERE id = 1") as cursor:
                row = await cursor.fetchone()
                current_status = EmergencyStatus(row[0]) if row else EmergencyStatus.NORMAL

            # Idempotent - if already EMERGENCY, don't update
            if current_status == EmergencyStatus.EMERGENCY:
                return

            # Transition NORMAL → EMERGENCY
            now = datetime.now(UTC).isoformat()
            await db.execute("""
                UPDATE emergency_state
                SET status = ?, activated_at = ?, activated_by_thread = ?
                WHERE id = 1
            """, (EmergencyStatus.EMERGENCY.value, now, thread_id))

            await db.commit()

    async def deactivate(self):
        """Deactivate emergency mode."""
        async with aiosqlite.connect(self.db_path) as db:
            # Check current status
            async with db.execute("SELECT status FROM emergency_state WHERE id = 1") as cursor:
                row = await cursor.fetchone()
                current_status = EmergencyStatus(row[0]) if row else EmergencyStatus.NORMAL

            # Idempotent - if already NORMAL, don't update
            if current_status == EmergencyStatus.NORMAL:
                return

            # Transition EMERGENCY → NORMAL
            await db.execute("""
                UPDATE emergency_state
                SET status = ?, activated_at = NULL, activated_by_thread = NULL
                WHERE id = 1
            """, (EmergencyStatus.NORMAL.value,))

            await db.commit()

    async def is_active(self) -> bool:
        """
        Check if emergency mode is active.

        Returns:
            True if emergency mode is EMERGENCY, False if NORMAL
        """
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT status FROM emergency_state WHERE id = 1") as cursor:
                row = await cursor.fetchone()
                if not row:
                    return False
                return EmergencyStatus(row[0]) == EmergencyStatus.EMERGENCY

    async def get_state(self) -> dict:
        """
        Get current emergency mode state.

        Returns:
            Dict with status, activated_at, activated_by_thread
        """
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT status, activated_at, activated_by_thread
                FROM emergency_state
                WHERE id = 1
            """) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return {
                        "status": EmergencyStatus.NORMAL.value,
                        "activated_at": None,
                        "activated_by_thread": None,
                    }
                return {
                    "status": row[0],
                    "activated_at": row[1],
                    "activated_by_thread": row[2],
                }
