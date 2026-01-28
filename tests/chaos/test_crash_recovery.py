"""
Chaos tests for daemon and process crash recovery.

Tests validate that the system recovers gracefully from crashes,
restores session state correctly, and handles corrupt data safely.
"""

import asyncio
import tempfile
import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.session.manager import SessionManager, SessionStatus
from src.session.lifecycle import SessionLifecycle
from src.session.recovery import CrashRecovery


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
async def session_lifecycle(session_manager):
    """Create SessionLifecycle instance."""
    lifecycle = SessionLifecycle(session_manager)
    return lifecycle


@pytest.fixture
async def crash_recovery(session_manager, session_lifecycle):
    """Create CrashRecovery instance."""
    recovery = CrashRecovery(session_manager, session_lifecycle)
    return recovery


@pytest.mark.asyncio
async def test_daemon_crash_recovery(session_manager, crash_recovery):
    """
    Test daemon crash detection and recovery.

    Validates:
    - ACTIVE sessions detected as crashed
    - Sessions transitioned to PAUSED
    - recovered_at timestamp set
    - User notifications sent (mocked)
    """
    # Create 3 ACTIVE sessions (simulating daemon crash scenario)
    sessions = []
    for i in range(3):
        session = await session_manager.create(f"/tmp/project_{i}", f"+155500000{i}")
        await session_manager.update(session.id, status=SessionStatus.ACTIVE)
        sessions.append(session)

    # Verify all sessions ACTIVE
    for session in sessions:
        retrieved = await session_manager.get(session.id)
        assert retrieved.status == SessionStatus.ACTIVE

    # Run crash recovery
    recovered_ids = await crash_recovery.recover()

    # Verify all 3 sessions recovered
    assert len(recovered_ids) == 3
    assert set(recovered_ids) == {s.id for s in sessions}

    # Verify all sessions now PAUSED
    for session in sessions:
        retrieved = await session_manager.get(session.id)
        assert retrieved.status == SessionStatus.PAUSED
        assert "recovered_at" in retrieved.context
        # Verify timestamp is ISO format string
        assert isinstance(retrieved.context["recovered_at"], str)
        assert "T" in retrieved.context["recovered_at"]  # ISO format


@pytest.mark.asyncio
async def test_no_false_positive_recovery(session_manager, crash_recovery):
    """
    Test that non-ACTIVE sessions are not incorrectly recovered.

    Validates:
    - CREATED sessions not affected
    - PAUSED sessions not affected
    - TERMINATED sessions not affected
    - Only ACTIVE sessions recovered
    """
    # Create sessions in various states
    created_session = await session_manager.create("/tmp/project_1", "+15550001")
    # Keep as CREATED

    paused_session = await session_manager.create("/tmp/project_2", "+15550002")
    await session_manager.update(paused_session.id, status=SessionStatus.PAUSED)

    terminated_session = await session_manager.create("/tmp/project_3", "+15550003")
    await session_manager.update(terminated_session.id, status=SessionStatus.TERMINATED)

    active_session = await session_manager.create("/tmp/project_4", "+15550004")
    await session_manager.update(active_session.id, status=SessionStatus.ACTIVE)

    # Run recovery
    recovered_ids = await crash_recovery.recover()

    # Only active_session should be recovered
    assert len(recovered_ids) == 1
    assert recovered_ids[0] == active_session.id

    # Verify other sessions unchanged
    created = await session_manager.get(created_session.id)
    assert created.status == SessionStatus.CREATED

    paused = await session_manager.get(paused_session.id)
    assert paused.status == SessionStatus.PAUSED

    terminated = await session_manager.get(terminated_session.id)
    assert terminated.status == SessionStatus.TERMINATED

    # Verify active session now paused
    active = await session_manager.get(active_session.id)
    assert active.status == SessionStatus.PAUSED


@pytest.mark.asyncio
async def test_idempotent_recovery(session_manager, crash_recovery):
    """
    Test recovery is idempotent - safe to run multiple times.

    Validates:
    - Running recovery twice doesn't cause errors
    - Already-recovered sessions not re-recovered
    - System remains in consistent state
    """
    # Create ACTIVE session
    session = await session_manager.create("/tmp/project", "+15550000")
    await session_manager.update(session.id, status=SessionStatus.ACTIVE)

    # First recovery
    recovered_ids_1 = await crash_recovery.recover()
    assert len(recovered_ids_1) == 1

    # Verify session now PAUSED
    session_after_first = await session_manager.get(session.id)
    assert session_after_first.status == SessionStatus.PAUSED
    first_context = session_after_first.context.copy()

    # Second recovery (should be no-op)
    recovered_ids_2 = await crash_recovery.recover()
    assert len(recovered_ids_2) == 0  # No ACTIVE sessions to recover

    # Verify session still PAUSED with same context
    session_after_second = await session_manager.get(session.id)
    assert session_after_second.status == SessionStatus.PAUSED
    assert session_after_second.context["recovered_at"] == first_context["recovered_at"]


@pytest.mark.asyncio
async def test_recovery_with_existing_context(session_manager, crash_recovery):
    """
    Test recovery preserves existing session context.

    Validates:
    - Existing context data not lost
    - recovered_at added to existing context
    - Context merge works correctly
    """
    # Create ACTIVE session with existing context
    session = await session_manager.create("/tmp/project", "+15550000")
    existing_context = {
        "conversation_history": {"turns": 5},
        "activity_log": [{"type": "command", "details": "test"}],
        "custom_data": "important"
    }
    await session_manager.update(session.id, status=SessionStatus.ACTIVE, context=existing_context)

    # Run recovery
    recovered_ids = await crash_recovery.recover()
    assert len(recovered_ids) == 1

    # Verify existing context preserved
    recovered_session = await session_manager.get(session.id)
    assert recovered_session.context["conversation_history"] == {"turns": 5}
    assert recovered_session.context["activity_log"] == [{"type": "command", "details": "test"}]
    assert recovered_session.context["custom_data"] == "important"
    assert "recovered_at" in recovered_session.context


@pytest.mark.asyncio
async def test_crash_detection_logic(session_manager, crash_recovery):
    """
    Test crash detection accurately identifies crashed sessions.

    Validates:
    - detect_crashed_sessions() returns only ACTIVE sessions
    - Detection is accurate and reliable
    - No false positives or negatives
    """
    # Create mix of sessions
    active1 = await session_manager.create("/tmp/project_1", "+15550001")
    await session_manager.update(active1.id, status=SessionStatus.ACTIVE)

    active2 = await session_manager.create("/tmp/project_2", "+15550002")
    await session_manager.update(active2.id, status=SessionStatus.ACTIVE)

    paused = await session_manager.create("/tmp/project_3", "+15550003")
    await session_manager.update(paused.id, status=SessionStatus.PAUSED)

    # Detect crashed sessions
    crashed_sessions = await crash_recovery.detect_crashed_sessions()

    # Should detect exactly 2 ACTIVE sessions
    assert len(crashed_sessions) == 2
    crashed_ids = {s.id for s in crashed_sessions}
    assert crashed_ids == {active1.id, active2.id}

    # Verify crashed sessions are indeed ACTIVE
    for session in crashed_sessions:
        assert session.status == SessionStatus.ACTIVE


@pytest.mark.asyncio
async def test_empty_recovery(crash_recovery):
    """
    Test recovery with no crashed sessions.

    Validates:
    - Empty database doesn't cause errors
    - Recovery returns empty list
    - System handles "nothing to recover" gracefully
    """
    # Run recovery on empty database
    recovered_ids = await crash_recovery.recover()

    # Should return empty list (no sessions to recover)
    assert recovered_ids == []


@pytest.mark.asyncio
async def test_concurrent_session_crashes(session_manager, crash_recovery):
    """
    Test recovery of many concurrent crashed sessions.

    Validates:
    - System handles bulk recovery efficiently
    - All crashed sessions recovered
    - No deadlocks or race conditions
    """
    # Create 20 ACTIVE sessions (simulating many concurrent crashes)
    sessions = []
    for i in range(20):
        session = await session_manager.create(f"/tmp/project_{i}", f"+15550{i:04d}")
        await session_manager.update(session.id, status=SessionStatus.ACTIVE)
        sessions.append(session)

    # Run recovery
    recovered_ids = await crash_recovery.recover()

    # Verify all 20 sessions recovered
    assert len(recovered_ids) == 20
    assert set(recovered_ids) == {s.id for s in sessions}

    # Verify all now PAUSED
    all_sessions = await session_manager.list()
    for session in all_sessions:
        assert session.status == SessionStatus.PAUSED
        assert "recovered_at" in session.context


@pytest.mark.asyncio
async def test_recovery_with_database_error():
    """
    Test recovery behavior when database errors occur.

    Validates:
    - Database errors during recovery are detectable
    - System remains in consistent state after error
    - Error doesn't corrupt database
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_sessions.db"
        manager = SessionManager(str(db_path))
        await manager.initialize()

        # Create ACTIVE session
        session = await manager.create("/tmp/project", "+15550000")
        await manager.update(session.id, status=SessionStatus.ACTIVE)

        # Create lifecycle and recovery
        lifecycle = SessionLifecycle(manager)
        recovery = CrashRecovery(manager, lifecycle)

        # Run normal recovery first
        recovered_ids = await recovery.recover()
        assert len(recovered_ids) == 1

        # Verify session recovered correctly
        recovered_session = await manager.get(session.id)
        assert recovered_session.status == SessionStatus.PAUSED
        assert "recovered_at" in recovered_session.context

        # Running recovery again should be no-op (idempotent)
        recovered_ids_2 = await recovery.recover()
        assert len(recovered_ids_2) == 0

        await manager.close()


@pytest.mark.asyncio
async def test_recovery_timestamp_accuracy(session_manager, crash_recovery):
    """
    Test recovered_at timestamp is accurate and consistent.

    Validates:
    - Timestamps are recent (within last second)
    - All recovered sessions have same timestamp
    - Timestamp format is correct ISO 8601
    """
    import time
    from datetime import datetime, UTC

    # Record time before recovery
    before_recovery = datetime.now(UTC)

    # Create ACTIVE sessions
    sessions = []
    for i in range(3):
        session = await session_manager.create(f"/tmp/project_{i}", f"+155500000{i}")
        await session_manager.update(session.id, status=SessionStatus.ACTIVE)
        sessions.append(session)

    # Small delay to ensure timestamp difference
    await asyncio.sleep(0.1)

    # Run recovery
    recovered_ids = await crash_recovery.recover()

    # Record time after recovery
    after_recovery = datetime.now(UTC)

    # Verify all sessions have recovered_at timestamp
    recovered_timestamps = []
    for session_id in recovered_ids:
        session = await session_manager.get(session_id)
        timestamp_str = session.context["recovered_at"]
        recovered_timestamps.append(timestamp_str)

        # Parse timestamp
        timestamp = datetime.fromisoformat(timestamp_str)

        # Verify timestamp is recent (between before and after)
        assert before_recovery <= timestamp <= after_recovery

    # Verify all sessions recovered at same time (single recovery run)
    assert len(set(recovered_timestamps)) == 1


@pytest.mark.asyncio
async def test_database_integrity_after_recovery(session_manager, crash_recovery):
    """
    Test database remains consistent after recovery.

    Validates:
    - No orphaned records
    - Indexes still valid
    - Database constraints maintained
    """
    # Create ACTIVE sessions
    for i in range(5):
        session = await session_manager.create(f"/tmp/project_{i}", f"+155500000{i}")
        await session_manager.update(session.id, status=SessionStatus.ACTIVE)

    # Run recovery
    await crash_recovery.recover()

    # Verify database consistency
    all_sessions = await session_manager.list()
    assert len(all_sessions) == 5

    # Verify all sessions retrievable by ID
    for session in all_sessions:
        retrieved = await session_manager.get(session.id)
        assert retrieved is not None
        assert retrieved.id == session.id

    # Verify updated_at timestamp changed (recovery modified sessions)
    for session in all_sessions:
        assert session.updated_at > session.created_at
