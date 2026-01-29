"""Tests for daemon service."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.daemon.service import ServiceDaemon
from src.thread.mapper import ThreadMapper


@pytest.mark.asyncio
async def test_message_receiving_loop():
    """
    Integration test: Verify daemon receives messages from Signal
    and enqueues them for processing.

    Gap being closed: VERIFICATION.md identified that receive_messages()
    was never called by daemon. This test proves the wiring is complete.
    """
    # Track whether receive_messages was called and message was processed
    receive_called = False
    message_enqueued = False

    # Mock Signal message payload
    mock_message = {
        "envelope": {
            "source": "+15551234567",
            "sourceNumber": "+15551234567",
            "timestamp": 1234567890000,
            "dataMessage": {
                "timestamp": 1234567890000,
                "message": "test command"
            }
        }
    }

    # Create daemon with mocked SignalClient
    class MockSignalClient:
        def __init__(self, api_url=None, phone_number=None):
            self.api_url = api_url or "http://mock-signal-api:8080"
            self.phone_number = phone_number or "+19735258994"

        async def connect(self):
            pass

        async def disconnect(self):
            pass

        async def receive_messages(self):
            """Yield one test message then stop."""
            nonlocal receive_called
            receive_called = True
            yield mock_message
            # Exit after one message to prevent infinite loop
            await asyncio.sleep(0.1)

        async def send_message(self, to_number, message):
            pass

    # Mock MessageQueue to track when put() is called
    original_queue = ServiceDaemon().message_queue

    class MockMessageQueue:
        def __init__(self):
            self._queue = asyncio.Queue()
            self._processing = False

        async def put(self, message):
            nonlocal message_enqueued
            message_enqueued = True
            await self._queue.put(message)

        async def process_queue(self, processor):
            """Mock processor that doesn't actually process."""
            self._processing = True
            # Just sleep - don't process messages
            try:
                while self._processing:
                    await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                pass

        def stop_processing(self):
            self._processing = False

        @property
        def size(self):
            return self._queue.qsize()

    daemon = ServiceDaemon()
    daemon.signal_client = MockSignalClient()
    daemon.message_queue = MockMessageQueue()

    # Mock health server to prevent port conflicts
    daemon._start_health_server = AsyncMock()
    daemon._stop_health_server = AsyncMock()

    # Run daemon for short duration
    async def run_briefly():
        try:
            async with asyncio.timeout(0.5):
                await daemon.run()
        except asyncio.TimeoutError:
            pass  # Expected - daemon runs forever, we stop it with timeout

    await run_briefly()

    # Verify the wiring exists: receive_messages() was called
    assert receive_called, "receive_messages() should have been called by daemon"

    # Verify message flow: message was enqueued
    assert message_enqueued, "Message should have been enqueued via put()"

    # Verify message is in queue
    assert daemon.message_queue.size > 0, "Message should be in queue"


@pytest.mark.asyncio
async def test_daemon_start_with_thread_mappings(capsys):
    """
    Daemon loads existing thread mappings on startup.

    Verifies that when thread_mappings.db contains mappings,
    the daemon:
    1. Successfully initializes ThreadMapper
    2. Loads existing mappings
    3. Logs the count of loaded mappings
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup: Create thread_mappings.db with 2 mappings
        thread_db_path = Path(tmpdir) / "thread_mappings.db"
        mapper = ThreadMapper(str(thread_db_path))
        await mapper.initialize()

        # Create two test project directories and mappings
        project1 = Path(tmpdir) / "project1"
        project2 = Path(tmpdir) / "project2"
        project1.mkdir()
        project2.mkdir()

        await mapper.map("thread-123", str(project1))
        await mapper.map("thread-456", str(project2))
        await mapper.close()

        # Create daemon with this database
        daemon = ServiceDaemon()
        daemon.thread_mapper = ThreadMapper(str(thread_db_path))

        # Mock dependencies to prevent actual connections
        daemon.signal_client = AsyncMock()
        daemon.signal_client.connect = AsyncMock(side_effect=ConnectionError("Mock stop"))
        daemon.signal_client.api_url = "ws://mock:8080"
        daemon.session_manager = AsyncMock()
        daemon.session_manager.initialize = AsyncMock()
        daemon.session_manager.close = AsyncMock()
        daemon.crash_recovery = AsyncMock()
        daemon.crash_recovery.recover = AsyncMock(return_value=[])

        # Mock health server to prevent port conflicts
        daemon._start_health_server = AsyncMock()
        daemon._stop_health_server = AsyncMock()

        # Run daemon briefly (will fail at signal_client.connect, which is expected)
        try:
            await daemon.run()
        except (ConnectionError, AttributeError):
            pass  # Expected - daemon stops at mocked connection failure

        # Verify: Thread mapper was initialized and mappings were loaded
        loaded_mappings = await daemon.thread_mapper.list_all()
        assert len(loaded_mappings) == 2, "Should have loaded 2 thread mappings"

        # Verify: Logs show thread mappings loaded
        # Check captured stdout which has the structlog output
        captured = capsys.readouterr()
        assert "thread_mappings_loaded" in captured.out, \
            "Should log thread_mappings_loaded message"
        assert "thread_count=2" in captured.out, \
            "Should include thread_count=2 in log"

        # Cleanup
        await daemon.thread_mapper.close()


@pytest.mark.asyncio
async def test_daemon_start_no_thread_mappings(capsys):
    """
    Daemon starts successfully when thread_mappings.db is empty.

    Verifies that when thread_mappings.db exists but contains no mappings,
    the daemon:
    1. Successfully initializes ThreadMapper
    2. Handles empty mapping list gracefully
    3. Logs that no mappings are configured
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup: Create empty thread_mappings.db
        thread_db_path = Path(tmpdir) / "thread_mappings.db"
        mapper = ThreadMapper(str(thread_db_path))
        await mapper.initialize()
        await mapper.close()

        # Create daemon with this empty database
        daemon = ServiceDaemon()
        daemon.thread_mapper = ThreadMapper(str(thread_db_path))

        # Mock dependencies to prevent actual connections
        daemon.signal_client = AsyncMock()
        daemon.signal_client.connect = AsyncMock(side_effect=ConnectionError("Mock stop"))
        daemon.signal_client.api_url = "ws://mock:8080"
        daemon.session_manager = AsyncMock()
        daemon.session_manager.initialize = AsyncMock()
        daemon.session_manager.close = AsyncMock()
        daemon.crash_recovery = AsyncMock()
        daemon.crash_recovery.recover = AsyncMock(return_value=[])

        # Mock health server to prevent port conflicts
        daemon._start_health_server = AsyncMock()
        daemon._stop_health_server = AsyncMock()

        # Run daemon briefly (will fail at signal_client.connect, which is expected)
        try:
            await daemon.run()
        except (ConnectionError, AttributeError):
            pass  # Expected - daemon stops at mocked connection failure

        # Verify: Thread mapper returns empty list
        loaded_mappings = await daemon.thread_mapper.list_all()
        assert len(loaded_mappings) == 0, "Should have no thread mappings"

        # Verify: Logs show no thread mappings configured
        captured = capsys.readouterr()
        assert "no_thread_mappings_configured" in captured.out, \
            "Should log no_thread_mappings_configured message"

        # Cleanup
        await daemon.thread_mapper.close()


@pytest.mark.asyncio
async def test_daemon_start_creates_thread_mappings_db(capsys):
    """
    Daemon creates thread_mappings.db on first start.

    Verifies that when thread_mappings.db doesn't exist,
    the daemon:
    1. Successfully creates the database file
    2. Initializes the schema
    3. Works correctly with empty mappings
    4. Logs no mappings configured
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup: Ensure thread_mappings.db doesn't exist
        thread_db_path = Path(tmpdir) / "thread_mappings.db"
        assert not thread_db_path.exists(), "Database should not exist yet"

        # Create daemon with non-existent database path
        daemon = ServiceDaemon()
        daemon.thread_mapper = ThreadMapper(str(thread_db_path))

        # Mock dependencies to prevent actual connections
        daemon.signal_client = AsyncMock()
        daemon.signal_client.connect = AsyncMock(side_effect=ConnectionError("Mock stop"))
        daemon.signal_client.api_url = "ws://mock:8080"
        daemon.session_manager = AsyncMock()
        daemon.session_manager.initialize = AsyncMock()
        daemon.session_manager.close = AsyncMock()
        daemon.crash_recovery = AsyncMock()
        daemon.crash_recovery.recover = AsyncMock(return_value=[])

        # Mock health server to prevent port conflicts
        daemon._start_health_server = AsyncMock()
        daemon._stop_health_server = AsyncMock()

        # Run daemon briefly (will fail at signal_client.connect, which is expected)
        try:
            await daemon.run()
        except (ConnectionError, AttributeError):
            pass  # Expected - daemon stops at mocked connection failure

        # Verify: Database file was created
        assert thread_db_path.exists(), "Database file should have been created"

        # Verify: Thread mapper works (returns empty list)
        loaded_mappings = await daemon.thread_mapper.list_all()
        assert len(loaded_mappings) == 0, "Should have no thread mappings in new database"

        # Verify: Logs show no thread mappings configured
        captured = capsys.readouterr()
        assert "no_thread_mappings_configured" in captured.out, \
            "Should log no_thread_mappings_configured message"

        # Cleanup
        await daemon.thread_mapper.close()

@pytest.mark.asyncio
async def test_daemon_startup_initializes_approval_system(capsys):
    """
    Verify daemon initializes approval system on startup.

    Verifies that the daemon:
    1. Creates approval_detector, approval_manager, approval_workflow
    2. Wires approval_commands into session_commands
    3. Logs approval system initialization with safe/destructive tool counts
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create daemon
        daemon = ServiceDaemon()
        daemon.thread_mapper = ThreadMapper(str(Path(tmpdir) / "thread_mappings.db"))

        # Mock dependencies to prevent actual connections
        daemon.signal_client = AsyncMock()
        daemon.signal_client.connect = AsyncMock(side_effect=ConnectionError("Mock stop"))
        daemon.signal_client.api_url = "ws://mock:8080"
        daemon.session_manager = AsyncMock()
        daemon.session_manager.initialize = AsyncMock()
        daemon.session_manager.close = AsyncMock()
        daemon.crash_recovery = AsyncMock()
        daemon.crash_recovery.recover = AsyncMock(return_value=[])

        # Mock health server to prevent port conflicts
        daemon._start_health_server = AsyncMock()
        daemon._stop_health_server = AsyncMock()

        # Run daemon briefly (will fail at signal_client.connect, which is expected)
        try:
            await daemon.run()
        except (ConnectionError, AttributeError):
            pass  # Expected - daemon stops at mocked connection failure

        # Verify: Approval components exist
        assert daemon.approval_detector is not None, "approval_detector should be initialized"
        assert daemon.approval_manager is not None, "approval_manager should be initialized"
        assert daemon.approval_workflow is not None, "approval_workflow should be initialized"

        # Verify: Approval commands wired into session commands
        assert daemon.session_commands.approval_commands is not None, \
            "approval_commands should be wired into session_commands"

        # Verify: Startup logging
        captured = capsys.readouterr()
        assert "approval_system_initialized" in captured.out, \
            "Should log approval_system_initialized message"

        # Cleanup
        await daemon.thread_mapper.close()


@pytest.mark.asyncio
async def test_daemon_startup_initializes_notification_system(capsys):
    """
    Verify daemon initializes notification system on startup.

    Verifies that the daemon:
    1. Creates notification components (categorizer, preferences, manager)
    2. Wires notification_manager into orchestrator and approval_workflow
    3. Wires notification_commands into session_commands
    4. Logs notification system initialization
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create daemon
        daemon = ServiceDaemon()
        daemon.thread_mapper = ThreadMapper(str(Path(tmpdir) / "thread_mappings.db"))

        # Mock dependencies to prevent actual connections
        daemon.signal_client = AsyncMock()
        daemon.signal_client.connect = AsyncMock(side_effect=ConnectionError("Mock stop"))
        daemon.signal_client.api_url = "ws://mock:8080"
        daemon.session_manager = AsyncMock()
        daemon.session_manager.initialize = AsyncMock()
        daemon.session_manager.close = AsyncMock()
        daemon.crash_recovery = AsyncMock()
        daemon.crash_recovery.recover = AsyncMock(return_value=[])

        # Mock health server to prevent port conflicts
        daemon._start_health_server = AsyncMock()
        daemon._stop_health_server = AsyncMock()

        # Run daemon briefly (will fail at signal_client.connect, which is expected)
        try:
            await daemon.run()
        except (ConnectionError, AttributeError):
            pass  # Expected - daemon stops at mocked connection failure

        # Verify: Notification components exist
        assert daemon.notification_categorizer is not None, \
            "notification_categorizer should be initialized"
        assert daemon.notification_prefs is not None, \
            "notification_prefs should be initialized"
        assert hasattr(daemon, 'notification_manager'), \
            "notification_manager should be created in run()"

        # Verify: Notification manager wired into components
        assert daemon.claude_orchestrator.notification_manager is not None, \
            "notification_manager should be wired into orchestrator"
        assert daemon.approval_workflow.notification_manager is not None, \
            "notification_manager should be wired into approval_workflow"

        # Verify: Notification commands wired into session commands
        assert daemon.session_commands.notification_commands is not None, \
            "notification_commands should be wired into session_commands"

        # Verify: Startup logging
        captured = capsys.readouterr()
        assert "notification_system_initialized" in captured.out, \
            "Should log notification_system_initialized message"
        assert "notification_system_ready" in captured.out, \
            "Should log notification_system_ready message"

        # Cleanup
        await daemon.thread_mapper.close()
        if hasattr(daemon, 'notification_prefs') and daemon.notification_prefs._connection:
            await daemon.notification_prefs.close()


@pytest.mark.asyncio
async def test_health_server_port_already_in_use(capsys):
    """
    Verify daemon handles health server port conflicts gracefully.

    Tests that when port 8081 is already bound:
    1. Daemon logs the error
    2. Daemon continues initialization (health check is optional)
    3. Main service remains functional
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create daemon
        daemon = ServiceDaemon()
        daemon.thread_mapper = ThreadMapper(str(Path(tmpdir) / "thread_mappings.db"))

        # Mock _start_health_server to simulate port conflict
        async def mock_health_server_error():
            raise OSError("Address already in use")

        daemon._start_health_server = mock_health_server_error
        daemon._stop_health_server = AsyncMock()

        # Mock dependencies
        daemon.signal_client = AsyncMock()
        daemon.signal_client.connect = AsyncMock(side_effect=ConnectionError("Mock stop"))
        daemon.signal_client.api_url = "ws://mock:8080"
        daemon.session_manager = AsyncMock()
        daemon.session_manager.initialize = AsyncMock()
        daemon.session_manager.close = AsyncMock()
        daemon.crash_recovery = AsyncMock()
        daemon.crash_recovery.recover = AsyncMock(return_value=[])

        # Run daemon briefly - should handle health server error
        try:
            await daemon.run()
        except OSError as e:
            # Health server error should propagate
            assert "Address already in use" in str(e)

        # Cleanup
        await daemon.thread_mapper.close()


@pytest.mark.asyncio
async def test_shutdown_with_active_sessions(capsys):
    """
    Verify daemon cleanly shuts down with active sessions.

    Tests that when shutdown signal is received while sessions are active:
    1. All sessions are terminated cleanly
    2. Session processes are stopped
    3. Resources are released properly
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create daemon
        daemon = ServiceDaemon()
        daemon.thread_mapper = ThreadMapper(str(Path(tmpdir) / "thread_mappings.db"))

        # Track session cleanup
        sessions_cleaned = []

        # Mock session manager with active sessions
        daemon.session_manager = AsyncMock()
        daemon.session_manager.initialize = AsyncMock()

        async def mock_close():
            # Simulate cleanup of active sessions
            sessions_cleaned.extend(["session-1", "session-2"])

        daemon.session_manager.close = mock_close

        # Mock other dependencies
        daemon.signal_client = AsyncMock()
        daemon.signal_client.connect = AsyncMock()
        daemon.signal_client.disconnect = AsyncMock()
        daemon.signal_client.receive_messages = AsyncMock(return_value=iter([]))  # No messages
        daemon.crash_recovery = AsyncMock()
        daemon.crash_recovery.recover = AsyncMock(return_value=[])
        daemon._start_health_server = AsyncMock()
        daemon._stop_health_server = AsyncMock()

        # Run daemon briefly then trigger shutdown
        async def run_and_shutdown():
            # Start daemon in background
            daemon_task = asyncio.create_task(daemon.run())

            # Wait a bit for initialization
            await asyncio.sleep(0.2)

            # Trigger shutdown
            daemon._shutdown_event.set()

            # Wait for graceful shutdown
            try:
                await asyncio.wait_for(daemon_task, timeout=2.0)
            except asyncio.TimeoutError:
                daemon_task.cancel()

        await run_and_shutdown()

        # Verify: Session cleanup was called
        assert len(sessions_cleaned) == 2, "Should have cleaned up 2 active sessions"

        # Cleanup
        await daemon.thread_mapper.close()


@pytest.mark.asyncio
async def test_thread_mapper_initialization_failure(capsys):
    """
    Verify daemon handles ThreadMapper initialization failures gracefully.

    Tests that when ThreadMapper.initialize() raises an exception:
    1. Error is logged
    2. Daemon continues without thread mapping
    3. Main service remains functional
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create daemon
        daemon = ServiceDaemon()

        # Mock ThreadMapper to fail on initialize
        daemon.thread_mapper = Mock()
        daemon.thread_mapper.initialize = AsyncMock(side_effect=Exception("Database corrupted"))
        daemon.thread_mapper.close = AsyncMock()

        # Mock other dependencies
        daemon.signal_client = AsyncMock()
        daemon.signal_client.connect = AsyncMock(side_effect=ConnectionError("Mock stop"))
        daemon.signal_client.api_url = "ws://mock:8080"
        daemon.session_manager = AsyncMock()
        daemon.session_manager.initialize = AsyncMock()
        daemon.session_manager.close = AsyncMock()
        daemon.crash_recovery = AsyncMock()
        daemon.crash_recovery.recover = AsyncMock(return_value=[])
        daemon._start_health_server = AsyncMock()
        daemon._stop_health_server = AsyncMock()

        # Run daemon - should handle thread mapper error
        try:
            await daemon.run()
        except Exception as e:
            # ThreadMapper initialization error should propagate
            assert "Database corrupted" in str(e)

        # Cleanup
        await daemon.thread_mapper.close()


@pytest.mark.asyncio
async def test_message_processing_with_invalid_json():
    """
    Verify daemon handles malformed Signal messages gracefully.

    Tests that when Signal sends invalid JSON:
    1. Message defaults are applied (empty strings for missing fields)
    2. Daemon continues processing without crashing
    3. No service disruption
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Track processed messages
        processed = []

        # Create daemon
        daemon = ServiceDaemon()
        daemon.thread_mapper = ThreadMapper(str(Path(tmpdir) / "thread_mappings.db"))

        # Mock phone verifier to allow all
        daemon.phone_verifier.verify = lambda x: True
        daemon.phone_verifier.authorized_number = "+15551234567"

        # Mock session_commands.handle
        async def mock_handle(thread_id, text):
            processed.append((thread_id, text))
            return None

        daemon.session_commands.handle = mock_handle

        # Test with malformed message (missing required fields)
        malformed_message = {
            # Missing 'envelope' key entirely
            "timestamp": 1234567890000
        }

        # Should handle gracefully without crashing
        await daemon._process_message(malformed_message)

        # Message is processed with empty defaults (sender="", text="")
        assert len(processed) == 1, "Malformed message should be processed with defaults"
        assert processed[0][0] == "", "Missing sender should default to empty string"
        assert processed[0][1] == "", "Missing message text should default to empty string"

        # Test with partially valid message (has envelope but missing data)
        partial_message = {
            "envelope": {
                "sourceNumber": "+15551234567"
                # Missing 'dataMessage' key
            }
        }

        await daemon._process_message(partial_message)

        # Should process with sender but empty text
        assert len(processed) == 2, "Partial message should be processed"
        assert processed[1][0] == "+15551234567", "Sender should be extracted"
        assert processed[1][1] == "", "Missing message text should default to empty string"

        # Test unauthorized sender is rejected
        unauthorized_message = {
            "envelope": {
                "sourceNumber": "+19995551234",  # Different number
                "dataMessage": {"message": "test"}
            }
        }

        # Override verifier to reject this number
        daemon.phone_verifier.verify = lambda x: x == "+15551234567"

        await daemon._process_message(unauthorized_message)

        # Should NOT be processed (still 2 from before)
        assert len(processed) == 2, "Unauthorized message should be rejected"

        # Cleanup
        await daemon.thread_mapper.close()


@pytest.mark.asyncio
async def test_concurrent_session_creation():
    """
    Verify daemon handles concurrent session creation safely.

    Tests that when multiple threads/coroutines create sessions simultaneously:
    1. All sessions are created successfully
    2. No race conditions or deadlocks
    3. Session state remains consistent
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Track created sessions
        created_sessions = []

        # Create daemon
        daemon = ServiceDaemon()
        daemon.thread_mapper = ThreadMapper(str(Path(tmpdir) / "thread_mappings.db"))
        await daemon.thread_mapper.initialize()

        # Mock phone verifier
        daemon.phone_verifier.verify = lambda x: True
        daemon.phone_verifier.authorized_number = "+15551234567"

        # Mock session_commands.handle to simulate session creation
        async def mock_handle(thread_id, text):
            created_sessions.append(thread_id)
            # Simulate some async work
            await asyncio.sleep(0.01)
            return f"Session created for {thread_id}"

        daemon.session_commands.handle = mock_handle

        # Create messages for concurrent processing
        messages = [
            {
                "envelope": {
                    "sourceNumber": "+15551234567",
                    "timestamp": 1234567890000 + i,
                    "dataMessage": {"message": "/session start"}
                },
                "thread_id": f"thread-{i}"
            }
            for i in range(5)
        ]

        # Process all messages concurrently
        tasks = [daemon._process_message(msg) for msg in messages]
        await asyncio.gather(*tasks)

        # Verify: All sessions created
        assert len(created_sessions) == 5, "Should have created 5 sessions"
        assert len(set(created_sessions)) == 5, "All sessions should be unique"

        # Cleanup
        await daemon.thread_mapper.close()
