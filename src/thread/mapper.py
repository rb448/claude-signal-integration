"""
Thread-to-Project Mapper - Persistent thread-project associations.

GREEN Phase: Implementation to make tests pass.
"""

import asyncio
import aiosqlite
import structlog
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional

logger = structlog.get_logger(__name__)


class ThreadMappingError(Exception):
    """Raised when thread mapping operation fails."""
    pass


@dataclass
class ThreadMapping:
    """
    Thread-to-project mapping data model.

    Represents a persistent association between a Signal thread and a project directory.
    """
    thread_id: str
    project_path: str
    created_at: datetime
    updated_at: datetime


class ThreadMapper:
    """
    Manages thread-to-project mappings with SQLite persistence.

    Provides CRUD operations for bijective thread-project associations that survive process restarts.
    Uses WAL mode for concurrent access safety.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize ThreadMapper.

        Args:
            db_path: Path to SQLite database. Defaults to ~/.claude-signal/threads.db
        """
        if db_path is None:
            db_path = str(Path.home() / ".claude-signal" / "threads.db")

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

    async def map(self, thread_id: str, project_path: str) -> ThreadMapping:
        """
        Create thread-to-project mapping.

        Args:
            thread_id: Signal thread identifier
            project_path: Local project directory path

        Returns:
            ThreadMapping with timestamps

        Raises:
            ThreadMappingError: If path doesn't exist, thread already mapped, or path already mapped
        """
        # Validate: Path must exist
        if not Path(project_path).exists():
            raise ThreadMappingError(f"Path does not exist: {project_path}")

        # Validate: Thread not already mapped
        existing_by_thread = await self.get_by_thread(thread_id)
        if existing_by_thread is not None:
            raise ThreadMappingError(f"Thread already mapped to {existing_by_thread.project_path}")

        # Validate: Path not already mapped
        existing_by_path = await self.get_by_path(project_path)
        if existing_by_path is not None:
            raise ThreadMappingError(f"Path already mapped to thread {existing_by_path.thread_id}")

        # Create mapping
        now = datetime.now(UTC)

        async with self._lock:
            await self._connection.execute(
                """
                INSERT INTO thread_mappings (thread_id, project_path, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    thread_id,
                    project_path,
                    now.isoformat(),
                    now.isoformat(),
                )
            )
            await self._connection.commit()

        self._log.info(
            "thread_mapped",
            thread_id=thread_id,
            project_path=project_path
        )

        return ThreadMapping(
            thread_id=thread_id,
            project_path=project_path,
            created_at=now,
            updated_at=now,
        )

    async def get_by_thread(self, thread_id: str) -> Optional[ThreadMapping]:
        """
        Retrieve mapping by thread_id.

        Args:
            thread_id: Signal thread identifier

        Returns:
            ThreadMapping if exists, None otherwise
        """
        async with self._lock:
            cursor = await self._connection.execute(
                """
                SELECT thread_id, project_path, created_at, updated_at
                FROM thread_mappings
                WHERE thread_id = ?
                """,
                (thread_id,)
            )
            row = await cursor.fetchone()

        if row is None:
            return None

        return self._row_to_mapping(row)

    async def get_by_path(self, project_path: str) -> Optional[ThreadMapping]:
        """
        Retrieve mapping by project_path (reverse lookup).

        Args:
            project_path: Local project directory path

        Returns:
            ThreadMapping if exists, None otherwise
        """
        async with self._lock:
            cursor = await self._connection.execute(
                """
                SELECT thread_id, project_path, created_at, updated_at
                FROM thread_mappings
                WHERE project_path = ?
                """,
                (project_path,)
            )
            row = await cursor.fetchone()

        if row is None:
            return None

        return self._row_to_mapping(row)

    async def list_all(self) -> list[ThreadMapping]:
        """
        List all mappings ordered by created_at DESC.

        Returns:
            List of mappings, newest first
        """
        async with self._lock:
            cursor = await self._connection.execute(
                """
                SELECT thread_id, project_path, created_at, updated_at
                FROM thread_mappings
                ORDER BY created_at DESC
                """
            )
            rows = await cursor.fetchall()

        return [self._row_to_mapping(row) for row in rows]

    async def unmap(self, thread_id: str) -> None:
        """
        Remove thread-to-project mapping.

        Idempotent: Does not raise error if thread not mapped.

        Args:
            thread_id: Signal thread identifier
        """
        async with self._lock:
            await self._connection.execute(
                """
                DELETE FROM thread_mappings
                WHERE thread_id = ?
                """,
                (thread_id,)
            )
            await self._connection.commit()

        self._log.info("thread_unmapped", thread_id=thread_id)

    def _row_to_mapping(self, row: tuple) -> ThreadMapping:
        """
        Convert database row to ThreadMapping object.

        Args:
            row: Tuple from SELECT query

        Returns:
            ThreadMapping object
        """
        return ThreadMapping(
            thread_id=row[0],
            project_path=row[1],
            created_at=datetime.fromisoformat(row[2]),
            updated_at=datetime.fromisoformat(row[3]),
        )
