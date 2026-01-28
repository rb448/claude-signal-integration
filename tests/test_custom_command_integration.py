"""Integration tests for CustomCommandRegistry and CommandSyncer."""
import pytest
import asyncio
import tempfile
from pathlib import Path

from src.custom_commands.registry import CustomCommandRegistry
from src.custom_commands.syncer import CommandSyncer


@pytest.mark.asyncio
async def test_syncer_registry_integration_create():
    """Test that file creation updates registry."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup
        agents_dir = Path(tmpdir) / "agents"
        agents_dir.mkdir()
        db_path = Path(tmpdir) / "commands.db"

        registry = CustomCommandRegistry(db_path)
        await registry.initialize()

        syncer = CommandSyncer(agents_dir=agents_dir, registry=registry)
        loop = asyncio.get_running_loop()
        syncer.start(loop=loop)

        try:
            # Create a command file
            command_file = agents_dir / "test-cmd.md"
            command_file.write_text("""---
name: test-command
description: A test command
parameters:
  - name: param1
    description: First parameter
---

# Test Command
This is the body.
""")

            # Wait for watchdog to process
            await asyncio.sleep(0.3)

            # Verify command is in registry
            command = await registry.get_command("test-command")
            assert command is not None
            assert command["name"] == "test-command"
            assert command["metadata"]["description"] == "A test command"
            assert len(command["metadata"]["parameters"]) == 1

        finally:
            syncer.stop()


@pytest.mark.asyncio
async def test_syncer_registry_integration_modify():
    """Test that file modification updates registry."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup
        agents_dir = Path(tmpdir) / "agents"
        agents_dir.mkdir()
        db_path = Path(tmpdir) / "commands.db"

        registry = CustomCommandRegistry(db_path)
        await registry.initialize()

        # Create initial command
        command_file = agents_dir / "mod-cmd.md"
        command_file.write_text("""---
name: modify-test
description: Original description
version: 1.0
---
""")

        syncer = CommandSyncer(agents_dir=agents_dir, registry=registry)
        loop = asyncio.get_running_loop()
        syncer.start(loop=loop)

        try:
            # Wait for initial detection
            await asyncio.sleep(0.3)

            # Verify initial state
            command = await registry.get_command("modify-test")
            assert command["metadata"]["description"] == "Original description"
            assert command["metadata"]["version"] == 1.0  # YAML parses as float

            # Modify the file
            command_file.write_text("""---
name: modify-test
description: Updated description
version: 2.0
---
""")

            # Wait for modification detection
            await asyncio.sleep(0.3)

            # Verify updated state
            command = await registry.get_command("modify-test")
            assert command["metadata"]["description"] == "Updated description"
            assert command["metadata"]["version"] == 2.0  # YAML parses as float

        finally:
            syncer.stop()


@pytest.mark.asyncio
async def test_syncer_registry_integration_delete():
    """Test that file deletion removes from registry."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup
        agents_dir = Path(tmpdir) / "agents"
        agents_dir.mkdir()
        db_path = Path(tmpdir) / "commands.db"

        registry = CustomCommandRegistry(db_path)
        await registry.initialize()

        # Create initial command
        command_file = agents_dir / "delete-test.md"
        command_file.write_text("""---
name: delete-test
description: To be deleted
---
""")

        syncer = CommandSyncer(agents_dir=agents_dir, registry=registry)
        loop = asyncio.get_running_loop()
        syncer.start(loop=loop)

        try:
            # Wait for initial detection
            await asyncio.sleep(0.3)

            # Verify command exists
            assert await registry.command_exists("delete-test")

            # Delete the file
            command_file.unlink()

            # Wait for deletion detection
            await asyncio.sleep(0.3)

            # Verify command removed
            assert not await registry.command_exists("delete-test")
            assert await registry.get_command("delete-test") is None

        finally:
            syncer.stop()


@pytest.mark.asyncio
async def test_syncer_registry_integration_initial_scan():
    """Test initial scan loads existing commands into registry."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup
        agents_dir = Path(tmpdir) / "agents"
        agents_dir.mkdir()
        db_path = Path(tmpdir) / "commands.db"

        # Create command files before syncer starts
        (agents_dir / "cmd1.md").write_text("""---
name: command-one
description: First command
---
""")
        (agents_dir / "cmd2.md").write_text("""---
name: command-two
description: Second command
---
""")
        (agents_dir / "cmd3.md").write_text("""---
name: command-three
description: Third command
---
""")

        # Create non-.md file (should be ignored)
        (agents_dir / "readme.txt").write_text("Not a command")

        registry = CustomCommandRegistry(db_path)
        await registry.initialize()

        syncer = CommandSyncer(agents_dir=agents_dir, registry=registry)

        # Run initial scan
        await syncer.initial_scan()

        # Verify all commands loaded
        commands = await registry.list_commands()
        assert len(commands) == 3

        command_names = [cmd["name"] for cmd in commands]
        assert "command-one" in command_names
        assert "command-two" in command_names
        assert "command-three" in command_names

        # Verify metadata preserved
        cmd1 = await registry.get_command("command-one")
        assert cmd1["metadata"]["description"] == "First command"


@pytest.mark.asyncio
async def test_syncer_registry_integration_persistence():
    """Test that syncer updates persist across registry restarts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup
        agents_dir = Path(tmpdir) / "agents"
        agents_dir.mkdir()
        db_path = Path(tmpdir) / "commands.db"

        # First session: sync commands
        registry1 = CustomCommandRegistry(db_path)
        await registry1.initialize()

        command_file = agents_dir / "persist.md"
        command_file.write_text("""---
name: persistent-command
description: Should persist
---
""")

        syncer1 = CommandSyncer(agents_dir=agents_dir, registry=registry1)
        await syncer1.initial_scan()

        # Verify command exists in first session
        cmd = await registry1.get_command("persistent-command")
        assert cmd is not None

        # Second session: new registry instance
        registry2 = CustomCommandRegistry(db_path)
        await registry2.initialize()

        # Verify command persisted
        cmd = await registry2.get_command("persistent-command")
        assert cmd is not None
        assert cmd["name"] == "persistent-command"
        assert cmd["metadata"]["description"] == "Should persist"
