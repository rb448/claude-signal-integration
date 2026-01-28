"""Integration tests for end-to-end custom command flow.

Tests the complete flow: list → show → invoke → execute → stream.
"""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, MagicMock

from src.custom_commands.commands import CustomCommands
from src.custom_commands.registry import CustomCommandRegistry
from src.claude.orchestrator import ClaudeOrchestrator
from src.claude.parser import OutputParser
from src.claude.responder import SignalResponder


@pytest.fixture
async def registry():
    """Create test registry with temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_commands.db"
        registry = CustomCommandRegistry(db_path)
        await registry.initialize()
        yield registry


@pytest.fixture
def orchestrator():
    """Create mock orchestrator with execute_custom_command."""
    bridge = Mock()
    parser = OutputParser()
    responder = SignalResponder()
    send_signal = AsyncMock()

    # Mock bridge response
    async def mock_read_response():
        yield "Executing command..."
        yield "Command complete!"

    bridge.send_command = AsyncMock()
    bridge.read_response = mock_read_response

    orchestrator = ClaudeOrchestrator(bridge, parser, responder, send_signal)
    return orchestrator


@pytest.fixture
async def custom_commands(registry, orchestrator):
    """Create CustomCommands handler with dependencies."""
    return CustomCommands(registry=registry, orchestrator=orchestrator)


@pytest.mark.asyncio
async def test_end_to_end_custom_command_flow(custom_commands, registry, orchestrator):
    """Test complete flow: list → show → invoke → execute → stream."""
    # Setup: Add test command to registry
    await registry.add_command(
        name="test:cmd",
        file_path="/path/to/test.md",
        metadata={
            "description": "Test command for integration",
            "parameters": ["arg1", "arg2"],
            "usage": "/test:cmd <arg1> <arg2>",
        }
    )

    # Step 1: List commands
    list_response = await custom_commands.handle("thread-123", "/custom list")

    # Verify command appears in list
    assert "test:cmd" in list_response
    assert "Test command for integration" in list_response
    assert "📋" in list_response  # List emoji

    # Step 2: Show command details
    show_response = await custom_commands.handle("thread-123", "/custom show test:cmd")

    # Verify details displayed
    assert "test:cmd" in show_response
    assert "Test command for integration" in show_response
    assert "Parameters:" in show_response
    assert "arg1" in show_response
    assert "arg2" in show_response
    assert "Usage:" in show_response
    assert "/test:cmd <arg1> <arg2>" in show_response
    assert "📄" in show_response  # Show emoji

    # Step 3: Set active session (required for invoke)
    custom_commands.set_active_session("thread-123", "session-456")

    # Step 4: Invoke command
    invoke_response = await custom_commands.handle(
        "thread-123",
        "/custom invoke test:cmd value1 value2"
    )

    # Verify invocation message
    assert "executing" in invoke_response.lower() or "invoked" in invoke_response.lower()
    assert "test:cmd" in invoke_response
    assert "▶️" in invoke_response  # Invoke emoji

    # Step 5: Verify orchestrator.execute_custom_command was called
    orchestrator.bridge.send_command.assert_called_once()
    call_args = orchestrator.bridge.send_command.call_args
    sent_command = call_args[0][0]

    # Verify formatted command sent to bridge
    assert "/test:cmd value1 value2" in sent_command

    # Step 6: Verify response streamed to Signal
    assert orchestrator.send_signal.call_count >= 1


@pytest.mark.asyncio
async def test_command_not_found_flow(custom_commands):
    """Test flow when command doesn't exist."""
    # Try to show non-existent command
    show_response = await custom_commands.handle("thread-123", "/custom show unknown:cmd")
    assert "not found" in show_response.lower()
    assert "unknown:cmd" in show_response

    # Try to invoke non-existent command
    custom_commands.set_active_session("thread-123", "session-789")
    invoke_response = await custom_commands.handle(
        "thread-123",
        "/custom invoke unknown:cmd arg1"
    )
    assert "not found" in invoke_response.lower()


@pytest.mark.asyncio
async def test_invoke_without_session(custom_commands, registry):
    """Test invoke flow without active session."""
    # Add command
    await registry.add_command(
        name="test:cmd",
        file_path="/path/to/test.md",
        metadata={"description": "Test"}
    )

    # Try to invoke without setting session
    response = await custom_commands.handle(
        "thread-123",
        "/custom invoke test:cmd arg1"
    )

    # Should get error about missing session
    assert "session" in response.lower()
    assert "start" in response.lower() or "active" in response.lower()


@pytest.mark.asyncio
async def test_mobile_friendly_formatting_in_flow(custom_commands, registry):
    """Test mobile-friendly formatting throughout flow."""
    # Add command with long name
    long_name = "very:long:command:name:exceeding:mobile:width:limit"
    await registry.add_command(
        name=long_name,
        file_path="/path/to/cmd.md",
        metadata={"description": "Long command test"}
    )

    # List should show truncated name
    list_response = await custom_commands.handle("thread-123", "/custom list")

    # Name should be truncated (30 char limit) in list view
    if len(long_name) > 30:
        assert long_name[:27] + "..." in list_response or long_name[:30] in list_response

    # Show should display full name in details
    show_response = await custom_commands.handle("thread-123", f"/custom show {long_name}")
    assert long_name in show_response  # Full name in details view


@pytest.mark.asyncio
async def test_multiple_commands_flow(custom_commands, registry):
    """Test flow with multiple commands in registry."""
    # Add multiple commands
    commands = [
        ("gsd:plan", "Create project plan"),
        ("gsd:execute", "Execute GSD plan"),
        ("test:unit", "Run unit tests"),
    ]

    for name, description in commands:
        await registry.add_command(
            name=name,
            file_path=f"/path/to/{name}.md",
            metadata={"description": description}
        )

    # List should show all commands
    list_response = await custom_commands.handle("thread-123", "/custom list")

    for name, description in commands:
        assert name in list_response
        assert description in list_response

    # Show each command
    for name, description in commands:
        show_response = await custom_commands.handle("thread-123", f"/custom show {name}")
        assert name in show_response
        assert description in show_response


@pytest.mark.asyncio
async def test_command_execution_streams_responses(custom_commands, registry, orchestrator):
    """Test that command execution properly streams Claude responses."""
    # Setup command
    await registry.add_command(
        name="stream:test",
        file_path="/path/to/stream.md",
        metadata={"description": "Streaming test"}
    )

    # Setup orchestrator with multiple response lines
    async def multi_line_response():
        yield "Starting command..."
        yield "Using Read tool on file.py"
        yield "Using Edit tool on file.py"
        yield "Using Write tool on output.txt"
        yield "Command completed successfully!"

    orchestrator.bridge.read_response = multi_line_response

    # Set active session and invoke
    custom_commands.set_active_session("thread-456", "session-789")
    await custom_commands.handle("thread-456", "/custom invoke stream:test")

    # Verify responses were streamed to Signal
    assert orchestrator.send_signal.call_count >= 1

    # Get all messages sent
    calls = orchestrator.send_signal.call_args_list
    messages = [call[0][1] for call in calls]
    combined = "\n".join(messages)

    # Verify tool emojis present (formatted by responder)
    assert "📖" in combined  # Read
    assert "✏️" in combined  # Edit
    assert "💾" in combined  # Write
