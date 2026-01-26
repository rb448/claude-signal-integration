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
            yield mock_message
            # Exit after one message to prevent infinite loop
            await asyncio.sleep(0.1)

        async def send_message(self, to_number, message):
            pass

    daemon = ServiceDaemon()
    daemon.signal_client = MockSignalClient()

    # Run daemon for short duration
    async def run_briefly():
        try:
            async with asyncio.timeout(0.5):
                await daemon.run()
        except asyncio.TimeoutError:
            pass  # Expected - daemon runs forever, we stop it with timeout

    await run_briefly()

    # Verify message was enqueued
    assert daemon.message_queue.size > 0, "Message should be in queue"

    # Verify it's the message we sent
    queued_msg = await daemon.message_queue._queue.get()
    assert queued_msg["envelope"]["source"] == "+15551234567"
    assert queued_msg["envelope"]["dataMessage"]["message"] == "test command"
