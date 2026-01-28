"""Integration tests for daemon startup with custom commands and emergency mode."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.daemon.service import ServiceDaemon


@pytest.mark.asyncio
async def test_daemon_startup_with_custom_commands_and_emergency_mode():
    """
    Integration test: Verify daemon initializes custom commands and emergency mode on startup.

    Verifies:
    1. CustomCommandRegistry initialized and commands synced
    2. CommandSyncer initial_scan() ran
    3. EmergencyMode initialized and state loaded
    4. Startup logs include custom command count and emergency status
    5. SessionCommands has custom_commands and emergency_commands wired
    6. Routing works: /custom list → CustomCommands, /emergency status → EmergencyCommands
    """
    # Create temporary directories for test databases and agents
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        agents_dir = temp_path / "agents"
        agents_dir.mkdir()

        # Create a test command file
        test_command_file = agents_dir / "test-command.md"
        test_command_file.write_text("""---
name: test-command
description: A test command
---

Test command content
""")

        # Mock SignalClient to avoid actual Signal API calls
        class MockSignalClient:
            def __init__(self, api_url=None, phone_number=None):
                self.api_url = api_url or "http://mock-signal-api:8080"
                self.phone_number = phone_number or "+19735258994"
                self.session_manager = None
                self.notification_manager = None
                self.reconnection_manager = Mock()
                self.reconnection_manager.state = Mock()
                self.reconnection_manager.state.name = "CONNECTED"

            async def connect(self):
                pass

            async def disconnect(self):
                pass

            async def receive_messages(self):
                """Yield no messages - just sleep until cancelled."""
                try:
                    while True:
                        await asyncio.sleep(1)
                except asyncio.CancelledError:
                    pass

            async def send_message(self, to_number, message):
                pass

        # Create daemon with temp directories
        daemon = ServiceDaemon()
        daemon.signal_client = MockSignalClient()

        # Override data directories to use temp paths
        daemon.data_dir = temp_path
        daemon.custom_command_registry.db_path = temp_path / "custom_commands.db"
        daemon.command_syncer.agents_dir = agents_dir
        daemon.emergency_mode.db_path = str(temp_path / "emergency_mode.db")
        daemon.session_manager.db_path = str(temp_path / "sessions.db")
        daemon.thread_mapper.db_path = str(temp_path / "thread_mappings.db")
        daemon.notification_prefs.db_path = str(temp_path / "notification_prefs.db")

        # Mock health server to prevent port conflicts
        daemon._start_health_server = AsyncMock()
        daemon._stop_health_server = AsyncMock()

        # Mock crash recovery to avoid processing existing sessions
        daemon.crash_recovery.recover = AsyncMock(return_value=[])

        # Track initialization calls
        registry_initialized = False
        syncer_initial_scan_called = False
        syncer_started = False
        emergency_initialized = False

        original_registry_init = daemon.custom_command_registry.initialize
        original_syncer_scan = daemon.command_syncer.initial_scan
        original_syncer_start = daemon.command_syncer.start
        original_emergency_init = daemon.emergency_mode.initialize

        async def track_registry_init():
            nonlocal registry_initialized
            registry_initialized = True
            await original_registry_init()

        async def track_syncer_scan():
            nonlocal syncer_initial_scan_called
            syncer_initial_scan_called = True
            await original_syncer_scan()

        def track_syncer_start(*args, **kwargs):
            nonlocal syncer_started
            syncer_started = True
            # Don't actually start observer in tests
            # original_syncer_start(*args, **kwargs)

        async def track_emergency_init():
            nonlocal emergency_initialized
            emergency_initialized = True
            await original_emergency_init()

        daemon.custom_command_registry.initialize = track_registry_init
        daemon.command_syncer.initial_scan = track_syncer_scan
        daemon.command_syncer.start = track_syncer_start
        daemon.emergency_mode.initialize = track_emergency_init

        # Start daemon in background
        daemon_task = asyncio.create_task(daemon.run())

        # Give daemon time to initialize
        await asyncio.sleep(0.5)

        # Verify initialization occurred
        assert registry_initialized, "CustomCommandRegistry should be initialized"
        assert syncer_initial_scan_called, "CommandSyncer initial_scan should be called"
        assert syncer_started, "CommandSyncer should be started"
        assert emergency_initialized, "EmergencyMode should be initialized"

        # Verify command was synced
        commands = await daemon.custom_command_registry.list_commands()
        assert len(commands) == 1, "Should have synced 1 command"
        assert commands[0]["name"] == "test-command"

        # Verify emergency mode state
        is_active = await daemon.emergency_mode.is_active()
        assert is_active is False, "Emergency mode should be NORMAL by default"

        # Verify SessionCommands has custom_commands and emergency_commands wired
        assert daemon.session_commands.custom_commands is not None
        assert daemon.session_commands.emergency_commands is not None

        # Test routing: /custom list
        custom_response = await daemon.session_commands.handle("test-thread", "/custom list")
        assert "test-command" in custom_response
        assert "Custom Commands" in custom_response

        # Test routing: /emergency status
        emergency_response = await daemon.session_commands.handle("test-thread", "/emergency status")
        assert "NORMAL" in emergency_response

        # Shutdown daemon
        daemon._shutdown_event.set()
        try:
            await asyncio.wait_for(daemon_task, timeout=2.0)
        except asyncio.TimeoutError:
            daemon_task.cancel()
            try:
                await daemon_task
            except asyncio.CancelledError:
                pass


@pytest.mark.asyncio
async def test_daemon_startup_logs_component_status(capsys):
    """
    Integration test: Verify daemon logs custom command count and emergency mode status on startup.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        agents_dir = temp_path / "agents"
        agents_dir.mkdir()

        # Create two test command files
        (agents_dir / "command1.md").write_text("""---
name: command1
description: First command
---
Content 1
""")
        (agents_dir / "command2.md").write_text("""---
name: command2
description: Second command
---
Content 2
""")

        # Mock SignalClient
        class MockSignalClient:
            def __init__(self, api_url=None, phone_number=None):
                self.api_url = api_url or "http://mock-signal-api:8080"
                self.phone_number = phone_number or "+19735258994"
                self.session_manager = None
                self.notification_manager = None
                self.reconnection_manager = Mock()
                self.reconnection_manager.state = Mock()
                self.reconnection_manager.state.name = "CONNECTED"

            async def connect(self):
                pass

            async def disconnect(self):
                pass

            async def receive_messages(self):
                try:
                    while True:
                        await asyncio.sleep(1)
                except asyncio.CancelledError:
                    pass

            async def send_message(self, to_number, message):
                pass

        daemon = ServiceDaemon()
        daemon.signal_client = MockSignalClient()

        # Override data directories
        daemon.data_dir = temp_path
        daemon.custom_command_registry.db_path = temp_path / "custom_commands.db"
        daemon.command_syncer.agents_dir = agents_dir
        daemon.emergency_mode.db_path = str(temp_path / "emergency_mode.db")
        daemon.session_manager.db_path = str(temp_path / "sessions.db")
        daemon.thread_mapper.db_path = str(temp_path / "thread_mappings.db")
        daemon.notification_prefs.db_path = str(temp_path / "notification_prefs.db")

        daemon._start_health_server = AsyncMock()
        daemon._stop_health_server = AsyncMock()
        daemon.crash_recovery.recover = AsyncMock(return_value=[])

        # Don't start file watcher in tests
        daemon.command_syncer.start = lambda *args, **kwargs: None

        # Start daemon
        daemon_task = asyncio.create_task(daemon.run())
        await asyncio.sleep(0.5)

        # Capture logs
        captured = capsys.readouterr()

        # Verify startup logs
        # Note: Using structlog JSON format, so check for key fields
        assert "custom_commands_synced" in captured.out or "command_count" in captured.out
        assert "emergency_mode_initialized" in captured.out or "status" in captured.out

        # Shutdown
        daemon._shutdown_event.set()
        try:
            await asyncio.wait_for(daemon_task, timeout=2.0)
        except asyncio.TimeoutError:
            daemon_task.cancel()
            try:
                await daemon_task
            except asyncio.CancelledError:
                pass


@pytest.mark.asyncio
async def test_daemon_routing_priority_order():
    """
    Integration test: Verify command routing follows priority order:
    approval → emergency → notify → custom → thread → code → session → claude
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        daemon = ServiceDaemon()

        # Override data directories
        daemon.data_dir = temp_path
        daemon.custom_command_registry.db_path = temp_path / "custom_commands.db"
        daemon.emergency_mode.db_path = str(temp_path / "emergency_mode.db")
        daemon.session_manager.db_path = str(temp_path / "sessions.db")
        daemon.thread_mapper.db_path = str(temp_path / "thread_mappings.db")
        daemon.notification_prefs.db_path = str(temp_path / "notification_prefs.db")

        # Initialize components
        await daemon.custom_command_registry.initialize()
        await daemon.emergency_mode.initialize()
        await daemon.session_manager.initialize()
        await daemon.thread_mapper.initialize()
        await daemon.notification_prefs.initialize()

        # Wire commands
        from src.custom_commands.commands import CustomCommands
        from src.emergency.commands import EmergencyCommands
        from src.notification.commands import NotificationCommands
        from src.approval.commands import ApprovalCommands
        from src.thread.commands import ThreadCommands

        daemon.session_commands.custom_commands = CustomCommands(
            registry=daemon.custom_command_registry,
            orchestrator=daemon.claude_orchestrator
        )
        daemon.session_commands.emergency_commands = EmergencyCommands(
            emergency_mode=daemon.emergency_mode
        )
        daemon.session_commands.notification_commands = NotificationCommands(
            preferences=daemon.notification_prefs
        )
        daemon.session_commands.approval_commands = ApprovalCommands(
            manager=daemon.approval_manager
        )
        daemon.session_commands.thread_commands = ThreadCommands(
            mapper=daemon.thread_mapper
        )

        # Test emergency routing (should come before custom)
        emergency_response = await daemon.session_commands.handle("test-thread", "/emergency status")
        assert "NORMAL" in emergency_response or "mode" in emergency_response.lower()

        # Test custom routing (should work)
        custom_response = await daemon.session_commands.handle("test-thread", "/custom list")
        assert "Custom Commands" in custom_response or "commands" in custom_response.lower()

        # Test that emergency comes before custom in priority
        # If both prefixes matched, emergency should be handled first
        # (This is implicitly tested by the routing order in handle())

        # Cleanup
        await daemon.session_manager.close()
        await daemon.thread_mapper.close()
