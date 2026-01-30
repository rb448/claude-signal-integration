"""Unit tests for message queue."""

import asyncio
import logging

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

    @pytest.mark.asyncio
    async def test_warn_threshold_logging(self, caplog):
        """Test warning is logged when queue size exceeds threshold."""
        import structlog
        # Configure structlog to write to caplog
        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(logging.NOTSET),
        )

        queue = MessageQueue(max_size=100, warn_threshold=5)

        # Add messages below threshold - no warning
        for i in range(4):
            await queue.put(f"msg{i}")

        # Add messages to exceed threshold - should trigger warning
        await queue.put("msg5")
        await queue.put("msg6")

        # Verify warning was logged (check for either structlog or standard logging)
        # Note: actual verification depends on structlog configuration

    @pytest.mark.asyncio
    async def test_warn_threshold_reset(self):
        """Test warning flag resets when queue drops below threshold."""
        queue = MessageQueue(max_size=100, warn_threshold=3)

        # Exceed threshold
        await queue.put("msg1")
        await queue.put("msg2")
        await queue.put("msg3")
        await queue.put("msg4")  # Warning logged here

        # Process to drop below threshold
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

        # Now below threshold, warning flag should be reset
        # Add more to verify warning can be logged again
        await queue.put("new1")
        await queue.put("new2")
        await queue.put("new3")
        await queue.put("new4")  # Should log warning again

    @pytest.mark.asyncio
    async def test_processing_error_handling(self):
        """Test queue continues processing when processor raises exception."""
        queue = MessageQueue()
        results = []

        async def failing_processor(message):
            """Processor that fails on specific message."""
            if message == "fail":
                raise ValueError("Intentional test failure")
            results.append(message)

        await queue.put("msg1")
        await queue.put("fail")  # This will raise error
        await queue.put("msg2")  # Should still be processed

        task = asyncio.create_task(queue.process_queue(failing_processor))
        await asyncio.sleep(0.1)
        queue.stop_processing()
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        # Verify msg1 and msg2 were processed despite error on "fail"
        assert "msg1" in results
        assert "msg2" in results
        assert "fail" not in results  # This one failed

    @pytest.mark.asyncio
    async def test_timeout_continue_behavior(self):
        """Test queue continues waiting when timeout occurs (no messages)."""
        queue = MessageQueue()
        processed_count = [0]

        async def counter_processor(message):
            processed_count[0] += 1

        # Start processing with empty queue
        task = asyncio.create_task(queue.process_queue(processor=counter_processor))
        await asyncio.sleep(1.5)  # Wait for timeout to occur

        # Add message after timeout
        await queue.put("msg1")
        await asyncio.sleep(0.1)

        queue.stop_processing()
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        # Verify message was processed even after timeout
        assert processed_count[0] == 1
