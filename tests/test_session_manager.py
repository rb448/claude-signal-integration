"""
Tests for Session Persistence Layer.

Following TDD methodology: These tests written BEFORE implementation.
Expected to fail initially (RED phase).
"""

import pytest
import asyncio
import os
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from uuid import UUID

# Import will fail initially - expected in RED phase
from src.session.manager import SessionManager, Session, SessionStatus


class TestSessionManager:
    """Test suite for SessionManager CRUD operations."""

    @pytest.fixture
    async def temp_db_path(self):
        """Create temporary database path for isolated tests."""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "test_sessions.db"
        yield db_path
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    async def manager(self, temp_db_path):
        """Create SessionManager instance with temporary database."""
        mgr = SessionManager(db_path=str(temp_db_path))
        await mgr.initialize()
        yield mgr
        await mgr.close()

    @pytest.mark.asyncio
    async def test_create_session_returns_session_with_uuid(self, manager):
        """
        RED: Test create() returns Session with valid UUID.

        Expected behavior:
        - Session has valid UUID4 string
        - Status is CREATED
        - Timestamps are set
        - project_path and thread_id match input
        """
        session = await manager.create(
            project_path="/test/project",
            thread_id="thread-123"
        )

        # Verify Session object returned
        assert isinstance(session, Session)

        # Verify UUID is valid
        assert session.id is not None
        UUID(session.id)  # Should not raise ValueError

        # Verify initial status
        assert session.status == SessionStatus.CREATED

        # Verify fields match input
        assert session.project_path == "/test/project"
        assert session.thread_id == "thread-123"

        # Verify timestamps
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.updated_at, datetime)
        assert session.created_at == session.updated_at

    @pytest.mark.asyncio
    async def test_create_session_persists_to_database(self, manager):
        """
        RED: Test created session persists to database.

        Expected behavior:
        - Session can be retrieved after creation
        - Retrieved session matches created session
        """
        created = await manager.create(
            project_path="/test/project",
            thread_id="thread-456"
        )

        # Retrieve from database
        retrieved = await manager.get(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.project_path == created.project_path
        assert retrieved.thread_id == created.thread_id
        assert retrieved.status == created.status

    @pytest.mark.asyncio
    async def test_get_returns_none_for_missing_session(self, manager):
        """
        RED: Test get() returns None for non-existent session.

        Expected behavior:
        - No exception thrown
        - Returns None cleanly
        """
        result = await manager.get("non-existent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_returns_all_sessions_ordered_by_created_desc(self, manager):
        """
        RED: Test list() returns all sessions in descending created_at order.

        Expected behavior:
        - Returns list of all sessions
        - Ordered by created_at DESC (newest first)
        """
        # Create multiple sessions with slight delays
        session1 = await manager.create("/project1", "thread1")
        await asyncio.sleep(0.01)  # Ensure different timestamps
        session2 = await manager.create("/project2", "thread2")
        await asyncio.sleep(0.01)
        session3 = await manager.create("/project3", "thread3")

        # List all sessions
        sessions = await manager.list()

        assert len(sessions) == 3
        # Newest first
        assert sessions[0].id == session3.id
        assert sessions[1].id == session2.id
        assert sessions[2].id == session1.id

    @pytest.mark.asyncio
    async def test_update_changes_status_and_context(self, manager):
        """
        RED: Test update() modifies session status and context.

        Expected behavior:
        - Status changes to new value
        - Context JSON blob updates
        - updated_at timestamp changes
        """
        # Create initial session
        session = await manager.create("/project", "thread")
        original_updated_at = session.updated_at

        # Small delay to ensure timestamp difference
        await asyncio.sleep(0.01)

        # Update session
        context = {"messages": [{"role": "user", "content": "hello"}]}
        updated = await manager.update(
            session.id,
            status=SessionStatus.ACTIVE,
            context=context
        )

        assert updated.status == SessionStatus.ACTIVE
        assert updated.context == context
        assert updated.updated_at > original_updated_at

        # Verify persistence
        retrieved = await manager.get(session.id)
        assert retrieved.status == SessionStatus.ACTIVE
        assert retrieved.context == context

    @pytest.mark.asyncio
    async def test_sessions_persist_across_manager_restarts(self, temp_db_path):
        """
        RED: Test sessions survive SessionManager restart.

        Expected behavior:
        - Create session with manager1
        - Close manager1
        - Open manager2 with same database
        - Session still retrievable
        """
        # Create session with first manager
        manager1 = SessionManager(db_path=str(temp_db_path))
        await manager1.initialize()

        session = await manager1.create("/project", "thread")
        session_id = session.id

        await manager1.close()

        # Open new manager with same database
        manager2 = SessionManager(db_path=str(temp_db_path))
        await manager2.initialize()

        # Retrieve session
        retrieved = await manager2.get(session_id)

        assert retrieved is not None
        assert retrieved.id == session_id
        assert retrieved.project_path == "/project"

        await manager2.close()

    @pytest.mark.asyncio
    async def test_concurrent_creates_generate_unique_ids(self, manager):
        """
        RED: Test concurrent create() calls generate unique IDs.

        Expected behavior:
        - Multiple concurrent creates don't collide
        - All sessions have unique IDs
        """
        # Create 10 sessions concurrently
        tasks = [
            manager.create(f"/project{i}", f"thread{i}")
            for i in range(10)
        ]
        sessions = await asyncio.gather(*tasks)

        # Verify all IDs are unique
        ids = [s.id for s in sessions]
        assert len(ids) == len(set(ids))  # No duplicates

    @pytest.mark.asyncio
    async def test_empty_context_handled_correctly(self, manager):
        """
        RED: Test session with empty context dict.

        Expected behavior:
        - Empty dict stored and retrieved correctly
        - No serialization errors
        """
        session = await manager.create("/project", "thread")

        # Update with empty context
        updated = await manager.update(
            session.id,
            status=SessionStatus.ACTIVE,
            context={}
        )

        assert updated.context == {}

        # Verify retrieval
        retrieved = await manager.get(session.id)
        assert retrieved.context == {}
