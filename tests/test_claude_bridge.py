"""
Tests for CLIBridge stdin/stdout communication with Claude Code CLI.

TDD RED Phase: Write failing tests first.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, Mock
from src.claude.bridge import CLIBridge


@pytest.mark.asyncio
async def test_send_command():
    """Test sending command to Claude Code CLI stdin."""
    # Create mock process with stdin
    mock_process = MagicMock()
    mock_stdin = AsyncMock()
    mock_process.stdin = mock_stdin
    mock_process.returncode = None

    bridge = CLIBridge(mock_process)

    # Send command
    await bridge.send_command("help me debug this")

    # Verify command written to stdin with newline
    mock_stdin.write.assert_called_once_with(b"help me debug this\n")
    mock_stdin.drain.assert_called_once()


@pytest.mark.asyncio
async def test_read_response():
    """Test reading response from Claude Code CLI stdout."""
    # Create mock process with stdout
    mock_process = MagicMock()
    mock_stdout = AsyncMock()
    mock_process.stdout = mock_stdout
    mock_process.returncode = None

    # Mock readline to return response lines then empty
    mock_stdout.readline.side_effect = [
        b"Response line 1\n",
        b"Response line 2\n",
        b"",  # Empty means EOF or prompt
    ]

    bridge = CLIBridge(mock_process)

    # Read response
    lines = []
    async for line in bridge.read_response():
        lines.append(line)

    # Verify lines read correctly
    assert lines == ["Response line 1", "Response line 2"]


@pytest.mark.asyncio
async def test_is_connected_when_running():
    """Test is_connected returns True when process is running."""
    mock_process = MagicMock()
    mock_process.returncode = None  # Still running

    bridge = CLIBridge(mock_process)

    assert bridge.is_connected is True


@pytest.mark.asyncio
async def test_is_connected_when_stopped():
    """Test is_connected returns False when process has exited."""
    mock_process = MagicMock()
    mock_process.returncode = 0  # Exited

    bridge = CLIBridge(mock_process)

    assert bridge.is_connected is False


@pytest.mark.asyncio
async def test_send_command_encodes_utf8():
    """Test send_command properly encodes UTF-8 characters."""
    mock_process = MagicMock()
    mock_stdin = AsyncMock()
    mock_process.stdin = mock_stdin
    mock_process.returncode = None

    bridge = CLIBridge(mock_process)

    # Send command with unicode
    await bridge.send_command("help with émojis 🚀")

    # Verify UTF-8 encoding
    expected = "help with émojis 🚀\n".encode('utf-8')
    mock_stdin.write.assert_called_once_with(expected)


@pytest.mark.asyncio
async def test_read_response_decodes_utf8():
    """Test read_response properly decodes UTF-8 bytes."""
    mock_process = MagicMock()
    mock_stdout = AsyncMock()
    mock_process.stdout = mock_stdout
    mock_process.returncode = None

    # Mock readline with UTF-8 encoded response
    response = "Response with émojis 🎉\n".encode('utf-8')
    mock_stdout.readline.side_effect = [response, b""]

    bridge = CLIBridge(mock_process)

    lines = []
    async for line in bridge.read_response():
        lines.append(line)

    assert lines == ["Response with émojis 🎉"]
