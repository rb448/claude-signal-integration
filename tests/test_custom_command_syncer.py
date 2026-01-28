"""Tests for CommandSyncer."""
import pytest
import asyncio
import time
from pathlib import Path
import tempfile
from unittest.mock import AsyncMock, MagicMock

from src.custom_commands.syncer import CommandSyncer


@pytest.fixture
def temp_agents_dir():
    """Create a temporary agents directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        agents_dir = Path(tmpdir) / "agents"
        agents_dir.mkdir()
        yield agents_dir


@pytest.fixture
def mock_registry():
    """Create a mock registry for testing."""
    registry = AsyncMock()
    registry.add_command = AsyncMock()
    registry.update_command = AsyncMock()
    registry.remove_command = AsyncMock()
    return registry


def test_parse_command_frontmatter(temp_agents_dir):
    """Test parsing command frontmatter from .md file."""
    command_file = temp_agents_dir / "test-cmd.md"
    command_file.write_text("""---
name: test-command
description: A test command
parameters:
  - name: param1
    description: First parameter
  - name: param2
    description: Second parameter
---

# Test Command

This is the command body.
""")

    syncer = CommandSyncer(agents_dir=temp_agents_dir, registry=None)
    metadata = syncer._parse_command_file(command_file)

    assert metadata is not None
    assert metadata["name"] == "test-command"
    assert metadata["description"] == "A test command"
    assert len(metadata["parameters"]) == 2


def test_parse_invalid_frontmatter(temp_agents_dir):
    """Test parsing file with invalid frontmatter returns None."""
    command_file = temp_agents_dir / "invalid.md"
    command_file.write_text("# No frontmatter here\n\nJust content.")

    syncer = CommandSyncer(agents_dir=temp_agents_dir, registry=None)
    metadata = syncer._parse_command_file(command_file)

    # Should return None or empty dict for invalid frontmatter
    assert metadata is None or not metadata


def test_parse_missing_name(temp_agents_dir):
    """Test parsing file without name field returns None."""
    command_file = temp_agents_dir / "no-name.md"
    command_file.write_text("""---
description: Missing name field
---

# Command
""")

    syncer = CommandSyncer(agents_dir=temp_agents_dir, registry=None)
    metadata = syncer._parse_command_file(command_file)

    # Should return None if required 'name' field is missing
    assert metadata is None


def test_ignore_non_md_files(temp_agents_dir):
    """Test that non-.md files are ignored."""
    # Create various non-.md files
    (temp_agents_dir / "test.txt").write_text("text file")
    (temp_agents_dir / "test.py").write_text("# python file")
    (temp_agents_dir / "test.json").write_text('{"key": "value"}')

    syncer = CommandSyncer(agents_dir=temp_agents_dir, registry=None)

    # Parse each file
    assert syncer._parse_command_file(temp_agents_dir / "test.txt") is None
    assert syncer._parse_command_file(temp_agents_dir / "test.py") is None
    assert syncer._parse_command_file(temp_agents_dir / "test.json") is None


@pytest.mark.asyncio
async def test_initial_scan(temp_agents_dir, mock_registry):
    """Test initial scan loads existing commands."""
    # Create test command files
    (temp_agents_dir / "cmd1.md").write_text("""---
name: cmd1
description: First command
---
""")
    (temp_agents_dir / "cmd2.md").write_text("""---
name: cmd2
description: Second command
---
""")
    (temp_agents_dir / "cmd3.md").write_text("""---
name: cmd3
description: Third command
---
""")

    # Create non-.md file (should be ignored)
    (temp_agents_dir / "readme.txt").write_text("Not a command")

    syncer = CommandSyncer(agents_dir=temp_agents_dir, registry=mock_registry)
    await syncer.initial_scan()

    # Verify registry.add_command was called 3 times (not 4)
    assert mock_registry.add_command.call_count == 3

    # Verify each command was added with correct data
    calls = mock_registry.add_command.call_args_list
    command_names = [call.kwargs.get("name") or call.args[0] for call in calls]
    assert "cmd1" in command_names
    assert "cmd2" in command_names
    assert "cmd3" in command_names


@pytest.mark.asyncio
async def test_detect_new_command(temp_agents_dir, mock_registry):
    """Test that syncer detects and adds new command files."""
    loop = asyncio.get_running_loop()
    syncer = CommandSyncer(agents_dir=temp_agents_dir, registry=mock_registry)
    syncer.start(loop=loop)

    try:
        # Create a new command file
        command_file = temp_agents_dir / "new-cmd.md"
        command_file.write_text("""---
name: new-command
description: A new command
---
""")

        # Give watchdog time to detect the change and process event
        await asyncio.sleep(0.3)

        # Verify add_command was called
        mock_registry.add_command.assert_called()

        # Verify it was called with the correct command name
        calls = mock_registry.add_command.call_args_list
        command_names = [call.kwargs.get("name") or call.args[0] for call in calls]
        assert "new-command" in command_names

    finally:
        syncer.stop()


@pytest.mark.asyncio
async def test_detect_modified_command(temp_agents_dir, mock_registry):
    """Test that syncer detects and updates modified command files."""
    loop = asyncio.get_running_loop()

    # Create initial command
    command_file = temp_agents_dir / "mod-cmd.md"
    command_file.write_text("""---
name: mod-command
description: Original description
---
""")

    syncer = CommandSyncer(agents_dir=temp_agents_dir, registry=mock_registry)
    syncer.start(loop=loop)

    try:
        # Modify the command file
        command_file.write_text("""---
name: mod-command
description: Updated description
---
""")

        # Give watchdog time to detect the change
        await asyncio.sleep(0.3)

        # Verify add_command was called (updates use add with idempotent behavior)
        mock_registry.add_command.assert_called()

        # Verify the updated description was passed
        calls = mock_registry.add_command.call_args_list
        # Find the call with mod-command
        command_names = [call.kwargs.get("name") or call.args[0] for call in calls]
        assert "mod-command" in command_names

    finally:
        syncer.stop()


@pytest.mark.asyncio
async def test_detect_deleted_command(temp_agents_dir, mock_registry):
    """Test that syncer detects and removes deleted command files."""
    loop = asyncio.get_running_loop()

    # Create initial command
    command_file = temp_agents_dir / "del-cmd.md"
    command_file.write_text("""---
name: del-command
description: To be deleted
---
""")

    syncer = CommandSyncer(agents_dir=temp_agents_dir, registry=mock_registry)
    syncer.start(loop=loop)

    try:
        # Delete the command file
        command_file.unlink()

        # Give watchdog time to detect the change
        await asyncio.sleep(0.3)

        # Verify remove_command was called
        mock_registry.remove_command.assert_called()

        # Verify it was called with the correct command name
        calls = mock_registry.remove_command.call_args_list
        command_names = [call.kwargs.get("name") or call.args[0] for call in calls]
        assert "del-cmd" in command_names  # Filename stem is "del-cmd"

    finally:
        syncer.stop()


@pytest.mark.asyncio
async def test_syncer_creates_agents_dir_if_missing(mock_registry):
    """Test that syncer creates ~/.claude/agents/ if it doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        agents_dir = Path(tmpdir) / "nonexistent" / "agents"
        assert not agents_dir.exists()

        syncer = CommandSyncer(agents_dir=agents_dir, registry=mock_registry)
        await syncer.initial_scan()

        assert agents_dir.exists()
