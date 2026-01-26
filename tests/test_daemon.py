"""Tests for daemon service."""

import asyncio

import pytest

from src.daemon.service import ServiceDaemon


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
        def __init__(self):
            self.api_url = "ws://mock-signal-api:8080"

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
