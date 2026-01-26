"""
Crash Recovery Tests - RED Phase.

Tests for CrashRecovery that detects and recovers ACTIVE sessions on daemon restart.
These tests are written BEFORE implementation to follow TDD discipline.
"""

import pytest
from datetime import datetime, UTC
from pathlib import Path
import tempfile
import os

from src.session import SessionManager, SessionLifecycle, SessionStatus
from src.session.recovery import CrashRecovery


@pytest.fixture
async def temp_db():
    """Create temporary database for isolated testing."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name

    yield db_path

    # Cleanup
    try:
        os.unlink(db_path)
    except FileNotFoundError:
        pass


@pytest.fixture
async def session_manager(temp_db):
    """Create SessionManager with temporary database."""
    manager = SessionManager(db_path=temp_db)
    await manager.initialize()
    yield manager
    await manager.close()


@pytest.fixture
async def session_lifecycle(session_manager):
    """Create SessionLifecycle for transition operations."""
    return SessionLifecycle(session_manager)


@pytest.fixture
async def crash_recovery(session_manager, session_lifecycle):
    """Create CrashRecovery instance."""
    return CrashRecovery(session_manager, session_lifecycle)


@pytest.mark.asyncio
async def test_clean_startup_no_active_sessions(crash_recovery, session_manager):
    """
    Test clean startup with no ACTIVE sessions.

    When daemon starts and no sessions are ACTIVE,
    recovery should return empty list (no crash detected).
    """
    # Create sessions in non-ACTIVE states
    session1 = await session_manager.create(project_path="/proj1", thread_id="t1")
    session2 = await session_manager.create(project_path="/proj2", thread_id="t2")
    # Leave them in CREATED state

    # Run recovery
    recovered = await crash_recovery.recover()

    # Assert no recovery needed
    assert recovered == [], "Clean startup should not recover any sessions"


@pytest.mark.asyncio
async def test_crash_recovery_single_active_session(
    crash_recovery,
    session_manager,
    session_lifecycle
):
    """
    Test crash recovery with one ACTIVE session.

    When daemon crashed with session in ACTIVE state:
    - Session should transition to PAUSED
    - recovered_at timestamp should be added to context
    - Session ID should be in recovered list
    """
    # Create and activate session
    session = await session_manager.create(project_path="/proj1", thread_id="t1")
    await session_lifecycle.transition(session.id, SessionStatus.CREATED, SessionStatus.ACTIVE)

    # Simulate daemon crash and restart
    # (In reality, daemon process dies and restarts - session stays ACTIVE in DB)

    # Run recovery
    recovered = await crash_recovery.recover()

    # Assert session recovered
    assert session.id in recovered, "Session should be in recovered list"
    assert len(recovered) == 1, "Should recover exactly one session"

    # Verify status transitioned
    updated = await session_manager.get(session.id)
    assert updated.status == SessionStatus.PAUSED, "ACTIVE session should transition to PAUSED"

    # Verify recovered_at timestamp exists
    assert "recovered_at" in updated.context, "recovered_at timestamp should be added"
    assert isinstance(updated.context["recovered_at"], str), "recovered_at should be ISO datetime string"


@pytest.mark.asyncio
async def test_crash_recovery_multiple_active_sessions(
    crash_recovery,
    session_manager,
    session_lifecycle
):
    """
    Test crash recovery with multiple ACTIVE sessions.

    All ACTIVE sessions should transition to PAUSED.
    """
    # Create and activate multiple sessions
    sessions = []
    for i in range(3):
        session = await session_manager.create(
            project_path=f"/proj{i}",
            thread_id=f"t{i}"
        )
        await session_lifecycle.transition(
            session.id,
            SessionStatus.CREATED,
            SessionStatus.ACTIVE
        )
        sessions.append(session)

    # Run recovery
    recovered = await crash_recovery.recover()

    # Assert all sessions recovered
    assert len(recovered) == 3, "Should recover all 3 ACTIVE sessions"
    for session in sessions:
        assert session.id in recovered, f"Session {session.id} should be recovered"

    # Verify all transitioned to PAUSED
    for session in sessions:
        updated = await session_manager.get(session.id)
        assert updated.status == SessionStatus.PAUSED
        assert "recovered_at" in updated.context


@pytest.mark.asyncio
async def test_crash_recovery_mixed_statuses(
    crash_recovery,
    session_manager,
    session_lifecycle
):
    """
    Test crash recovery with mixed session statuses.

    Only ACTIVE sessions should be recovered.
    CREATED, PAUSED, TERMINATED should remain unchanged.
    """
    # Create sessions in different states
    created = await session_manager.create(project_path="/proj1", thread_id="t1")
    # Leave in CREATED

    paused = await session_manager.create(project_path="/proj2", thread_id="t2")
    await session_lifecycle.transition(paused.id, SessionStatus.CREATED, SessionStatus.ACTIVE)
    await session_lifecycle.transition(paused.id, SessionStatus.ACTIVE, SessionStatus.PAUSED)

    active = await session_manager.create(project_path="/proj3", thread_id="t3")
    await session_lifecycle.transition(active.id, SessionStatus.CREATED, SessionStatus.ACTIVE)

    terminated = await session_manager.create(project_path="/proj4", thread_id="t4")
    await session_lifecycle.transition(terminated.id, SessionStatus.CREATED, SessionStatus.TERMINATED)

    # Run recovery
    recovered = await crash_recovery.recover()

    # Assert only ACTIVE session recovered
    assert len(recovered) == 1, "Should only recover ACTIVE session"
    assert active.id in recovered

    # Verify statuses
    assert (await session_manager.get(created.id)).status == SessionStatus.CREATED
    assert (await session_manager.get(paused.id)).status == SessionStatus.PAUSED
    assert (await session_manager.get(active.id)).status == SessionStatus.PAUSED
    assert (await session_manager.get(terminated.id)).status == SessionStatus.TERMINATED


@pytest.mark.asyncio
async def test_recovered_at_timestamp_format(
    crash_recovery,
    session_manager,
    session_lifecycle
):
    """
    Test that recovered_at timestamp is valid ISO format.
    """
    # Create and activate session
    session = await session_manager.create(project_path="/proj1", thread_id="t1")
    await session_lifecycle.transition(session.id, SessionStatus.CREATED, SessionStatus.ACTIVE)

    # Run recovery
    before_recovery = datetime.now(UTC)
    await crash_recovery.recover()
    after_recovery = datetime.now(UTC)

    # Verify timestamp
    updated = await session_manager.get(session.id)
    recovered_at_str = updated.context["recovered_at"]
    recovered_at = datetime.fromisoformat(recovered_at_str)

    # Timestamp should be between before and after
    assert before_recovery <= recovered_at <= after_recovery


@pytest.mark.asyncio
async def test_recovery_is_idempotent(
    crash_recovery,
    session_manager,
    session_lifecycle
):
    """
    Test that running recovery twice doesn't re-recover sessions.

    After first recovery, sessions are PAUSED.
    Second recovery should find no ACTIVE sessions.
    """
    # Create and activate session
    session = await session_manager.create(project_path="/proj1", thread_id="t1")
    await session_lifecycle.transition(session.id, SessionStatus.CREATED, SessionStatus.ACTIVE)

    # First recovery
    recovered1 = await crash_recovery.recover()
    assert len(recovered1) == 1

    # Second recovery
    recovered2 = await crash_recovery.recover()
    assert recovered2 == [], "Second recovery should find no ACTIVE sessions"

    # Verify session still PAUSED
    updated = await session_manager.get(session.id)
    assert updated.status == SessionStatus.PAUSED


@pytest.mark.asyncio
async def test_detect_crashed_sessions_returns_active_sessions(
    crash_recovery,
    session_manager,
    session_lifecycle
):
    """
    Test that detect_crashed_sessions() finds ACTIVE sessions.
    """
    # Create mixed state sessions
    await session_manager.create(project_path="/proj1", thread_id="t1")  # CREATED

    active = await session_manager.create(project_path="/proj2", thread_id="t2")
    await session_lifecycle.transition(active.id, SessionStatus.CREATED, SessionStatus.ACTIVE)

    # Detect crashed sessions
    crashed = await crash_recovery.detect_crashed_sessions()

    # Should find the ACTIVE session
    assert len(crashed) == 1
    assert crashed[0].id == active.id
    assert crashed[0].status == SessionStatus.ACTIVE


@pytest.mark.asyncio
async def test_recovery_preserves_existing_context(
    crash_recovery,
    session_manager,
    session_lifecycle
):
    """
    Test that recovery preserves existing session context.

    If session has context data, it should not be lost during recovery.
    """
    # Create session with context
    session = await session_manager.create(project_path="/proj1", thread_id="t1")
    await session_manager.update(
        session.id,
        context={"user_data": "important", "task_id": "123"}
    )
    await session_lifecycle.transition(session.id, SessionStatus.CREATED, SessionStatus.ACTIVE)

    # Run recovery
    await crash_recovery.recover()

    # Verify context preserved
    updated = await session_manager.get(session.id)
    assert updated.context["user_data"] == "important"
    assert updated.context["task_id"] == "123"
    assert "recovered_at" in updated.context  # New field added
