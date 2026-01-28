"""Tests for CustomCommands handler following TDD RED-GREEN-REFACTOR cycle.

RED Phase: Write failing tests for CustomCommands.
"""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from src.custom_commands.commands import CustomCommands
from src.custom_commands.registry import CustomCommandRegistry
from src.claude.orchestrator import ClaudeOrchestrator


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
    """Create mock orchestrator."""
    orchestrator = MagicMock(spec=ClaudeOrchestrator)
    orchestrator.execute_custom_command = AsyncMock()
    return orchestrator


@pytest.fixture
async def custom_commands(registry, orchestrator):
    """Create CustomCommands handler with test dependencies."""
    return CustomCommands(registry=registry, orchestrator=orchestrator)


@pytest.mark.asyncio
async def test_handle_list(custom_commands, registry):
    """Test /custom list returns formatted list of commands."""
    # Add test commands to registry
    await registry.add_command(
        name="gsd:plan",
        file_path="/path/to/plan.md",
        metadata={
            "description": "Create project plan from context",
            "parameters": ["context"],
        }
    )
    await registry.add_command(
        name="test:cmd",
        file_path="/path/to/test.md",
        metadata={
            "description": "Run test suite",
            "parameters": [],
        }
    )

    # Execute /custom list
    response = await custom_commands.handle("thread123", "/custom list")

    # Verify formatted list with emoji
    assert "📋 gsd:plan" in response
    assert "Create project plan from context" in response
    assert "📋 test:cmd" in response
    assert "Run test suite" in response


@pytest.mark.asyncio
async def test_handle_list_empty(custom_commands):
    """Test /custom list with no commands returns helpful message."""
    response = await custom_commands.handle("thread123", "/custom list")
    assert "no custom commands" in response.lower()


@pytest.mark.asyncio
async def test_handle_show(custom_commands, registry):
    """Test /custom show returns command details."""
    # Add test command
    await registry.add_command(
        name="gsd:plan",
        file_path="/path/to/plan.md",
        metadata={
            "description": "Create project plan from context",
            "parameters": ["context", "scope"],
            "usage": "/gsd:plan <context> [scope]",
        }
    )

    # Execute /custom show
    response = await custom_commands.handle("thread123", "/custom show gsd:plan")

    # Verify command details displayed
    assert "gsd:plan" in response
    assert "Create project plan from context" in response
    assert "Parameters:" in response
    assert "context" in response
    assert "scope" in response
    assert "Usage:" in response
    assert "/gsd:plan <context> [scope]" in response


@pytest.mark.asyncio
async def test_handle_show_not_found(custom_commands):
    """Test /custom show with unknown command returns 'not found' message."""
    response = await custom_commands.handle("thread123", "/custom show unknown")
    assert "not found" in response.lower()
    assert "unknown" in response


@pytest.mark.asyncio
async def test_handle_show_missing_name(custom_commands):
    """Test /custom show without command name returns error."""
    response = await custom_commands.handle("thread123", "/custom show")
    assert "usage" in response.lower() or "missing" in response.lower()


@pytest.mark.asyncio
async def test_handle_invoke(custom_commands, registry, orchestrator):
    """Test /custom invoke executes command via orchestrator."""
    # Add test command
    await registry.add_command(
        name="gsd:plan",
        file_path="/path/to/plan.md",
        metadata={"description": "Create plan"}
    )

    # Set active session
    custom_commands.set_active_session("thread123", "session123")

    # Execute /custom invoke
    response = await custom_commands.handle("thread123", "/custom invoke gsd:plan arg1 arg2")

    # Verify orchestrator called
    orchestrator.execute_custom_command.assert_called_once()
    call_args = orchestrator.execute_custom_command.call_args
    assert call_args[1]["command_name"] == "gsd:plan"
    assert call_args[1]["args"] == "arg1 arg2"
    assert call_args[1]["thread_id"] == "thread123"

    # Verify success message
    assert "executing" in response.lower() or "invoked" in response.lower()


@pytest.mark.asyncio
async def test_handle_invoke_requires_session(custom_commands, registry):
    """Test /custom invoke returns error if no active session."""
    # Add test command
    await registry.add_command(
        name="test:cmd",
        file_path="/path/to/test.md",
        metadata={"description": "Test"}
    )

    # Do NOT set active session

    # Execute /custom invoke
    response = await custom_commands.handle("thread123", "/custom invoke test:cmd arg1")

    # Verify error about missing session
    assert "session" in response.lower()
    assert "start" in response.lower() or "active" in response.lower()


@pytest.mark.asyncio
async def test_handle_invoke_not_found(custom_commands):
    """Test /custom invoke with unknown command returns 'not found'."""
    custom_commands.set_active_session("thread123", "session123")

    response = await custom_commands.handle("thread123", "/custom invoke unknown arg1")
    assert "not found" in response.lower()
    assert "unknown" in response


@pytest.mark.asyncio
async def test_handle_invoke_missing_name(custom_commands):
    """Test /custom invoke without command name returns error."""
    custom_commands.set_active_session("thread123", "session123")

    response = await custom_commands.handle("thread123", "/custom invoke")
    assert "usage" in response.lower() or "missing" in response.lower()


@pytest.mark.asyncio
async def test_handle_help(custom_commands):
    """Test /custom help returns usage instructions."""
    response = await custom_commands.handle("thread123", "/custom help")

    # Verify help content
    assert "/custom list" in response
    assert "/custom show" in response
    assert "/custom invoke" in response
    assert "usage" in response.lower() or "available" in response.lower()


@pytest.mark.asyncio
async def test_unknown_subcommand(custom_commands):
    """Test /custom with unknown subcommand returns help text."""
    response = await custom_commands.handle("thread123", "/custom unknown")

    # Should return help text
    assert "/custom list" in response or "usage" in response.lower()


@pytest.mark.asyncio
async def test_mobile_friendly_formatting(custom_commands, registry):
    """Test command names are truncated for mobile display."""
    # Add command with very long name
    long_name = "very:long:command:name:that:exceeds:mobile:width"
    await registry.add_command(
        name=long_name,
        file_path="/path/to/cmd.md",
        metadata={"description": "Long command"}
    )

    response = await custom_commands.handle("thread123", "/custom list")

    # Long names should be truncated (30 char limit)
    if len(long_name) > 30:
        assert long_name[:27] + "..." in response or long_name[:30] in response


@pytest.mark.asyncio
async def test_set_active_session(custom_commands):
    """Test set_active_session stores session mapping."""
    custom_commands.set_active_session("thread123", "session456")

    # Verify session stored (implementation will check this in invoke)
    assert hasattr(custom_commands, '_active_sessions')
    assert custom_commands._active_sessions.get("thread123") == "session456"


@pytest.mark.asyncio
async def test_clear_active_session(custom_commands):
    """Test clear_active_session removes session mapping."""
    custom_commands.set_active_session("thread123", "session456")
    custom_commands.clear_active_session("thread123")

    # Verify session cleared
    assert custom_commands._active_sessions.get("thread123") is None
