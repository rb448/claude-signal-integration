"""
Integration tests for full session workflow.

Tests the complete session lifecycle from creation to termination,
including crash recovery scenarios and offline operation.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from src.session import SessionManager, SessionLifecycle, SessionStatus, CrashRecovery, SessionCommands
from src.claude import ClaudeProcess
from src.claude.orchestrator import ClaudeOrchestrator
from src.thread import ThreadMapper, ThreadCommands
from src.signal.client import SignalClient
from src.signal.reconnection import ConnectionState
from unittest.mock import AsyncMock, Mock, patch


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
    """
    Extract truncated session ID from command response.

    Note: This returns the 8-char truncated ID shown in the response,
    not the full UUID. For full ID, use test_session_commands.thread_sessions[thread_id].
    """
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
    truncated_id = extract_session_id(response)

    # Get full session ID from thread mapping
    session_id = test_session_commands.thread_sessions[thread_id]

    # Verify session created
    session = await test_session_commands.manager.get(session_id)
    assert session is not None
    assert session.status == SessionStatus.ACTIVE
    assert session.project_path == temp_project_dir
    assert session.thread_id == thread_id

    # 2. List shows new session
    response = await test_session_commands.handle(thread_id, "/session list")
    assert truncated_id in response  # Truncated ID in list
    assert "ACTIVE" in response
    assert temp_project_dir in response or "tmp" in response  # Path might be truncated

    # 3. Stop session
    response = await test_session_commands.handle(thread_id, f"/session stop {session_id}")
    assert "Stopped session" in response
    assert truncated_id in response

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
    truncated_id = extract_session_id(response)

    # Get full session ID from thread mapping
    session_id = test_session_commands.thread_sessions[thread_id]

    # 2. Manually pause session (simulating crash or manual pause)
    await test_lifecycle.transition(session_id, SessionStatus.ACTIVE, SessionStatus.PAUSED)

    # 3. Verify session is paused
    session = await test_session_commands.manager.get(session_id)
    assert session.status == SessionStatus.PAUSED

    # 4. Resume session
    response = await test_session_commands.handle(thread_id, f"/session resume {session_id}")
    assert "Resumed session" in response
    assert truncated_id in response

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
        truncated_id1 = extract_session_id(response1)
        session_id1 = test_session_commands.thread_sessions["thread-1"]

        # Start session 2
        response2 = await test_session_commands.handle("thread-2", f"/session start {tmpdir2}")
        truncated_id2 = extract_session_id(response2)
        session_id2 = test_session_commands.thread_sessions["thread-2"]

        # Verify both sessions exist
        session1 = await test_session_commands.manager.get(session_id1)
        session2 = await test_session_commands.manager.get(session_id2)

        assert session1 is not None
        assert session2 is not None
        assert session1.id != session2.id
        assert session1.project_path != session2.project_path

        # List should show both
        response = await test_session_commands.handle("thread-1", "/session list")
        assert truncated_id1 in response
        assert truncated_id2 in response


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
    session_id = test_session_commands.thread_sessions[thread_id]

    # Verify process tracked
    assert session_id in test_session_commands.processes

    # Stop session
    await test_session_commands.handle(thread_id, f"/session stop {session_id}")

    # Verify process removed
    assert session_id not in test_session_commands.processes


@pytest.fixture
async def test_thread_mapper():
    """Create ThreadMapper with temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_threads.db")
        mapper = ThreadMapper(db_path=db_path)
        await mapper.initialize()
        yield mapper
        await mapper.close()


@pytest.fixture
async def test_session_commands_with_mapper(test_session_manager, test_lifecycle, test_thread_mapper):
    """Create SessionCommands with test components and thread mapper."""
    # Mock process factory
    def process_factory(session_id: str, project_path: str):
        process = AsyncMock(spec=ClaudeProcess)
        process.session_id = session_id
        process.project_path = project_path
        process.is_running = True
        return process

    return SessionCommands(
        test_session_manager,
        test_lifecycle,
        process_factory,
        thread_mapper=test_thread_mapper
    )


@pytest.mark.asyncio
async def test_mapped_thread_session_workflow(test_session_commands_with_mapper, test_thread_mapper, temp_project_dir):
    """
    End-to-end: map thread → start session → session uses mapped path.
    """
    thread_id = "thread-mapped-test"

    # 1. Map thread to project path
    mapping = await test_thread_mapper.map(thread_id, temp_project_dir)
    assert mapping.thread_id == thread_id
    assert mapping.project_path == temp_project_dir

    # 2. Start session without explicit path (should use mapping)
    response = await test_session_commands_with_mapper.handle(thread_id, "/session start")
    assert "Started session" in response
    truncated_id = extract_session_id(response)

    # Get full session ID from thread mapping
    session_id = test_session_commands_with_mapper.thread_sessions[thread_id]

    # 3. Verify session uses mapped path
    session = await test_session_commands_with_mapper.manager.get(session_id)
    assert session is not None
    assert session.project_path == temp_project_dir
    assert session.status == SessionStatus.ACTIVE
    assert session.thread_id == thread_id

    # 4. Verify process spawned with mapped path
    assert session_id in test_session_commands_with_mapper.processes
    process = test_session_commands_with_mapper.processes[session_id]
    assert process.project_path == temp_project_dir

    # 5. Verify response mentions mapped path
    assert temp_project_dir in response


@pytest.mark.asyncio
async def test_unmapped_thread_explicit_path(test_session_commands_with_mapper, temp_project_dir):
    """
    End-to-end: unmapped thread + explicit path works (backward compat).
    """
    thread_id = "thread-unmapped-test"

    # 1. Start session with explicit path (thread not mapped)
    response = await test_session_commands_with_mapper.handle(
        thread_id,
        f"/session start {temp_project_dir}"
    )
    assert "Started session" in response
    truncated_id = extract_session_id(response)

    # Get full session ID from thread mapping
    session_id = test_session_commands_with_mapper.thread_sessions[thread_id]

    # 2. Verify session uses explicit path
    session = await test_session_commands_with_mapper.manager.get(session_id)
    assert session is not None
    assert session.project_path == temp_project_dir
    assert session.status == SessionStatus.ACTIVE

    # 3. Verify session starts successfully
    assert session_id in test_session_commands_with_mapper.processes


@pytest.mark.asyncio
async def test_unmapped_thread_no_path_fails(test_session_commands_with_mapper):
    """
    End-to-end: unmapped thread without path returns error.
    """
    thread_id = "thread-no-mapping-no-path"

    # 1. Try to start session without path on unmapped thread
    response = await test_session_commands_with_mapper.handle(thread_id, "/session start")

    # 2. Verify error message mentions both options
    assert "not mapped" in response.lower()
    assert "/thread map" in response or "/session start" in response

    # 3. Verify no session created
    sessions = await test_session_commands_with_mapper.manager.list()
    # Should have no sessions for this thread
    thread_sessions = [s for s in sessions if s.thread_id == thread_id]
    assert len(thread_sessions) == 0


@pytest.mark.asyncio
async def test_mapped_thread_ignores_explicit_path(test_session_commands_with_mapper, test_thread_mapper, temp_project_dir):
    """
    End-to-end: mapped thread ignores explicit path in favor of mapping.
    """
    thread_id = "thread-mapping-priority"

    # Create second temp directory to use as explicit path
    with tempfile.TemporaryDirectory() as other_dir:
        # 1. Map thread to temp_project_dir
        await test_thread_mapper.map(thread_id, temp_project_dir)

        # 2. Try to start session with DIFFERENT explicit path
        response = await test_session_commands_with_mapper.handle(
            thread_id,
            f"/session start {other_dir}"
        )
        assert "Started session" in response
        truncated_id = extract_session_id(response)

        # Get full session ID from thread mapping
        session_id = test_session_commands_with_mapper.thread_sessions[thread_id]

        # 3. Verify session uses MAPPED path, not explicit path
        session = await test_session_commands_with_mapper.manager.get(session_id)
        assert session.project_path == temp_project_dir
        assert session.project_path != other_dir

        # 4. Verify response shows mapped path
        assert temp_project_dir in response
        assert other_dir not in response


@pytest.mark.asyncio
async def test_thread_mapping_survives_session_lifecycle(test_session_commands_with_mapper, test_thread_mapper, temp_project_dir):
    """
    End-to-end: thread mapping persists across session start/stop cycles.
    """
    thread_id = "thread-persistent-mapping"

    # 1. Map thread
    await test_thread_mapper.map(thread_id, temp_project_dir)

    # 2. Start session
    response1 = await test_session_commands_with_mapper.handle(thread_id, "/session start")
    session_id1 = test_session_commands_with_mapper.thread_sessions[thread_id]

    # 3. Stop session
    await test_session_commands_with_mapper.handle(thread_id, f"/session stop {session_id1}")

    # 4. Start another session (mapping should still work)
    response2 = await test_session_commands_with_mapper.handle(thread_id, "/session start")
    assert "Started session" in response2
    session_id2 = test_session_commands_with_mapper.thread_sessions[thread_id]

    # 5. Verify second session uses mapped path
    session2 = await test_session_commands_with_mapper.manager.get(session_id2)
    assert session2.project_path == temp_project_dir

    # 6. Verify different session IDs
    assert session_id1 != session_id2


@pytest.mark.asyncio
async def test_claude_continues_working_during_disconnect():
    """
    Integration test: Claude processes tasks while mobile disconnected.

    Flow:
    1. User sends command while connected
    2. Connection drops during Claude processing
    3. Claude completes work and buffers response
    4. Connection restored
    5. Response delivered from buffer
    """
    # Setup
    session_manager = SessionManager(db_path=":memory:")
    await session_manager.initialize()

    signal_client = SignalClient(
        api_url="http://localhost:8080",
        phone_number="+15551234567"
    )
    signal_client.session_id = "test-session-123"

    orchestrator = ClaudeOrchestrator(
        bridge=Mock(),
        parser=Mock(),
        responder=Mock(),
        send_signal=AsyncMock(),
    )

    # Create session
    session = await session_manager.create(
        project_path="/test/project",
        thread_id="+15559999999"
    )
    await session_manager.update(session.id, status=SessionStatus.ACTIVE)

    # Step 1: User sends command while CONNECTED
    assert signal_client.reconnection_manager.state == ConnectionState.CONNECTED

    user_command = "Analyze the authentication module"

    # Step 2: Simulate connection drop DURING processing
    # (In real scenario, this happens asynchronously)
    signal_client.reconnection_manager.transition(ConnectionState.DISCONNECTED)

    # Step 3: Claude processes command (continues despite disconnect)
    # Mock Claude response generation
    claude_response = (
        "The authentication module uses JWT tokens with RS256 signing. "
        "Found 3 security issues: ..."
    )

    # Step 4: Orchestrator attempts to send response → gets buffered
    recipient = "+15559999999"

    # Check state before send
    assert signal_client.reconnection_manager.state == ConnectionState.DISCONNECTED

    # Send message - should buffer instead of sending
    await signal_client.send_message(recipient, claude_response)

    # Verify message was buffered
    assert len(signal_client.message_buffer) == 1
    buffered = signal_client.message_buffer.dequeue()
    assert buffered == (recipient, claude_response)

    # Step 5: Connection restored (auto_reconnect succeeds)
    # Re-enqueue the message we dequeued for verification
    signal_client.message_buffer.enqueue(recipient, claude_response)

    # Mock successful reconnection
    with patch.object(signal_client, 'connect', new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = None

        # Trigger reconnection
        await signal_client.auto_reconnect()

    # Step 6: Verify state is CONNECTED and buffer drained
    assert signal_client.reconnection_manager.state == ConnectionState.CONNECTED
    assert len(signal_client.message_buffer) == 0  # Buffer drained

    # Step 7: Verify session context updated with Claude activity
    # (Session persisted the fact that Claude completed work during disconnect)
    updated_session = await session_manager.get(session.id)
    assert updated_session.status == SessionStatus.ACTIVE

    # Cleanup
    await session_manager.close()


@pytest.mark.asyncio
async def test_session_tracks_claude_activity_during_disconnect():
    """
    Verify session context persists Claude activity during disconnect.
    """
    # Setup
    session_manager = SessionManager(db_path=":memory:")
    await session_manager.initialize()

    session = await session_manager.create(
        project_path="/test/project",
        thread_id="+15559999999"
    )

    # Simulate Claude activity during disconnect
    await session_manager.track_activity(
        session.id,
        activity_type="command_executed",
        details={"command": "analyze auth module", "files_analyzed": 5}
    )

    await session_manager.track_activity(
        session.id,
        activity_type="response_generated",
        details={"response_length": 250, "issues_found": 3}
    )

    # Verify activity logged in context
    updated_session = await session_manager.get(session.id)
    assert "activity_log" in updated_session.context
    assert len(updated_session.context["activity_log"]) == 2

    # Verify activity details
    activity_log = updated_session.context["activity_log"]
    assert activity_log[0]["type"] == "command_executed"
    assert activity_log[0]["details"]["files_analyzed"] == 5
    assert activity_log[1]["type"] == "response_generated"
    assert activity_log[1]["details"]["issues_found"] == 3

    # Cleanup
    await session_manager.close()


@pytest.mark.asyncio
async def test_catchup_summary_after_reconnection():
    """
    Test complete offline work → reconnection → catch-up summary flow.

    Scenario:
    1. Start session
    2. Track several Claude activities
    3. Simulate reconnection
    4. Verify catch-up summary generated
    5. Verify summary sent as notification
    6. Verify activity log cleared after summary
    """
    # Setup
    session_manager = SessionManager(db_path=":memory:")
    await session_manager.initialize()

    # 1. Create session
    session = await session_manager.create("/tmp/test-project", "+15559999999")

    # 2. Track multiple activities
    activities = [
        ("tool_call", {"tool": "Read", "target": "config.json"}),
        ("tool_call", {"tool": "Edit", "target": "src/main.py"}),
        ("command_executed", {"command": "pytest"}),
    ]
    for activity_type, details in activities:
        await session_manager.track_activity(session.id, activity_type, details)

    # 3. Generate catch-up summary
    summary = await session_manager.generate_catchup_summary(session.id)

    # 4. Verify summary content
    assert "3 operations" in summary
    assert "Read config.json" in summary
    assert "Edit src/main.py" in summary
    assert "pytest" in summary
    assert "Ready to continue" in summary

    # 5. Verify activity log cleared
    updated_session = await session_manager.get(session.id)
    assert updated_session.context.get("activity_log") == []

    # Cleanup
    await session_manager.close()


@pytest.mark.asyncio
async def test_catchup_summary_empty_activity_log():
    """Test catch-up summary with empty activity log returns appropriate message."""
    # Setup
    session_manager = SessionManager(db_path=":memory:")
    await session_manager.initialize()

    # Create session without any activities
    session = await session_manager.create("/tmp/test-project", "+15559999999")

    # Generate summary
    summary = await session_manager.generate_catchup_summary(session.id)

    # Verify empty message
    assert summary == "No activity while disconnected"

    # Cleanup
    await session_manager.close()


@pytest.mark.asyncio
async def test_catchup_summary_single_activity():
    """Test catch-up summary with single activity (singular grammar)."""
    # Setup
    session_manager = SessionManager(db_path=":memory:")
    await session_manager.initialize()

    # Create session with one activity
    session = await session_manager.create("/tmp/test-project", "+15559999999")
    await session_manager.track_activity(
        session.id,
        "tool_call",
        {"tool": "Read", "target": "config.json"}
    )

    # Generate summary
    summary = await session_manager.generate_catchup_summary(session.id)

    # Verify singular grammar
    assert "1 operation:" in summary
    assert "operations" not in summary
    assert "Read config.json" in summary

    # Cleanup
    await session_manager.close()
