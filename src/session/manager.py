"""
Session Manager - Persistent session storage with SQLite.

GREEN Phase: Implementation to make tests pass.
"""

import asyncio
import json
import aiosqlite
import structlog
from dataclasses import dataclass
from datetime import datetime, UTC
from enum import Enum
from pathlib import Path
from typing import Optional
from uuid import uuid4

logger = structlog.get_logger(__name__)


class SessionNotFoundError(Exception):
    """Raised when a session is not found."""
    pass


class SessionStatus(Enum):
    """Session lifecycle states."""
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    TERMINATED = "TERMINATED"


@dataclass
class Session:
    """
    Session data model.

    Represents a single Claude Code session with durable state.
    """
    id: str
    project_path: str
    thread_id: str
    status: SessionStatus
    context: dict
    created_at: datetime
    updated_at: datetime


class SessionManager:
    """
    Manages session lifecycle with SQLite persistence.

    Provides CRUD operations for sessions that survive process restarts.
    Uses WAL mode for concurrent access safety.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize SessionManager.

        Args:
            db_path: Path to SQLite database. Defaults to ~/.claude-signal/sessions.db
        """
        if db_path is None:
            db_path = str(Path.home() / ".claude-signal" / "sessions.db")

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

    async def close(self):
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def create(self, project_path: str, thread_id: str) -> Session:
        """
        Create new session with unique ID.

        Args:
            project_path: Path to project directory
            thread_id: Signal thread ID for this session

        Returns:
            Session with generated UUID, CREATED status, timestamps
        """
        session_id = str(uuid4())
        now = datetime.now(UTC)
        status = SessionStatus.CREATED
        context = {}

        async with self._lock:
            await self._connection.execute(
                """
                INSERT INTO sessions (id, project_path, thread_id, status, context, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    project_path,
                    thread_id,
                    status.value,
                    json.dumps(context),
                    now.isoformat(),
                    now.isoformat(),
                )
            )
            await self._connection.commit()

        return Session(
            id=session_id,
            project_path=project_path,
            thread_id=thread_id,
            status=status,
            context=context,
            created_at=now,
            updated_at=now,
        )

    async def get(self, session_id: str) -> Optional[Session]:
        """
        Retrieve session by ID.

        Args:
            session_id: Session UUID to retrieve

        Returns:
            Session if exists, None otherwise
        """
        async with self._lock:
            cursor = await self._connection.execute(
                """
                SELECT id, project_path, thread_id, status, context, created_at, updated_at
                FROM sessions
                WHERE id = ?
                """,
                (session_id,)
            )
            row = await cursor.fetchone()

        if row is None:
            return None

        return self._row_to_session(row)

    async def list(self) -> list[Session]:
        """
        List all sessions ordered by created_at DESC.

        Returns:
            List of sessions, newest first
        """
        async with self._lock:
            cursor = await self._connection.execute(
                """
                SELECT id, project_path, thread_id, status, context, created_at, updated_at
                FROM sessions
                ORDER BY created_at DESC
                """
            )
            rows = await cursor.fetchall()

        return [self._row_to_session(row) for row in rows]

    async def update(
        self,
        session_id: str,
        status: Optional[SessionStatus] = None,
        context: Optional[dict] = None
    ) -> Session:
        """
        Update session status and/or context.

        Args:
            session_id: Session UUID to update
            status: New status (if provided)
            context: New context dict (if provided)

        Returns:
            Updated Session
        """
        now = datetime.now(UTC)

        # Build update fields dynamically
        updates = []
        params = []

        if status is not None:
            updates.append("status = ?")
            params.append(status.value)

        if context is not None:
            updates.append("context = ?")
            params.append(json.dumps(context))

        # Always update timestamp
        updates.append("updated_at = ?")
        params.append(now.isoformat())

        # Add WHERE clause parameter
        params.append(session_id)

        async with self._lock:
            await self._connection.execute(
                f"""
                UPDATE sessions
                SET {", ".join(updates)}
                WHERE id = ?
                """,
                params
            )
            await self._connection.commit()

        # Retrieve updated session
        return await self.get(session_id)

    async def update_context(
        self,
        session_id: str,
        conversation_history: dict
    ) -> None:
        """
        Update session conversation context.

        Stores conversation history for session resumption.
        Called by Claude integration (Phase 3) during active conversations.

        Args:
            session_id: Session UUID
            conversation_history: Dict containing conversation turns

        Raises:
            SessionNotFoundError: If session doesn't exist
        """
        session = await self.get(session_id)
        if not session:
            raise SessionNotFoundError(f"Session {session_id} not found")

        # Update context JSON blob with conversation history
        updated_context = {**session.context, "conversation_history": conversation_history}

        async with self._lock:
            await self._connection.execute(
                "UPDATE sessions SET context = ? WHERE id = ?",
                (json.dumps(updated_context), session_id)
            )
            await self._connection.commit()

        self._log.info(
            "session_context_updated",
            session_id=session_id,
            history_length=len(conversation_history)
        )

    async def track_activity(
        self,
        session_id: str,
        activity_type: str,
        details: dict
    ) -> Session:
        """
        Track Claude activity in session context.

        Args:
            session_id: Session UUID
            activity_type: Type of activity (e.g., "command_executed", "response_generated")
            details: Activity details to store

        Returns:
            Updated session

        Raises:
            SessionNotFoundError: If session doesn't exist
        """
        session = await self.get(session_id)
        if not session:
            raise SessionNotFoundError(f"Session {session_id} not found")

        # Add activity to context
        context = session.context.copy()
        if "activity_log" not in context:
            context["activity_log"] = []

        context["activity_log"].append({
            "timestamp": datetime.now(UTC).isoformat(),
            "type": activity_type,
            "details": details
        })

        # Keep only last 10 activities (prevent unbounded growth)
        context["activity_log"] = context["activity_log"][-10:]

        # Update session
        return await self.update(session_id, context=context)

    async def generate_catchup_summary(self, session_id: str) -> str:
        """
        Generate plain-English summary of Claude's offline work from activity_log.
        Called after reconnection before draining message buffer.

        Returns summary like:
        "While you were away, Claude completed 5 operations:
        - Read config.json (247 lines)
        - Modified src/main.py (23 lines changed)
        - Ran tests (12 passed)
        - Created docs/README.md (50 lines)
        - Committed changes to git

        Ready to continue!"

        Args:
            session_id: Session UUID

        Returns:
            Formatted summary string

        Raises:
            SessionNotFoundError: If session doesn't exist
        """
        session = await self.get(session_id)
        if not session:
            return "Session not found"

        activity_log = session.context.get("activity_log", [])
        if not activity_log:
            return "No activity while disconnected"

        # Format summary
        count = len(activity_log)
        summary_lines = [f"While you were away, Claude completed {count} operation{'s' if count != 1 else ''}:"]

        for activity in activity_log:
            # activity: {"timestamp": str, "type": str, "details": dict}
            activity_type = activity.get("type", "unknown")
            details = activity.get("details", {})

            # Format based on activity type
            if activity_type == "tool_call":
                tool = details.get("tool", "unknown")
                target = details.get("target", "")
                summary_lines.append(f"- {tool} {target}")
            elif activity_type == "command_executed":
                command = details.get("command", "unknown")
                summary_lines.append(f"- Executed: {command}")
            else:
                summary_lines.append(f"- {activity_type}")

        summary_lines.append("\nReady to continue!")

        # Clear activity log after generating summary
        await self.update_context(session_id, {"activity_log": []})

        return "\n".join(summary_lines)

    def _row_to_session(self, row: tuple) -> Session:
        """
        Convert database row to Session object.

        Args:
            row: Tuple from SELECT query

        Returns:
            Session object
        """
        return Session(
            id=row[0],
            project_path=row[1],
            thread_id=row[2],
            status=SessionStatus(row[3]),
            context=json.loads(row[4]) if row[4] else {},
            created_at=datetime.fromisoformat(row[5]),
            updated_at=datetime.fromisoformat(row[6]),
        )
