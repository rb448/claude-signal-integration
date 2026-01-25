"""Unit tests for message queue."""

import asyncio

import pytest

from src.signal.queue import MessageQueue


class TestMessageQueue:
    """Test MessageQueue FIFO behavior and overflow handling."""

    @pytest.mark.asyncio
    async def test_fifo_ordering(self):
        """Test messages are processed in FIFO order."""
        queue = MessageQueue()
        results = []

        async def processor(message):
            """Collect messages in order."""
            results.append(message)

        # Add messages A, B, C
        await queue.put("A")
        await queue.put("B")
        await queue.put("C")

        # Process queue for short time
        task = asyncio.create_task(queue.process_queue(processor))
        await asyncio.sleep(0.1)  # Let it process
        queue.stop_processing()
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        # Verify FIFO order: A, B, C
        assert results == ["A", "B", "C"], f"Expected FIFO order A,B,C but got {results}"

    @pytest.mark.asyncio
    async def test_queue_overflow_drops_oldest(self):
        """Test queue overflow drops oldest messages."""
        queue = MessageQueue(max_size=3)  # Small queue for testing

        # Fill to max
        await queue.put("msg1")
        await queue.put("msg2")
        await queue.put("msg3")
        assert queue.size == 3

        # Overflow: should drop msg1 and add msg4
        await queue.put("msg4")
        assert queue.size == 3

        # Process and verify msg1 was dropped
        results = []

        async def processor(message):
            results.append(message)

        task = asyncio.create_task(queue.process_queue(processor))
        await asyncio.sleep(0.1)
        queue.stop_processing()
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        # Should have msg2, msg3, msg4 (msg1 dropped)
        assert "msg1" not in results, "msg1 should have been dropped"
        assert "msg4" in results, "msg4 should have been added"

    @pytest.mark.asyncio
    async def test_multiple_puts_dont_block(self):
        """Test multiple puts don't block each other."""
        queue = MessageQueue()

        # Put multiple messages rapidly
        start = asyncio.get_event_loop().time()
        await asyncio.gather(
            queue.put("1"),
            queue.put("2"),
            queue.put("3"),
            queue.put("4"),
            queue.put("5")
        )
        elapsed = asyncio.get_event_loop().time() - start

        # Should complete quickly (< 0.1 seconds) since puts don't block
        assert elapsed < 0.1, f"Puts took {elapsed}s, should be nearly instant"
        assert queue.size == 5

    @pytest.mark.asyncio
    async def test_queue_size_property(self):
        """Test queue size property returns correct count."""
        queue = MessageQueue()

        assert queue.size == 0

        await queue.put("msg1")
        assert queue.size == 1

        await queue.put("msg2")
        await queue.put("msg3")
        assert queue.size == 3

    @pytest.mark.asyncio
    async def test_processing_flag(self):
        """Test is_processing flag reflects queue state."""
        queue = MessageQueue()

        assert not queue.is_processing

        async def dummy_processor(msg):
            await asyncio.sleep(0.01)

        await queue.put("msg")
        task = asyncio.create_task(queue.process_queue(dummy_processor))
        await asyncio.sleep(0.05)  # Let it start

        assert queue.is_processing

        queue.stop_processing()
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        await asyncio.sleep(0.05)  # Let it stop
        assert not queue.is_processing
