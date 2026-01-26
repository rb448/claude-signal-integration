"""
Integration tests for full session workflow.

Tests the complete session lifecycle from creation to termination,
including crash recovery scenarios.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from src.session import SessionManager, SessionLifecycle, SessionStatus, CrashRecovery, SessionCommands
from src.claude import ClaudeProcess
from unittest.mock import AsyncMock, patch


@pytest.fixture
async def test_session_manager():
    """Create SessionManager with temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_sessions.db")
        manager = SessionManager(db_path=db_path)
        await manager.initialize()
        yield manager
        await manager.close()


@pytest.fixture
async def test_lifecycle(test_session_manager):
    """Create SessionLifecycle with test manager."""
    return SessionLifecycle(test_session_manager)


@pytest.fixture
async def test_crash_recovery(test_session_manager, test_lifecycle):
    """Create CrashRecovery with test components."""
    return CrashRecovery(test_session_manager, test_lifecycle)


@pytest.fixture
async def test_session_commands(test_session_manager, test_lifecycle):
    """Create SessionCommands with test components and mocked processes."""
    # Mock process factory
    def process_factory(session_id: str, project_path: str):
        process = AsyncMock(spec=ClaudeProcess)
        process.session_id = session_id
        process.project_path = project_path
        process.is_running = True
        return process

    return SessionCommands(test_session_manager, test_lifecycle, process_factory)


@pytest.fixture
def temp_project_dir():
    """Create temporary project directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


def extract_session_id(response: str) -> str:
    """Extract session ID from command response."""
    # Response format: "Started session {id} for {path}"
    # or "Resumed session {id}"
    words = response.split()
    for i, word in enumerate(words):
        if word == "session" and i + 1 < len(words):
            return words[i + 1]
    raise ValueError(f"Could not extract session ID from response: {response}")


@pytest.mark.asyncio
async def test_session_workflow_start_to_stop(test_session_commands, temp_project_dir):
    """Test complete session lifecycle: start -> list -> stop."""
    thread_id = "thread-test-1"

    # 1. Start session
    response = await test_session_commands.handle(thread_id, f"/session start {temp_project_dir}")
    assert "Started session" in response
    session_id = extract_session_id(response)

    # Verify session created
    session = await test_session_commands.manager.get(session_id)
    assert session is not None
    assert session.status == SessionStatus.ACTIVE
    assert session.project_path == temp_project_dir
    assert session.thread_id == thread_id

    # 2. List shows new session
    response = await test_session_commands.handle(thread_id, "/session list")
    assert session_id[:8] in response  # Truncated ID in list
    assert "ACTIVE" in response
    assert temp_project_dir in response or "tmp" in response  # Path might be truncated

    # 3. Stop session
    response = await test_session_commands.handle(thread_id, f"/session stop {session_id}")
    assert "Stopped session" in response
    assert session_id in response

    # 4. Verify session terminated
    session = await test_session_commands.manager.get(session_id)
    assert session.status == SessionStatus.TERMINATED

    # 5. List shows TERMINATED
    response = await test_session_commands.handle(thread_id, "/session list")
    assert "TERMINATED" in response


@pytest.mark.asyncio
async def test_session_workflow_pause_resume(test_session_commands, test_lifecycle, temp_project_dir):
    """Test session pause and resume workflow."""
    thread_id = "thread-test-2"

    # 1. Start session
    response = await test_session_commands.handle(thread_id, f"/session start {temp_project_dir}")
    session_id = extract_session_id(response)

    # 2. Manually pause session (simulating crash or manual pause)
    await test_lifecycle.transition(session_id, SessionStatus.ACTIVE, SessionStatus.PAUSED)

    # 3. Verify session is paused
    session = await test_session_commands.manager.get(session_id)
    assert session.status == SessionStatus.PAUSED

    # 4. Resume session
    response = await test_session_commands.handle(thread_id, f"/session resume {session_id}")
    assert "Resumed session" in response
    assert session_id in response

    # 5. Verify session is active again
    session = await test_session_commands.manager.get(session_id)
    assert session.status == SessionStatus.ACTIVE


@pytest.mark.asyncio
async def test_crash_recovery_workflow(test_session_manager, test_lifecycle, test_crash_recovery, temp_project_dir):
    """Test crash recovery detects and pauses ACTIVE sessions."""
    # 1. Create active session (simulating running session before crash)
    session = await test_session_manager.create(temp_project_dir, "thread-crash-test")
    await test_lifecycle.transition(session.id, SessionStatus.CREATED, SessionStatus.ACTIVE)

    # Verify session is ACTIVE
    session = await test_session_manager.get(session.id)
    assert session.status == SessionStatus.ACTIVE

    # 2. Simulate daemon restart with crash recovery
    recovered = await test_crash_recovery.recover()
    assert session.id in recovered
    assert len(recovered) == 1

    # 3. Verify session is now PAUSED
    session = await test_session_manager.get(session.id)
    assert session.status == SessionStatus.PAUSED

    # 4. Verify recovered_at timestamp in context
    assert "recovered_at" in session.context
    assert isinstance(session.context["recovered_at"], str)


@pytest.mark.asyncio
async def test_crash_recovery_multiple_sessions(test_session_manager, test_lifecycle, test_crash_recovery, temp_project_dir):
    """Test crash recovery handles multiple ACTIVE sessions."""
    # Create multiple sessions in different states
    session1 = await test_session_manager.create(temp_project_dir, "thread-1")
    await test_lifecycle.transition(session1.id, SessionStatus.CREATED, SessionStatus.ACTIVE)

    session2 = await test_session_manager.create(temp_project_dir, "thread-2")
    await test_lifecycle.transition(session2.id, SessionStatus.CREATED, SessionStatus.ACTIVE)

    session3 = await test_session_manager.create(temp_project_dir, "thread-3")
    # Leave session3 in CREATED state

    # Run crash recovery
    recovered = await test_crash_recovery.recover()

    # Should recover only ACTIVE sessions
    assert len(recovered) == 2
    assert session1.id in recovered
    assert session2.id in recovered
    assert session3.id not in recovered

    # Verify sessions are PAUSED
    session1 = await test_session_manager.get(session1.id)
    assert session1.status == SessionStatus.PAUSED

    session2 = await test_session_manager.get(session2.id)
    assert session2.status == SessionStatus.PAUSED

    # session3 should still be CREATED
    session3 = await test_session_manager.get(session3.id)
    assert session3.status == SessionStatus.CREATED


@pytest.mark.asyncio
async def test_multiple_sessions_concurrent(test_session_commands, temp_project_dir):
    """Test multiple sessions can exist concurrently."""
    # Create temp directories for different projects
    with tempfile.TemporaryDirectory() as tmpdir2:
        # Start session 1
        response1 = await test_session_commands.handle("thread-1", f"/session start {temp_project_dir}")
        session_id1 = extract_session_id(response1)

        # Start session 2
        response2 = await test_session_commands.handle("thread-2", f"/session start {tmpdir2}")
        session_id2 = extract_session_id(response2)

        # Verify both sessions exist
        session1 = await test_session_commands.manager.get(session_id1)
        session2 = await test_session_commands.manager.get(session_id2)

        assert session1 is not None
        assert session2 is not None
        assert session1.id != session2.id
        assert session1.project_path != session2.project_path

        # List should show both
        response = await test_session_commands.handle("thread-1", "/session list")
        assert session_id1[:8] in response
        assert session_id2[:8] in response


@pytest.mark.asyncio
async def test_idempotent_crash_recovery(test_session_manager, test_lifecycle, test_crash_recovery, temp_project_dir):
    """Test crash recovery is idempotent - running twice doesn't re-recover."""
    # Create active session
    session = await test_session_manager.create(temp_project_dir, "thread-test")
    await test_lifecycle.transition(session.id, SessionStatus.CREATED, SessionStatus.ACTIVE)

    # First recovery
    recovered1 = await test_crash_recovery.recover()
    assert len(recovered1) == 1
    assert session.id in recovered1

    # Second recovery (should find nothing)
    recovered2 = await test_crash_recovery.recover()
    assert len(recovered2) == 0

    # Session should still be PAUSED
    session = await test_session_manager.get(session.id)
    assert session.status == SessionStatus.PAUSED


@pytest.mark.asyncio
async def test_session_commands_error_handling(test_session_commands):
    """Test error handling in session commands."""
    # Start without path
    response = await test_session_commands.handle("thread-1", "/session start")
    assert "error" in response.lower() or "usage" in response.lower()

    # Resume nonexistent session
    response = await test_session_commands.handle("thread-1", "/session resume nonexistent-id")
    assert "not found" in response.lower()

    # Stop without session ID
    response = await test_session_commands.handle("thread-1", "/session stop")
    assert "error" in response.lower() or "usage" in response.lower()

    # Invalid subcommand
    response = await test_session_commands.handle("thread-1", "/session invalid")
    assert "usage" in response.lower() or "available commands" in response.lower()


@pytest.mark.asyncio
async def test_process_lifecycle_tracking(test_session_commands, temp_project_dir):
    """Test that processes are tracked and cleaned up properly."""
    thread_id = "thread-test"

    # Start session
    response = await test_session_commands.handle(thread_id, f"/session start {temp_project_dir}")
    session_id = extract_session_id(response)

    # Verify process tracked
    assert session_id in test_session_commands.processes

    # Stop session
    await test_session_commands.handle(thread_id, f"/session stop {session_id}")

    # Verify process removed
    assert session_id not in test_session_commands.processes
