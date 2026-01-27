"""Tests for MessageBuffer."""
import pytest
from src.signal.message_buffer import MessageBuffer


def test_enqueue_and_dequeue_fifo_order():
    """Verify FIFO ordering: first in, first out."""
    buffer = MessageBuffer()

    # Enqueue 3 messages
    buffer.enqueue("+1234567890", "msg1")
    buffer.enqueue("+1234567890", "msg2")
    buffer.enqueue("+1234567890", "msg3")

    # Dequeue all
    msg1 = buffer.dequeue()
    msg2 = buffer.dequeue()
    msg3 = buffer.dequeue()

    # Assert order preserved
    assert msg1 == ("+1234567890", "msg1")
    assert msg2 == ("+1234567890", "msg2")
    assert msg3 == ("+1234567890", "msg3")
    assert buffer.dequeue() is None  # Buffer empty


def test_enqueue_when_full_drops_oldest():
    """When buffer full, oldest message should be dropped."""
    buffer = MessageBuffer(max_size=3)

    # Enqueue 4 messages (exceeds max_size)
    buffer.enqueue("+1234567890", "msg1")
    buffer.enqueue("+1234567890", "msg2")
    buffer.enqueue("+1234567890", "msg3")
    buffer.enqueue("+1234567890", "msg4")

    # Verify oldest (msg1) dropped, buffer has [msg2, msg3, msg4]
    assert len(buffer) == 3
    assert buffer.dequeue() == ("+1234567890", "msg2")
    assert buffer.dequeue() == ("+1234567890", "msg3")
    assert buffer.dequeue() == ("+1234567890", "msg4")


def test_drain_returns_all_buffered_messages():
    """Drain should return all messages and clear buffer."""
    buffer = MessageBuffer()

    # Enqueue 5 messages
    buffer.enqueue("+1234567890", "msg1")
    buffer.enqueue("+1234567890", "msg2")
    buffer.enqueue("+1234567890", "msg3")
    buffer.enqueue("+1234567890", "msg4")
    buffer.enqueue("+1234567890", "msg5")

    # Drain buffer
    messages = buffer.drain()

    # Assert returns all 5 messages in order
    assert len(messages) == 5
    assert messages[0] == ("+1234567890", "msg1")
    assert messages[1] == ("+1234567890", "msg2")
    assert messages[2] == ("+1234567890", "msg3")
    assert messages[3] == ("+1234567890", "msg4")
    assert messages[4] == ("+1234567890", "msg5")

    # Assert buffer now empty
    assert buffer.is_empty()
    assert len(buffer) == 0
