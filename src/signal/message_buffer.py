"""Message buffer for outgoing messages during disconnect."""
from collections import deque
from typing import List, Tuple


class MessageBuffer:
    """Buffer for outgoing messages during disconnect.

    Uses FIFO (deque) with size limit to prevent memory exhaustion.
    Oldest messages dropped if buffer full.
    """

    def __init__(self, max_size: int = 100):
        """
        Initialize message buffer.

        Args:
            max_size: Maximum messages to buffer (default 100)
        """
        self.max_size = max_size
        self._buffer: deque = deque(maxlen=max_size)

    def enqueue(self, recipient: str, text: str) -> None:
        """
        Add message to buffer.

        If buffer full, oldest message automatically dropped (deque behavior).

        Args:
            recipient: Phone number in E.164 format
            text: Message text
        """
        self._buffer.append((recipient, text))

    def dequeue(self) -> Tuple[str, str] | None:
        """
        Remove and return oldest message from buffer.

        Returns:
            (recipient, text) tuple or None if buffer empty
        """
        if self._buffer:
            return self._buffer.popleft()
        return None

    def drain(self) -> List[Tuple[str, str]]:
        """
        Remove and return all buffered messages.

        Returns:
            List of (recipient, text) tuples in FIFO order
        """
        messages = list(self._buffer)
        self._buffer.clear()
        return messages

    def __len__(self) -> int:
        """Return number of buffered messages."""
        return len(self._buffer)

    def is_empty(self) -> bool:
        """Check if buffer is empty."""
        return len(self._buffer) == 0
