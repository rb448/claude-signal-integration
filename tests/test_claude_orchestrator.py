"""Tests for ClaudeOrchestrator - end-to-end command flow."""

import pytest
from unittest.mock import AsyncMock, Mock, call
from src.claude.orchestrator import ClaudeOrchestrator
from src.claude.parser import OutputParser, ToolCall, Progress, Error, Response
from src.claude.responder import SignalResponder


@pytest.mark.asyncio
async def test_execute_command():
    """Test basic command execution flow."""
    # Arrange
    bridge = Mock()
    parser = OutputParser()
    responder = SignalResponder()
    send_signal = AsyncMock()

    # Mock bridge to return simple response
    async def mock_read_response():
        yield "Analyzing your request..."
        yield "Using Read tool on file.py"
        yield "Here's the analysis"

    bridge.send_command = AsyncMock()
    bridge.read_response = mock_read_response

    orchestrator = ClaudeOrchestrator(bridge, parser, responder, send_signal)

    # Act
    await orchestrator.execute_command("help me debug", "session-123")

    # Assert
    bridge.send_command.assert_called_once_with("help me debug")

    # Verify messages were sent to Signal
    assert send_signal.call_count >= 1

    # Verify at least one message was sent
    calls = send_signal.call_args_list
    messages = [call[0][1] for call in calls]  # Extract message text

    # Should contain formatted output
    assert any("📖" in msg for msg in messages)  # Tool call emoji


@pytest.mark.asyncio
async def test_stream_output():
    """Test streaming output with batching."""
    # Arrange
    bridge = Mock()
    parser = OutputParser()
    responder = SignalResponder()
    send_signal = AsyncMock()

    # Mock multiple lines of output
    async def mock_read_response():
        yield "Analyzing code..."
        yield "Using Read tool on src/main.py"
        yield "Using Edit tool on src/main.py"
        yield "Writing changes..."
        yield "Done!"

    bridge.send_command = AsyncMock()
    bridge.read_response = mock_read_response

    orchestrator = ClaudeOrchestrator(bridge, parser, responder, send_signal)

    # Act
    await orchestrator.execute_command("fix the bug", "session-456")

    # Assert
    assert send_signal.call_count >= 1

    # Verify tool calls were formatted
    calls = send_signal.call_args_list
    messages = [call[0][1] for call in calls]
    combined = "\n".join(messages)

    assert "📖" in combined  # Read tool
    assert "✏️" in combined  # Edit tool


@pytest.mark.asyncio
async def test_handle_error():
    """Test error handling in command execution."""
    # Arrange
    bridge = Mock()
    parser = OutputParser()
    responder = SignalResponder()
    send_signal = AsyncMock()

    # Mock error output
    async def mock_read_response():
        yield "Analyzing..."
        yield "Error: File not found: missing.py"

    bridge.send_command = AsyncMock()
    bridge.read_response = mock_read_response

    orchestrator = ClaudeOrchestrator(bridge, parser, responder, send_signal)

    # Act
    await orchestrator.execute_command("read missing.py", "session-789")

    # Assert
    calls = send_signal.call_args_list
    messages = [call[0][1] for call in calls]
    combined = "\n".join(messages)

    # Should contain error formatting
    assert "❌" in combined or "Error" in combined


@pytest.mark.asyncio
async def test_command_with_tool_calls():
    """Test command that makes multiple tool calls."""
    # Arrange
    bridge = Mock()
    parser = OutputParser()
    responder = SignalResponder()
    send_signal = AsyncMock()

    # Mock output with multiple tools
    async def mock_read_response():
        yield "Using Read tool on config.py"
        yield "Using Grep tool on *.py"
        yield "Using Write tool on output.txt"
        yield "Running: pytest tests/"
        yield "All tests passed!"

    bridge.send_command = AsyncMock()
    bridge.read_response = mock_read_response

    orchestrator = ClaudeOrchestrator(bridge, parser, responder, send_signal)

    # Act
    await orchestrator.execute_command("run tests", "session-abc")

    # Assert
    calls = send_signal.call_args_list
    messages = [call[0][1] for call in calls]
    combined = "\n".join(messages)

    # Verify all tool emojis present
    assert "📖" in combined  # Read
    assert "🔍" in combined  # Grep
    assert "💾" in combined  # Write
    assert "🔧" in combined  # Bash


@pytest.mark.asyncio
async def test_bridge_exception_handling():
    """Test handling of CLIBridge exceptions."""
    # Arrange
    bridge = Mock()
    parser = OutputParser()
    responder = SignalResponder()
    send_signal = AsyncMock()

    # Mock bridge to raise exception
    bridge.send_command = AsyncMock(side_effect=ValueError("stdin not available"))

    orchestrator = ClaudeOrchestrator(bridge, parser, responder, send_signal)

    # Act
    await orchestrator.execute_command("test command", "session-err")

    # Assert - should send error message to Signal
    assert send_signal.call_count >= 1
    calls = send_signal.call_args_list
    messages = [call[0][1] for call in calls]
    combined = "\n".join(messages)

    # Should contain error about bridge failure
    assert "error" in combined.lower() or "❌" in combined
