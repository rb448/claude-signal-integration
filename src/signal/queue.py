"""Async message queue for Signal message buffering."""

import asyncio
import logging
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)


class MessageQueue:
    """Async-safe message queue with overflow handling.

    Buffers incoming messages for sequential processing with FIFO ordering.
    Prevents message loss during burst traffic by queuing with overflow protection.
    """

    def __init__(self, max_size: int = 1000, warn_threshold: int = 100) -> None:
        """Initialize message queue.

        Args:
            max_size: Maximum queue size before oldest messages are dropped (default: 1000)
            warn_threshold: Queue size that triggers warning log (default: 100)
        """
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        self._max_size = max_size
        self._warn_threshold = warn_threshold
        self._processing = False
        self._warn_logged = False

    async def put(self, message: Any) -> None:
        """Add message to queue for processing.

        Args:
            message: Message to add to queue (any type)

        Note:
            If queue is full, oldest message is dropped and new message added.
            Logs warning when queue size exceeds warn_threshold.
        """
        current_size = self._queue.qsize()

        # Warn if queue is getting large
        if current_size >= self._warn_threshold and not self._warn_logged:
            logger.warning(
                "message_queue_high",
                queue_size=current_size,
                threshold=self._warn_threshold,
                max_size=self._max_size
            )
            self._warn_logged = True
        elif current_size < self._warn_threshold:
            self._warn_logged = False

        # Handle overflow by dropping oldest message
        if self._queue.full():
            try:
                dropped = self._queue.get_nowait()
                logger.warning(
                    "message_queue_overflow",
                    dropped_message=dropped,
                    queue_size=self._max_size
                )
            except asyncio.QueueEmpty:
                pass

        await self._queue.put(message)
        logger.debug("message_queued", queue_size=self._queue.qsize())

    async def process_queue(self, processor: callable) -> None:
        """Process messages from queue continuously.

        Args:
            processor: Async callable that processes each message.
                      Should accept message as single argument.

        Note:
            Runs continuously until cancelled. Processes messages in FIFO order.
            Use asyncio.create_task() to run in background.
        """
        self._processing = True
        logger.info("message_queue_processing_started")

        try:
            while self._processing:
                try:
                    # Wait for message with timeout to allow checking _processing flag
                    message = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=1.0
                    )

                    try:
                        await processor(message)
                        logger.debug("message_processed", queue_size=self._queue.qsize())
                    except Exception as e:
                        logger.error(
                            "message_processing_failed",
                            error=str(e),
                            message=message
                        )
                    finally:
                        self._queue.task_done()

                except asyncio.TimeoutError:
                    # No message available, continue loop
                    continue

        except asyncio.CancelledError:
            logger.info("message_queue_processing_cancelled")
            self._processing = False
            raise
        finally:
            self._processing = False

    def stop_processing(self) -> None:
        """Stop queue processing gracefully.

        Note:
            Call this before cancelling the process_queue task to ensure clean shutdown.
        """
        self._processing = False
        logger.info("message_queue_stop_requested")

    @property
    def size(self) -> int:
        """Get current queue size.

        Returns:
            int: Number of messages currently in queue
        """
        return self._queue.qsize()

    @property
    def is_processing(self) -> bool:
        """Check if queue is actively processing messages.

        Returns:
            bool: True if processing, False otherwise
        """
        return self._processing
