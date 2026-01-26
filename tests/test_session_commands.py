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
