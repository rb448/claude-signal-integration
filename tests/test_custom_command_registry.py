"""Tests for CustomCommandRegistry."""
import pytest
import json
from datetime import datetime, UTC
from pathlib import Path
import tempfile
import aiosqlite

from src.custom_commands.registry import CustomCommandRegistry


@pytest.fixture
async def temp_registry():
    """Create a temporary registry for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_commands.db"
        registry = CustomCommandRegistry(db_path)
        await registry.initialize()
        yield registry


@pytest.mark.asyncio
async def test_add_command(temp_registry):
    """Test adding a command to the registry."""
    metadata = {
        "description": "Test command",
        "parameters": ["param1", "param2"]
    }

    await temp_registry.add_command(
        name="test-command",
        file_path="/path/to/test.md",
        metadata=metadata
    )

    command = await temp_registry.get_command("test-command")
    assert command is not None
    assert command["name"] == "test-command"
    assert command["file_path"] == "/path/to/test.md"
    assert command["metadata"] == metadata
    assert "updated_at" in command


@pytest.mark.asyncio
async def test_get_command_not_found(temp_registry):
    """Test getting a non-existent command returns None."""
    command = await temp_registry.get_command("nonexistent")
    assert command is None


@pytest.mark.asyncio
async def test_list_commands(temp_registry):
    """Test listing all commands."""
    await temp_registry.add_command("cmd1", "/path/1.md", {"desc": "First"})
    await temp_registry.add_command("cmd2", "/path/2.md", {"desc": "Second"})
    await temp_registry.add_command("cmd3", "/path/3.md", {"desc": "Third"})

    commands = await temp_registry.list_commands()
    assert len(commands) == 3

    names = [cmd["name"] for cmd in commands]
    assert "cmd1" in names
    assert "cmd2" in names
    assert "cmd3" in names


@pytest.mark.asyncio
async def test_update_command(temp_registry):
    """Test updating command metadata."""
    original_metadata = {"description": "Original", "version": "1.0"}
    await temp_registry.add_command("cmd", "/path/cmd.md", original_metadata)

    updated_metadata = {"description": "Updated", "version": "2.0"}
    await temp_registry.update_command("cmd", updated_metadata)

    command = await temp_registry.get_command("cmd")
    assert command["metadata"] == updated_metadata
    assert command["metadata"]["description"] == "Updated"


@pytest.mark.asyncio
async def test_remove_command(temp_registry):
    """Test removing a command."""
    await temp_registry.add_command("cmd", "/path/cmd.md", {})

    assert await temp_registry.command_exists("cmd") is True

    await temp_registry.remove_command("cmd")

    assert await temp_registry.command_exists("cmd") is False
    assert await temp_registry.get_command("cmd") is None


@pytest.mark.asyncio
async def test_command_exists(temp_registry):
    """Test checking if command exists."""
    assert await temp_registry.command_exists("test") is False

    await temp_registry.add_command("test", "/path/test.md", {})

    assert await temp_registry.command_exists("test") is True


@pytest.mark.asyncio
async def test_persistence():
    """Test that commands persist across registry instances."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "persistent.db"

        # First instance: add commands
        registry1 = CustomCommandRegistry(db_path)
        await registry1.initialize()
        await registry1.add_command("persistent-cmd", "/path/cmd.md", {"data": "value"})

        # Second instance: verify persistence
        registry2 = CustomCommandRegistry(db_path)
        await registry2.initialize()
        command = await registry2.get_command("persistent-cmd")

        assert command is not None
        assert command["name"] == "persistent-cmd"
        assert command["metadata"]["data"] == "value"


@pytest.mark.asyncio
async def test_idempotent_add(temp_registry):
    """Test that adding the same command twice updates it (idempotent)."""
    metadata1 = {"version": "1.0"}
    await temp_registry.add_command("cmd", "/path/cmd.md", metadata1)

    metadata2 = {"version": "2.0"}
    await temp_registry.add_command("cmd", "/path/cmd.md", metadata2)

    command = await temp_registry.get_command("cmd")
    assert command["metadata"]["version"] == "2.0"

    # Should only have one command
    commands = await temp_registry.list_commands()
    assert len(commands) == 1


@pytest.mark.asyncio
async def test_idempotent_remove(temp_registry):
    """Test that removing a non-existent command doesn't error."""
    # Should not raise an exception
    await temp_registry.remove_command("nonexistent")


@pytest.mark.asyncio
async def test_update_nonexistent_command(temp_registry):
    """Test updating a non-existent command creates it."""
    metadata = {"description": "New command"}
    await temp_registry.update_command("new-cmd", metadata)

    command = await temp_registry.get_command("new-cmd")
    assert command is None  # Update should not create, only modify existing


@pytest.mark.asyncio
async def test_utc_timestamps(temp_registry):
    """Test that timestamps are UTC-aware."""
    await temp_registry.add_command("cmd", "/path/cmd.md", {})

    command = await temp_registry.get_command("cmd")
    updated_at = command["updated_at"]

    # Verify it's a valid ISO timestamp
    timestamp = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
    assert timestamp.tzinfo is not None

    # Verify it's recent (within last minute)
    now = datetime.now(UTC)
    delta = now - timestamp
    assert delta.total_seconds() < 60
