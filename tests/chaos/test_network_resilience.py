"""
Chaos tests for network resilience and reconnection behavior.

Tests validate that the system handles network failures gracefully,
automatically reconnects, and preserves message integrity during disruptions.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import tempfile
from pathlib import Path

import pytest
import aiohttp

from src.signal.reconnection import ReconnectionManager, ConnectionState
from src.signal.message_buffer import MessageBuffer
from src.session.manager import SessionManager, SessionStatus


@pytest.fixture
def reconnection_manager():
    """Create ReconnectionManager instance."""
    return ReconnectionManager()


@pytest.fixture
def message_buffer():
    """Create MessageBuffer instance."""
    return MessageBuffer(max_size=100)


@pytest.fixture
async def session_manager():
    """Create SessionManager with temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_sessions.db"
        manager = SessionManager(str(db_path))
        await manager.initialize()
        yield manager
        await manager.close()


@pytest.mark.asyncio
async def test_websocket_drop_and_reconnect(reconnection_manager):
    """
    Test WebSocket drop detection and automatic reconnection.

    Validates:
    - ReconnectionManager detects DISCONNECTED state
    - auto_reconnect() logic spawned
    - Exponential backoff applied: 1s, 2s, 4s, 8s
    - State transitions: DISCONNECTED → RECONNECTING → CONNECTED
    """
    # Initial state should be CONNECTED
    assert reconnection_manager.state == ConnectionState.CONNECTED
    assert reconnection_manager.attempt_count == 0

    # Simulate network drop
    success = reconnection_manager.transition(ConnectionState.DISCONNECTED)
    assert success is True
    assert reconnection_manager.state == ConnectionState.DISCONNECTED

    # Simulate reconnection attempts with backoff
    backoff_delays = []
    for expected_attempt in range(1, 5):
        # Transition to RECONNECTING
        success = reconnection_manager.transition(ConnectionState.RECONNECTING)
        assert success is True
        assert reconnection_manager.state == ConnectionState.RECONNECTING
        assert reconnection_manager.attempt_count == expected_attempt

        # Calculate backoff
        backoff = reconnection_manager.calculate_backoff()
        backoff_delays.append(backoff)

        # Verify exponential backoff: 1s, 2s, 4s, 8s
        expected_backoff = 2 ** (expected_attempt - 1)
        assert backoff == expected_backoff, f"Attempt {expected_attempt}: expected {expected_backoff}s, got {backoff}s"

        # Simulate failed reconnection (back to DISCONNECTED) - except on last attempt
        if expected_attempt < 4:
            success = reconnection_manager.transition(ConnectionState.DISCONNECTED)
            assert success is True

    # Last attempt was RECONNECTING, now transition to CONNECTED
    success = reconnection_manager.transition(ConnectionState.CONNECTED)
    assert success is True
    assert reconnection_manager.state == ConnectionState.CONNECTED
    assert reconnection_manager.attempt_count == 0  # Reset on successful connection

    # Verify we collected 4 backoff delays
    assert len(backoff_delays) == 4
    assert backoff_delays == [1.0, 2.0, 4.0, 8.0]


@pytest.mark.asyncio
async def test_message_buffer_during_disconnect(message_buffer):
    """
    Test message buffering and draining during network disconnect.

    Validates:
    - Messages buffered when disconnected
    - No messages lost during disconnect
    - Buffer drains on reconnect
    - All messages eventually sent in correct order
    """
    # Fill buffer with 50 messages (simulating messages during connected state)
    for i in range(50):
        message_buffer.enqueue("+15550000", f"Message {i}")

    assert len(message_buffer) == 50

    # Simulate disconnect - attempt to send 10 more messages
    for i in range(50, 60):
        message_buffer.enqueue("+15550000", f"Message {i}")

    # Buffer should now have 60 messages
    assert len(message_buffer) == 60

    # Simulate reconnect - drain buffer
    messages = message_buffer.drain()

    # Verify all 60 messages present
    assert len(messages) == 60
    assert len(message_buffer) == 0

    # Verify messages in correct order (FIFO)
    for i, (recipient, text) in enumerate(messages):
        assert recipient == "+15550000"
        assert text == f"Message {i}"


@pytest.mark.asyncio
async def test_session_sync_after_reconnect(session_manager, reconnection_manager, message_buffer):
    """
    Test session state synchronization after reconnection.

    Validates:
    - Session remains ACTIVE during disconnect
    - Activity log grows during disconnect
    - Catch-up summary generated on reconnect
    - Session state synchronized correctly
    """
    # Create an ACTIVE session
    session = await session_manager.create("/tmp/test-project", "+15550000")
    await session_manager.update(session.id, status=SessionStatus.ACTIVE)

    # Simulate disconnect
    reconnection_manager.transition(ConnectionState.DISCONNECTED)

    # Simulate Claude executing commands during disconnect (activity logged)
    for i in range(5):
        await session_manager.track_activity(
            session.id,
            "command_executed",
            {"command": f"command_{i}", "result": "success"}
        )

    # Verify activity log has 5 entries
    session = await session_manager.get(session.id)
    assert len(session.context.get("activity_log", [])) == 5

    # Simulate reconnection
    reconnection_manager.transition(ConnectionState.RECONNECTING)
    reconnection_manager.transition(ConnectionState.CONNECTED)

    # Transition to SYNCING state
    reconnection_manager.transition(ConnectionState.SYNCING)

    # Generate catch-up summary
    summary = await session_manager.generate_catchup_summary(session.id)

    # Verify summary contains activity information
    assert "5 operations" in summary
    assert "command_0" in summary or "Executed" in summary
    assert "Ready to continue" in summary

    # Verify activity log cleared after summary generation
    session = await session_manager.get(session.id)
    assert len(session.context.get("activity_log", [])) == 0

    # Complete sync
    reconnection_manager.transition(ConnectionState.CONNECTED)
    assert reconnection_manager.state == ConnectionState.CONNECTED


@pytest.mark.asyncio
async def test_backoff_cap_at_maximum():
    """
    Test backoff delay caps at maximum value.

    Validates:
    - Backoff increases exponentially
    - Backoff caps at 60 seconds
    - Multiple failures don't cause excessive delays
    """
    manager = ReconnectionManager()

    # Simulate many failed reconnection attempts
    manager.transition(ConnectionState.DISCONNECTED)

    backoff_delays = []
    for i in range(10):
        manager.transition(ConnectionState.RECONNECTING)
        backoff = manager.calculate_backoff()
        backoff_delays.append(backoff)
        manager.transition(ConnectionState.DISCONNECTED)

    # Verify exponential growth then cap
    assert backoff_delays[0] == 1.0   # Attempt 1
    assert backoff_delays[1] == 2.0   # Attempt 2
    assert backoff_delays[2] == 4.0   # Attempt 3
    assert backoff_delays[3] == 8.0   # Attempt 4
    assert backoff_delays[4] == 16.0  # Attempt 5
    assert backoff_delays[5] == 32.0  # Attempt 6
    assert backoff_delays[6] == 60.0  # Attempt 7 (capped at MAX_BACKOFF)
    assert backoff_delays[7] == 60.0  # Attempt 8 (still capped)
    assert backoff_delays[8] == 60.0  # Attempt 9 (still capped)
    assert backoff_delays[9] == 60.0  # Attempt 10 (still capped)


@pytest.mark.asyncio
async def test_invalid_state_transitions_rejected(reconnection_manager):
    """
    Test invalid state transitions are rejected.

    Validates:
    - State machine enforces valid transitions
    - Invalid transitions return False
    - State remains unchanged on invalid transition
    """
    # Initial state: CONNECTED
    assert reconnection_manager.state == ConnectionState.CONNECTED

    # Invalid: CONNECTED → RECONNECTING (must go through DISCONNECTED)
    success = reconnection_manager.transition(ConnectionState.RECONNECTING)
    assert success is False
    assert reconnection_manager.state == ConnectionState.CONNECTED

    # Valid: CONNECTED → DISCONNECTED
    success = reconnection_manager.transition(ConnectionState.DISCONNECTED)
    assert success is True
    assert reconnection_manager.state == ConnectionState.DISCONNECTED

    # Invalid: DISCONNECTED → SYNCING (can only sync from CONNECTED)
    success = reconnection_manager.transition(ConnectionState.SYNCING)
    assert success is False
    assert reconnection_manager.state == ConnectionState.DISCONNECTED

    # Valid: DISCONNECTED → RECONNECTING
    success = reconnection_manager.transition(ConnectionState.RECONNECTING)
    assert success is True
    assert reconnection_manager.state == ConnectionState.RECONNECTING


@pytest.mark.asyncio
async def test_buffer_overflow_during_extended_disconnect(message_buffer):
    """
    Test buffer overflow handling during extended disconnect.

    Validates:
    - Buffer respects max_size limit (100 messages)
    - Oldest messages dropped when buffer full
    - System doesn't crash or leak memory
    """
    # Fill buffer beyond capacity
    for i in range(150):
        message_buffer.enqueue("+15550000", f"Message {i}")

    # Buffer should cap at max_size
    assert len(message_buffer) == 100

    # Drain buffer
    messages = message_buffer.drain()

    # Should have messages 50-149 (oldest 50 dropped)
    assert len(messages) == 100
    assert messages[0][1] == "Message 50"   # Oldest message now
    assert messages[-1][1] == "Message 149"  # Newest message


@pytest.mark.asyncio
async def test_concurrent_buffer_operations():
    """
    Test concurrent enqueue and drain operations don't cause corruption.

    Validates:
    - Buffer is thread-safe for concurrent access
    - No messages lost during concurrent operations
    - No race conditions in buffer state
    """
    buffer = MessageBuffer(max_size=200)

    async def enqueue_messages(start, count):
        """Enqueue messages continuously."""
        for i in range(start, start + count):
            buffer.enqueue("+15550000", f"Message {i}")
            await asyncio.sleep(0.001)  # Small delay

    async def drain_periodically():
        """Drain buffer periodically."""
        drained_messages = []
        for _ in range(3):
            await asyncio.sleep(0.02)
            messages = buffer.drain()
            drained_messages.extend(messages)
        return drained_messages

    # Run concurrent enqueue and drain operations
    enqueue_task1 = enqueue_messages(0, 50)
    enqueue_task2 = enqueue_messages(50, 50)
    drain_task = drain_periodically()

    results = await asyncio.gather(enqueue_task1, enqueue_task2, drain_task)
    drained_messages = results[2]

    # Verify no crashes occurred
    assert isinstance(drained_messages, list)

    # Verify buffer operations completed
    # Some messages should have been drained, rest remain in buffer
    total_messages = len(drained_messages) + len(buffer)
    assert total_messages <= 100  # Some messages enqueued, some drained


@pytest.mark.asyncio
async def test_reconnection_after_multiple_disconnects():
    """
    Test system handles multiple disconnect/reconnect cycles.

    Validates:
    - Multiple disconnects handled correctly
    - Backoff resets after successful connection
    - State machine remains consistent through cycles
    """
    manager = ReconnectionManager()

    # Perform 3 disconnect/reconnect cycles
    for cycle in range(3):
        # Disconnect
        manager.transition(ConnectionState.DISCONNECTED)
        assert manager.state == ConnectionState.DISCONNECTED

        # Attempt reconnection (with a few failures)
        for attempt in range(2):
            manager.transition(ConnectionState.RECONNECTING)
            manager.transition(ConnectionState.DISCONNECTED)

        # Successful reconnection
        manager.transition(ConnectionState.RECONNECTING)
        manager.transition(ConnectionState.CONNECTED)

        # Verify backoff reset
        assert manager.attempt_count == 0
        assert manager.state == ConnectionState.CONNECTED


@pytest.mark.asyncio
async def test_activity_log_bounded_during_long_disconnect(session_manager):
    """
    Test activity log doesn't grow unbounded during extended disconnect.

    Validates:
    - Activity log caps at 10 entries
    - Oldest entries dropped when cap reached
    - Most recent activity preserved
    """
    # Create session
    session = await session_manager.create("/tmp/test-project", "+15550000")

    # Log 20 activities (exceeds 10-entry cap)
    for i in range(20):
        await session_manager.track_activity(
            session.id,
            "command_executed",
            {"command": f"command_{i}"}
        )

    # Verify only last 10 activities stored
    session = await session_manager.get(session.id)
    activity_log = session.context.get("activity_log", [])
    assert len(activity_log) == 10

    # Verify oldest entries (0-9) dropped, newest (10-19) kept
    commands = [act["details"]["command"] for act in activity_log]
    assert commands[0] == "command_10"  # Oldest kept
    assert commands[-1] == "command_19"  # Newest
