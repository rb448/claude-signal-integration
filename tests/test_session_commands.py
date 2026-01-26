"""
Tests for session command handlers.

RED Phase: Write failing tests before implementation.
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from src.session import SessionManager, SessionStatus, Session, SessionLifecycle
from src.session.commands import SessionCommands
from src.claude import ClaudeProcess
from src.claude.orchestrator import ClaudeOrchestrator
from src.thread import ThreadMapper, ThreadMapping
from src.approval.commands import ApprovalCommands
from src.approval.manager import ApprovalManager
from datetime import datetime, UTC


@pytest.mark.asyncio
async def test_start_creates_session_and_spawns_process():
    """Test /session start creates session and spawns Claude process."""
    # Setup mocks
    manager = AsyncMock(spec=SessionManager)
    lifecycle = AsyncMock(spec=SessionLifecycle)
    process_factory = MagicMock()

    # Mock session creation
    session = Session(
        id="test-session-id",
        project_path="/tmp/test-project",
        thread_id="thread-123",
        status=SessionStatus.CREATED,
        context={},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    manager.create.return_value = session

    # Mock transition to ACTIVE
    active_session = Session(
        id="test-session-id",
        project_path="/tmp/test-project",
        thread_id="thread-123",
        status=SessionStatus.ACTIVE,
        context={},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    lifecycle.transition.return_value = active_session

    # Mock process
    mock_process = AsyncMock(spec=ClaudeProcess)
    process_factory.return_value = mock_process

    # Create commands handler
    commands = SessionCommands(manager, lifecycle, process_factory)

    # Execute command
    with patch('pathlib.Path.exists', return_value=True):
        response = await commands.handle("thread-123", "/session start /tmp/test-project")

    # Verify session created
    manager.create.assert_called_once_with("/tmp/test-project", "thread-123")

    # Verify transition CREATED -> ACTIVE
    lifecycle.transition.assert_called_once_with(
        "test-session-id", SessionStatus.CREATED, SessionStatus.ACTIVE
    )

    # Verify process spawned
    process_factory.assert_called_once_with("test-session-id", "/tmp/test-project")
    mock_process.start.assert_called_once()

    # Verify response
    assert "Started session" in response
    assert "test-ses" in response  # Truncated session ID (first 8 chars)
    assert "/tmp/test-project" in response


@pytest.mark.asyncio
async def test_start_without_path_returns_error():
    """Test /session start without path returns error message."""
    manager = AsyncMock(spec=SessionManager)
    lifecycle = AsyncMock(spec=SessionLifecycle)
    process_factory = MagicMock()

    commands = SessionCommands(manager, lifecycle, process_factory)

    # Execute command without path
    response = await commands.handle("thread-123", "/session start")

    # Verify error response
    assert "project path" in response.lower() or "usage" in response.lower()

    # Verify no session created
    manager.create.assert_not_called()


@pytest.mark.asyncio
async def test_start_with_nonexistent_path_returns_error():
    """Test /session start with nonexistent path returns error."""
    manager = AsyncMock(spec=SessionManager)
    lifecycle = AsyncMock(spec=SessionLifecycle)
    process_factory = MagicMock()

    commands = SessionCommands(manager, lifecycle, process_factory)

    # Execute command with nonexistent path
    with patch('pathlib.Path.exists', return_value=False):
        response = await commands.handle("thread-123", "/session start /nonexistent/path")

    # Verify error response
    assert "not exist" in response.lower() or "not found" in response.lower()

    # Verify no session created
    manager.create.assert_not_called()


@pytest.mark.asyncio
async def test_list_shows_all_sessions():
    """Test /session list returns all sessions in formatted table."""
    manager = AsyncMock(spec=SessionManager)
    lifecycle = AsyncMock(spec=SessionLifecycle)
    process_factory = MagicMock()

    # Mock sessions
    sessions = [
        Session(
            id="session-1",
            project_path="/tmp/project1",
            thread_id="thread-1",
            status=SessionStatus.ACTIVE,
            context={},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ),
        Session(
            id="session-2",
            project_path="/tmp/project2",
            thread_id="thread-2",
            status=SessionStatus.PAUSED,
            context={},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ),
    ]
    manager.list.return_value = sessions

    commands = SessionCommands(manager, lifecycle, process_factory)

    # Execute command
    response = await commands.handle("thread-123", "/session list")

    # Verify list called
    manager.list.assert_called_once()

    # Verify response contains session data
    # Session IDs are truncated to 8 chars in display
    assert "session-" in response  # Truncated IDs
    assert "ACTIVE" in response
    assert "PAUSED" in response
    assert "/tmp/project1" in response
    assert "/tmp/project2" in response


@pytest.mark.asyncio
async def test_list_with_no_sessions():
    """Test /session list with no sessions returns appropriate message."""
    manager = AsyncMock(spec=SessionManager)
    lifecycle = AsyncMock(spec=SessionLifecycle)
    process_factory = MagicMock()

    # Mock empty list
    manager.list.return_value = []

    commands = SessionCommands(manager, lifecycle, process_factory)

    # Execute command
    response = await commands.handle("thread-123", "/session list")

    # Verify appropriate message
    assert "no sessions" in response.lower() or "empty" in response.lower()


@pytest.mark.asyncio
async def test_resume_transitions_paused_to_active():
    """Test /session resume transitions PAUSED session to ACTIVE."""
    manager = AsyncMock(spec=SessionManager)
    lifecycle = AsyncMock(spec=SessionLifecycle)
    process_factory = MagicMock()

    # Mock paused session
    paused_session = Session(
        id="session-1",
        project_path="/tmp/project",
        thread_id="thread-1",
        status=SessionStatus.PAUSED,
        context={},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    manager.get.return_value = paused_session

    # Mock transition to ACTIVE
    active_session = Session(
        id="session-1",
        project_path="/tmp/project",
        thread_id="thread-1",
        status=SessionStatus.ACTIVE,
        context={},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    lifecycle.transition.return_value = active_session

    # Mock process
    mock_process = AsyncMock(spec=ClaudeProcess)
    process_factory.return_value = mock_process

    commands = SessionCommands(manager, lifecycle, process_factory)

    # Execute command
    response = await commands.handle("thread-1", "/session resume session-1")

    # Verify session retrieved
    manager.get.assert_called_once_with("session-1")

    # Verify transition PAUSED -> ACTIVE
    lifecycle.transition.assert_called_once_with(
        "session-1", SessionStatus.PAUSED, SessionStatus.ACTIVE
    )

    # Verify process spawned
    process_factory.assert_called_once_with("session-1", "/tmp/project")
    mock_process.start.assert_called_once()

    # Verify response
    assert "Resumed session" in response
    assert "session-" in response  # Truncated session ID (first 8 chars)


@pytest.mark.asyncio
async def test_resume_without_session_id_returns_error():
    """Test /session resume without session ID returns error."""
    manager = AsyncMock(spec=SessionManager)
    lifecycle = AsyncMock(spec=SessionLifecycle)
    process_factory = MagicMock()

    commands = SessionCommands(manager, lifecycle, process_factory)

    # Execute command without session ID
    response = await commands.handle("thread-1", "/session resume")

    # Verify error response
    assert "session id" in response.lower() or "usage" in response.lower()


@pytest.mark.asyncio
async def test_resume_nonexistent_session_returns_error():
    """Test /session resume with nonexistent session returns error."""
    manager = AsyncMock(spec=SessionManager)
    lifecycle = AsyncMock(spec=SessionLifecycle)
    process_factory = MagicMock()

    # Mock session not found
    manager.get.return_value = None

    commands = SessionCommands(manager, lifecycle, process_factory)

    # Execute command
    response = await commands.handle("thread-1", "/session resume nonexistent-id")

    # Verify error response
    assert "not found" in response.lower()


@pytest.mark.asyncio
async def test_stop_terminates_process_and_session():
    """Test /session stop terminates process and transitions to TERMINATED."""
    manager = AsyncMock(spec=SessionManager)
    lifecycle = AsyncMock(spec=SessionLifecycle)
    process_factory = MagicMock()

    # Mock active session
    active_session = Session(
        id="session-1",
        project_path="/tmp/project",
        thread_id="thread-1",
        status=SessionStatus.ACTIVE,
        context={},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    manager.get.return_value = active_session

    # Mock transition to TERMINATED
    terminated_session = Session(
        id="session-1",
        project_path="/tmp/project",
        thread_id="thread-1",
        status=SessionStatus.TERMINATED,
        context={},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    lifecycle.transition.return_value = terminated_session

    # Mock process
    mock_process = AsyncMock(spec=ClaudeProcess)

    commands = SessionCommands(manager, lifecycle, process_factory)
    # Manually add process to running processes
    commands.processes["session-1"] = mock_process

    # Execute command
    response = await commands.handle("thread-1", "/session stop session-1")

    # Verify session retrieved
    manager.get.assert_called_once_with("session-1")

    # Verify process stopped
    mock_process.stop.assert_called_once()

    # Verify transition ACTIVE -> TERMINATED
    lifecycle.transition.assert_called_once_with(
        "session-1", SessionStatus.ACTIVE, SessionStatus.TERMINATED
    )

    # Verify response
    assert "Stopped session" in response
    assert "session-" in response  # Truncated session ID (first 8 chars)

    # Verify process removed from tracking
    assert "session-1" not in commands.processes


@pytest.mark.asyncio
async def test_stop_without_session_id_returns_error():
    """Test /session stop without session ID returns error."""
    manager = AsyncMock(spec=SessionManager)
    lifecycle = AsyncMock(spec=SessionLifecycle)
    process_factory = MagicMock()

    commands = SessionCommands(manager, lifecycle, process_factory)

    # Execute command without session ID
    response = await commands.handle("thread-1", "/session stop")

    # Verify error response
    assert "session id" in response.lower() or "usage" in response.lower()


@pytest.mark.asyncio
async def test_invalid_subcommand_returns_help():
    """Test invalid subcommand returns help message."""
    manager = AsyncMock(spec=SessionManager)
    lifecycle = AsyncMock(spec=SessionLifecycle)
    process_factory = MagicMock()

    commands = SessionCommands(manager, lifecycle, process_factory)

    # Execute command with invalid subcommand
    response = await commands.handle("thread-1", "/session invalid")

    # Verify help response
    assert "usage" in response.lower() or "available commands" in response.lower()


@pytest.mark.asyncio
async def test_help_command():
    """Test /session without subcommand returns help."""
    manager = AsyncMock(spec=SessionManager)
    lifecycle = AsyncMock(spec=SessionLifecycle)
    process_factory = MagicMock()

    commands = SessionCommands(manager, lifecycle, process_factory)

    # Execute command without subcommand
    response = await commands.handle("thread-1", "/session")

    # Verify help response
    assert "usage" in response.lower() or "available commands" in response.lower()
    assert "start" in response.lower()
    assert "list" in response.lower()
    assert "resume" in response.lower()
    assert "stop" in response.lower()


@pytest.mark.asyncio
async def test_start_sets_orchestrator_bridge():
    """Test that _start() wires orchestrator bridge to enable command execution."""
    # Setup mocks
    manager = AsyncMock(spec=SessionManager)
    lifecycle = AsyncMock(spec=SessionLifecycle)
    process_factory = MagicMock()
    orchestrator = MagicMock(spec=ClaudeOrchestrator)

    # Mock session creation
    session = Session(
        id="test-session-id",
        project_path="/tmp/test-project",
        thread_id="thread-123",
        status=SessionStatus.CREATED,
        context={},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    manager.create.return_value = session

    # Mock transition to ACTIVE
    active_session = Session(
        id="test-session-id",
        project_path="/tmp/test-project",
        thread_id="thread-123",
        status=SessionStatus.ACTIVE,
        context={},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    lifecycle.transition.return_value = active_session

    # Mock process
    mock_process = AsyncMock(spec=ClaudeProcess)
    mock_bridge = MagicMock()
    mock_process.get_bridge.return_value = mock_bridge
    process_factory.return_value = mock_process

    # Create commands handler with orchestrator
    commands = SessionCommands(manager, lifecycle, process_factory, orchestrator)

    # Execute start command
    with patch('pathlib.Path.exists', return_value=True):
        await commands.handle("thread-123", "/session start /tmp/test-project")

    # Verify bridge is set (not None)
    assert orchestrator.bridge is not None, "orchestrator.bridge should be set after _start()"

    # Verify it's the process's bridge
    assert orchestrator.bridge is mock_bridge, "orchestrator.bridge should reference process bridge"


@pytest.mark.asyncio
async def test_resume_sets_orchestrator_bridge():
    """Test that _resume() wires orchestrator bridge to enable command execution."""
    # Setup mocks
    manager = AsyncMock(spec=SessionManager)
    lifecycle = AsyncMock(spec=SessionLifecycle)
    process_factory = MagicMock()
    orchestrator = MagicMock(spec=ClaudeOrchestrator)

    # Mock paused session
    paused_session = Session(
        id="session-1",
        project_path="/tmp/project",
        thread_id="thread-1",
        status=SessionStatus.PAUSED,
        context={},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    manager.get.return_value = paused_session

    # Mock transition to ACTIVE
    active_session = Session(
        id="session-1",
        project_path="/tmp/project",
        thread_id="thread-1",
        status=SessionStatus.ACTIVE,
        context={},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    lifecycle.transition.return_value = active_session

    # Mock process
    mock_process = AsyncMock(spec=ClaudeProcess)
    mock_bridge = MagicMock()
    mock_process.get_bridge.return_value = mock_bridge
    process_factory.return_value = mock_process

    # Create commands handler with orchestrator
    commands = SessionCommands(manager, lifecycle, process_factory, orchestrator)

    # Clear orchestrator bridge to simulate fresh daemon state
    orchestrator.bridge = None

    # Resume session
    await commands.handle("thread-1", "/session resume session-1")

    # Verify bridge is set (not None)
    assert orchestrator.bridge is not None, "orchestrator.bridge should be set after _resume()"

    # Verify it's the process's bridge
    assert orchestrator.bridge is mock_bridge, "orchestrator.bridge should reference process bridge"


@pytest.mark.asyncio
async def test_handle_routes_thread_commands():
    """Test that handle() routes /thread commands to ThreadCommands."""
    from src.thread import ThreadCommands

    # Setup mocks
    manager = AsyncMock(spec=SessionManager)
    lifecycle = AsyncMock(spec=SessionLifecycle)
    process_factory = MagicMock()
    thread_commands = AsyncMock(spec=ThreadCommands)

    # Mock thread_commands.handle() to return a message
    thread_commands.handle.return_value = "Thread command response"

    # Create commands handler with thread_commands
    commands = SessionCommands(
        manager,
        lifecycle,
        process_factory,
        thread_commands=thread_commands
    )

    # Execute /thread command
    response = await commands.handle("thread-123", "/thread map /tmp/project")

    # Verify ThreadCommands.handle() was called
    thread_commands.handle.assert_called_once_with("thread-123", "/thread map /tmp/project")

    # Verify response is from ThreadCommands
    assert response == "Thread command response"


@pytest.mark.asyncio
async def test_handle_thread_commands_unavailable():
    """Test that handle() returns error when thread_commands not provided."""
    # Setup mocks
    manager = AsyncMock(spec=SessionManager)
    lifecycle = AsyncMock(spec=SessionLifecycle)
    process_factory = MagicMock()

    # Create commands handler WITHOUT thread_commands
    commands = SessionCommands(manager, lifecycle, process_factory)

    # Execute /thread command
    response = await commands.handle("thread-123", "/thread map /tmp/project")

    # Verify error response
    assert "not available" in response.lower()


@pytest.mark.asyncio
async def test_start_uses_thread_mapping():
    """Test /session start uses thread mapping when available, ignores explicit path."""
    # Setup mocks
    manager = AsyncMock(spec=SessionManager)
    lifecycle = AsyncMock(spec=SessionLifecycle)
    process_factory = MagicMock()
    thread_mapper = AsyncMock(spec=ThreadMapper)

    # Mock thread mapping
    mapping = ThreadMapping(
        thread_id="thread-123",
        project_path="/mapped/project",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    thread_mapper.get_by_thread.return_value = mapping

    # Mock session creation
    session = Session(
        id="test-session-id",
        project_path="/mapped/project",
        thread_id="thread-123",
        status=SessionStatus.CREATED,
        context={},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    manager.create.return_value = session

    # Mock transition to ACTIVE
    active_session = Session(
        id="test-session-id",
        project_path="/mapped/project",
        thread_id="thread-123",
        status=SessionStatus.ACTIVE,
        context={},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    lifecycle.transition.return_value = active_session

    # Mock process
    mock_process = AsyncMock(spec=ClaudeProcess)
    process_factory.return_value = mock_process

    # Create commands handler with thread_mapper
    commands = SessionCommands(manager, lifecycle, process_factory, thread_mapper=thread_mapper)

    # Execute command with explicit path (should be ignored in favor of mapping)
    with patch('pathlib.Path.exists', return_value=True):
        response = await commands.handle("thread-123", "/session start /different/path")

    # Verify thread mapping lookup
    thread_mapper.get_by_thread.assert_called_once_with("thread-123")

    # Verify session created with MAPPED path, not explicit path
    manager.create.assert_called_once_with("/mapped/project", "thread-123")

    # Verify process spawned with mapped path
    process_factory.assert_called_once_with("test-session-id", "/mapped/project")

    # Verify response
    assert "Started session" in response
    assert "/mapped/project" in response


@pytest.mark.asyncio
async def test_start_unmapped_thread_requires_path():
    """Test /session start on unmapped thread requires explicit path."""
    # Setup mocks
    manager = AsyncMock(spec=SessionManager)
    lifecycle = AsyncMock(spec=SessionLifecycle)
    process_factory = MagicMock()
    thread_mapper = AsyncMock(spec=ThreadMapper)

    # Mock no thread mapping
    thread_mapper.get_by_thread.return_value = None

    # Create commands handler with thread_mapper
    commands = SessionCommands(manager, lifecycle, process_factory, thread_mapper=thread_mapper)

    # Execute command without path on unmapped thread
    response = await commands.handle("thread-123", "/session start")

    # Verify thread mapping lookup
    thread_mapper.get_by_thread.assert_called_once_with("thread-123")

    # Verify error message mentions both options
    assert "not mapped" in response.lower()
    assert "/thread map" in response or "/session start" in response

    # Verify no session created
    manager.create.assert_not_called()


@pytest.mark.asyncio
async def test_start_unmapped_thread_with_path_works():
    """Test /session start on unmapped thread with explicit path works (backward compatibility)."""
    # Setup mocks
    manager = AsyncMock(spec=SessionManager)
    lifecycle = AsyncMock(spec=SessionLifecycle)
    process_factory = MagicMock()
    thread_mapper = AsyncMock(spec=ThreadMapper)

    # Mock no thread mapping
    thread_mapper.get_by_thread.return_value = None

    # Mock session creation
    session = Session(
        id="test-session-id",
        project_path="/explicit/path",
        thread_id="thread-123",
        status=SessionStatus.CREATED,
        context={},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    manager.create.return_value = session

    # Mock transition to ACTIVE
    active_session = Session(
        id="test-session-id",
        project_path="/explicit/path",
        thread_id="thread-123",
        status=SessionStatus.ACTIVE,
        context={},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    lifecycle.transition.return_value = active_session

    # Mock process
    mock_process = AsyncMock(spec=ClaudeProcess)
    process_factory.return_value = mock_process

    # Create commands handler with thread_mapper
    commands = SessionCommands(manager, lifecycle, process_factory, thread_mapper=thread_mapper)

    # Execute command with explicit path
    with patch('pathlib.Path.exists', return_value=True):
        response = await commands.handle("thread-123", "/session start /explicit/path")

    # Verify thread mapping lookup
    thread_mapper.get_by_thread.assert_called_once_with("thread-123")

    # Verify session created with explicit path
    manager.create.assert_called_once_with("/explicit/path", "thread-123")

    # Verify process spawned
    process_factory.assert_called_once_with("test-session-id", "/explicit/path")

    # Verify response
    assert "Started session" in response
    assert "/explicit/path" in response


@pytest.mark.asyncio
async def test_start_without_thread_mapper():
    """Test /session start works without thread_mapper (graceful degradation)."""
    # Setup mocks
    manager = AsyncMock(spec=SessionManager)
    lifecycle = AsyncMock(spec=SessionLifecycle)
    process_factory = MagicMock()

    # Mock session creation
    session = Session(
        id="test-session-id",
        project_path="/tmp/test-project",
        thread_id="thread-123",
        status=SessionStatus.CREATED,
        context={},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    manager.create.return_value = session

    # Mock transition to ACTIVE
    active_session = Session(
        id="test-session-id",
        project_path="/tmp/test-project",
        thread_id="thread-123",
        status=SessionStatus.ACTIVE,
        context={},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    lifecycle.transition.return_value = active_session

    # Mock process
    mock_process = AsyncMock(spec=ClaudeProcess)
    process_factory.return_value = mock_process

    # Create commands handler WITHOUT thread_mapper
    commands = SessionCommands(manager, lifecycle, process_factory)

    # Execute command with explicit path
    with patch('pathlib.Path.exists', return_value=True):
        response = await commands.handle("thread-123", "/session start /tmp/test-project")

    # Verify session created with explicit path
    manager.create.assert_called_once_with("/tmp/test-project", "thread-123")

    # Verify response
    assert "Started session" in response
    assert "/tmp/test-project" in response


@pytest.mark.asyncio
async def test_approval_commands_routed_before_session_commands():
    """Test that approval commands take priority over session commands."""
    # Setup mocks
    manager = AsyncMock(spec=SessionManager)
    lifecycle = AsyncMock(spec=SessionLifecycle)
    process_factory = MagicMock()

    # Create ApprovalCommands
    approval_manager = ApprovalManager()
    approval_commands = ApprovalCommands(approval_manager)

    # Create pending approval
    request = approval_manager.request({"tool": "Edit"}, reason="Modifies file")

    # Create SessionCommands with approval_commands
    commands = SessionCommands(
        manager,
        lifecycle,
        process_factory,
        approval_commands=approval_commands
    )

    # Execute approval command
    response = await commands.handle("thread-123", f"approve {request.id}")

    # Should route to approval commands
    assert "Approved" in response
    assert request.id[:8] in response


@pytest.mark.asyncio
async def test_approval_commands_returns_none_for_unknown():
    """Test that approval commands return None for unknown commands, allowing fallthrough."""
    # Setup mocks
    manager = AsyncMock(spec=SessionManager)
    lifecycle = AsyncMock(spec=SessionLifecycle)
    process_factory = MagicMock()

    # Create ApprovalCommands
    approval_manager = ApprovalManager()
    approval_commands = ApprovalCommands(approval_manager)

    # Create SessionCommands with approval_commands
    commands = SessionCommands(
        manager,
        lifecycle,
        process_factory,
        approval_commands=approval_commands
    )

    # Mock session list
    manager.list.return_value = []

    # Execute session command (should fall through approval commands)
    response = await commands.handle("thread-123", "/session list")

    # Should route to session commands
    assert "No sessions found" in response


@pytest.mark.asyncio
async def test_help_includes_approval_commands():
    """Test that help message includes approval commands when available."""
    # Setup mocks
    manager = AsyncMock(spec=SessionManager)
    lifecycle = AsyncMock(spec=SessionLifecycle)
    process_factory = MagicMock()

    # Create ApprovalCommands
    approval_manager = ApprovalManager()
    approval_commands = ApprovalCommands(approval_manager)

    # Create SessionCommands with approval_commands
    commands = SessionCommands(
        manager,
        lifecycle,
        process_factory,
        approval_commands=approval_commands
    )

    # Get help
    help_text = commands._help()

    # Should include approval commands
    assert "Approval Commands:" in help_text
    assert "approve {id}" in help_text
    assert "reject {id}" in help_text
    assert "approve all" in help_text


@pytest.mark.asyncio
async def test_code_command_help():
    """Test /code command shows help text."""
    # Setup mocks
    manager = AsyncMock(spec=SessionManager)
    lifecycle = AsyncMock(spec=SessionLifecycle)
    process_factory = MagicMock()

    commands = SessionCommands(manager, lifecycle, process_factory)

    # Call /code with no args
    result = await commands.handle("thread-1", "/code")

    # Should return help text
    assert "Code Display Commands" in result
    assert "/code full" in result
    assert "/code help" in result


@pytest.mark.asyncio
async def test_code_command_explicit_help():
    """Test /code help shows help text."""
    # Setup mocks
    manager = AsyncMock(spec=SessionManager)
    lifecycle = AsyncMock(spec=SessionLifecycle)
    process_factory = MagicMock()

    commands = SessionCommands(manager, lifecycle, process_factory)

    # Call /code help
    result = await commands.handle("thread-1", "/code help")

    # Should return help text
    assert "Code Display Commands" in result
    assert "/code full" in result


@pytest.mark.asyncio
async def test_code_command_full_placeholder():
    """Test /code full returns placeholder for Phase 6."""
    # Setup mocks
    manager = AsyncMock(spec=SessionManager)
    lifecycle = AsyncMock(spec=SessionLifecycle)
    process_factory = MagicMock()

    commands = SessionCommands(manager, lifecycle, process_factory)

    # Call /code full
    result = await commands.handle("thread-1", "/code full")

    # Should return placeholder message
    assert "not yet implemented" in result.lower() or "coming" in result.lower()


@pytest.mark.asyncio
async def test_code_command_unknown_subcommand():
    """Test /code with unknown subcommand shows error."""
    # Setup mocks
    manager = AsyncMock(spec=SessionManager)
    lifecycle = AsyncMock(spec=SessionLifecycle)
    process_factory = MagicMock()

    commands = SessionCommands(manager, lifecycle, process_factory)

    # Call with unknown subcommand
    result = await commands.handle("thread-1", "/code invalid")

    # Should return error with help reference
    assert "Unknown subcommand" in result or "invalid" in result
    assert "/code help" in result
