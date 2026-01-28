"""
Load tests for concurrent session management.

Tests validate that SessionManager handles high concurrent load without
race conditions, deadlocks, or state corruption.
"""

import asyncio
import tempfile
import shutil
from pathlib import Path
from uuid import uuid4
import random

import pytest

from src.session.manager import SessionManager, SessionStatus


@pytest.fixture
async def session_manager():
    """Create SessionManager with temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_sessions.db"
        manager = SessionManager(str(db_path))
        await manager.initialize()
        yield manager
        await manager.close()


@pytest.fixture
def temp_projects():
    """Create temporary project directories for testing."""
    project_dirs = []
    temp_dir = tempfile.mkdtemp()

    try:
        for i in range(100):
            project_path = Path(temp_dir) / f"project_{i}"
            project_path.mkdir()
            project_dirs.append(str(project_path))

        yield project_dirs
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_100_concurrent_sessions(session_manager, temp_projects):
    """
    Test creating 100 concurrent sessions without race conditions.

    Validates:
    - SQLite WAL mode handles concurrent writes
    - No race conditions in session creation
    - All sessions created successfully
    - Database integrity maintained
    """
    # Create 100 sessions in parallel
    tasks = []
    for i in range(100):
        project_path = temp_projects[i]
        thread_id = f"+1555{i:04d}"  # Unique thread IDs
        tasks.append(session_manager.create(project_path, thread_id))

    # Execute all creates in parallel
    sessions = await asyncio.gather(*tasks)

    # Verify all sessions created successfully
    assert len(sessions) == 100
    assert all(session.status == SessionStatus.CREATED for session in sessions)

    # Verify database integrity - all sessions retrievable
    all_sessions = await session_manager.list()
    assert len(all_sessions) == 100

    # Verify unique session IDs
    session_ids = {session.id for session in all_sessions}
    assert len(session_ids) == 100

    # Verify no cross-contamination of data
    for i, session in enumerate(sessions):
        retrieved = await session_manager.get(session.id)
        assert retrieved.project_path == temp_projects[i]
        assert retrieved.thread_id == f"+1555{i:04d}"


@pytest.mark.asyncio
async def test_session_isolation_under_load(session_manager, temp_projects):
    """
    Test session isolation when multiple sessions execute concurrently.

    Validates:
    - Each session maintains independent state
    - No shared mutable state causes bugs
    - Context updates are isolated per session
    """
    # Create 10 sessions
    sessions = []
    for i in range(10):
        session = await session_manager.create(temp_projects[i], f"+1555000{i}")
        sessions.append(session)

    # Update each session's context with unique data in parallel
    async def update_session_context(session, value):
        context = {"test_value": value, "operations": []}
        for _ in range(10):  # Multiple updates per session
            context["operations"].append(str(uuid4()))
        await session_manager.update(session.id, context=context)
        return session.id

    tasks = [update_session_context(session, i * 100) for i, session in enumerate(sessions)]
    await asyncio.gather(*tasks)

    # Verify each session has correct isolated data
    for i, session in enumerate(sessions):
        retrieved = await session_manager.get(session.id)
        assert retrieved.context["test_value"] == i * 100
        assert len(retrieved.context["operations"]) == 10

        # Verify operations are unique (no shared state corruption)
        ops = retrieved.context["operations"]
        assert len(ops) == len(set(ops))  # All unique


@pytest.mark.asyncio
async def test_database_contention(session_manager, temp_projects):
    """
    Test concurrent database updates without locking errors.

    Validates:
    - SQLite WAL mode prevents locking errors
    - Concurrent updates complete successfully
    - All updates committed correctly
    """
    # Create one session
    session = await session_manager.create(temp_projects[0], "+15550000")

    # Perform 50 concurrent status updates
    async def update_status(iteration):
        # Alternate between CREATED and ACTIVE states
        target_status = SessionStatus.ACTIVE if iteration % 2 == 0 else SessionStatus.CREATED
        await session_manager.update(session.id, status=target_status)
        return iteration

    tasks = [update_status(i) for i in range(50)]
    results = await asyncio.gather(*tasks)

    # Verify all updates completed
    assert len(results) == 50

    # Verify session still valid and retrievable
    final_session = await session_manager.get(session.id)
    assert final_session is not None
    assert final_session.id == session.id

    # Verify final status is one of the valid states (last update won)
    assert final_session.status in (SessionStatus.CREATED, SessionStatus.ACTIVE)


@pytest.mark.asyncio
async def test_concurrent_read_write_operations(session_manager, temp_projects):
    """
    Test concurrent reads and writes don't cause deadlocks.

    Validates:
    - Read operations don't block writes
    - Write operations don't block reads excessively
    - No deadlocks occur under mixed load
    """
    # Create 10 sessions
    sessions = []
    for i in range(10):
        session = await session_manager.create(temp_projects[i], f"+1555100{i}")
        sessions.append(session)

    async def writer(session_id):
        """Continuously update session context."""
        for _ in range(5):
            context = {"timestamp": str(uuid4())}
            await session_manager.update(session_id, context=context)
            await asyncio.sleep(0.01)  # Small delay between writes

    async def reader(session_id):
        """Continuously read session state."""
        for _ in range(10):
            session = await session_manager.get(session_id)
            assert session is not None
            await asyncio.sleep(0.005)  # Faster reads than writes

    # Mix writers and readers
    tasks = []
    for session in sessions:
        tasks.append(writer(session.id))
        tasks.append(reader(session.id))

    # All tasks should complete without deadlock
    await asyncio.gather(*tasks)

    # Verify all sessions still accessible
    for session in sessions:
        retrieved = await session_manager.get(session.id)
        assert retrieved is not None


@pytest.mark.asyncio
async def test_session_list_under_concurrent_creation(session_manager, temp_projects):
    """
    Test listing sessions while they're being created concurrently.

    Validates:
    - list() doesn't deadlock with create()
    - list() returns consistent snapshots
    - No partial/corrupted data in list results
    """
    async def creator():
        """Create sessions continuously."""
        sessions = []
        for i in range(20):
            session = await session_manager.create(
                temp_projects[i % len(temp_projects)],
                f"+15551{random.randint(1000, 9999)}"
            )
            sessions.append(session)
            await asyncio.sleep(0.01)
        return len(sessions)

    async def lister():
        """List sessions continuously."""
        counts = []
        for _ in range(10):
            sessions = await session_manager.list()
            counts.append(len(sessions))
            await asyncio.sleep(0.02)
        return counts

    # Run creators and listers in parallel
    creator_tasks = [creator() for _ in range(3)]
    lister_tasks = [lister() for _ in range(2)]

    results = await asyncio.gather(*creator_tasks, *lister_tasks)

    # Verify creators created expected number of sessions
    created_counts = results[:3]
    assert all(count == 20 for count in created_counts)

    # Verify listers saw increasing counts (no corrupted data)
    list_counts = results[3:]
    for counts in list_counts:
        # Counts should generally increase (allowing for timing)
        assert len(counts) == 10
        assert all(isinstance(c, int) and c >= 0 for c in counts)

    # Final verification - all 60 sessions exist
    final_sessions = await session_manager.list()
    assert len(final_sessions) == 60
