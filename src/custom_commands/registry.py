"""Registry for custom Claude Code commands with SQLite persistence."""
import json
import aiosqlite
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional


class CustomCommandRegistry:
    """Persistent storage for custom Claude Code commands.

    Stores command metadata in SQLite with WAL mode for concurrent access.
    Follows Phase 2/4 patterns: async initialization, UTC timestamps, idempotent operations.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize registry with database path.

        Args:
            db_path: Path to SQLite database. Defaults to Application Support directory.
        """
        if db_path is None:
            app_support = Path.home() / "Library" / "Application Support" / "claude-signal-bot"
            app_support.mkdir(parents=True, exist_ok=True)
            db_path = app_support / "custom_commands.db"

        self.db_path = db_path
        self._initialized = False

    async def initialize(self):
        """Initialize database schema with WAL mode for concurrent access."""
        if self._initialized:
            return

        async with aiosqlite.connect(self.db_path) as db:
            # Enable WAL mode for concurrent reads during writes (Phase 2 pattern)
            await db.execute("PRAGMA journal_mode=WAL")

            # Create commands table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS commands (
                    name TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            await db.commit()

        self._initialized = True

    async def add_command(self, name: str, file_path: str, metadata: dict):
        """Add or update a command in the registry (idempotent).

        Args:
            name: Command name (unique identifier)
            file_path: Path to command file
            metadata: Command metadata (description, parameters, etc.)
        """
        metadata_json = json.dumps(metadata)
        updated_at = datetime.now(UTC).isoformat()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO commands (name, file_path, metadata, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    file_path=excluded.file_path,
                    metadata=excluded.metadata,
                    updated_at=excluded.updated_at
            """, (name, file_path, metadata_json, updated_at))
            await db.commit()

    async def get_command(self, name: str) -> Optional[dict]:
        """Get a command by name.

        Args:
            name: Command name

        Returns:
            Command dict with name, file_path, metadata, updated_at, or None if not found
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT name, file_path, metadata, updated_at FROM commands WHERE name = ?",
                (name,)
            ) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    return None

                return {
                    "name": row["name"],
                    "file_path": row["file_path"],
                    "metadata": json.loads(row["metadata"]),
                    "updated_at": row["updated_at"]
                }

    async def list_commands(self) -> list[dict]:
        """List all commands in the registry.

        Returns:
            List of command dicts with name, file_path, metadata, updated_at
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT name, file_path, metadata, updated_at FROM commands ORDER BY name"
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                    {
                        "name": row["name"],
                        "file_path": row["file_path"],
                        "metadata": json.loads(row["metadata"]),
                        "updated_at": row["updated_at"]
                    }
                    for row in rows
                ]

    async def update_command(self, name: str, metadata: dict):
        """Update command metadata.

        Only updates if command exists (does not create new commands).

        Args:
            name: Command name
            metadata: New metadata
        """
        metadata_json = json.dumps(metadata)
        updated_at = datetime.now(UTC).isoformat()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE commands
                SET metadata = ?, updated_at = ?
                WHERE name = ?
            """, (metadata_json, updated_at, name))
            await db.commit()

    async def remove_command(self, name: str):
        """Remove a command from the registry (idempotent).

        Args:
            name: Command name
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM commands WHERE name = ?", (name,))
            await db.commit()

    async def command_exists(self, name: str) -> bool:
        """Check if a command exists in the registry.

        Args:
            name: Command name

        Returns:
            True if command exists, False otherwise
        """
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT 1 FROM commands WHERE name = ? LIMIT 1",
                (name,)
            ) as cursor:
                row = await cursor.fetchone()
                return row is not None
