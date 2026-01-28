"""Tests for NotificationManager orchestration layer."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.notification.manager import NotificationManager
from src.notification.categorizer import EventCategorizer
from src.notification.preferences import NotificationPreferences
from src.notification.types import UrgencyLevel


@pytest.fixture
def mock_signal_client():
    """Create mock SignalClient."""
    client = MagicMock()
    client.send_message = AsyncMock()
    return client


@pytest.fixture
def mock_preferences():
    """Create mock NotificationPreferences."""
    prefs = MagicMock(spec=NotificationPreferences)
    prefs.should_notify = AsyncMock(return_value=True)
    return prefs


@pytest.fixture
def notification_manager(mock_signal_client, mock_preferences):
    """Create NotificationManager with mocked dependencies."""
    categorizer = EventCategorizer()
    return NotificationManager(
        categorizer=categorizer,
        preferences=mock_preferences,
        signal_client=mock_signal_client,
        authorized_number="+15551234567"
    )


@pytest.mark.asyncio
async def test_notify_sends_message_for_urgent_events(
    notification_manager, mock_signal_client, mock_preferences
):
    """URGENT events should send notification."""
    # Act
    result = await notification_manager.notify(
        event_type="error",
        details={"message": "File not found"},
        thread_id="thread-123",
        session_id="abc123de"
    )

    # Assert
    assert result is True
    mock_preferences.should_notify.assert_called_once()
    mock_signal_client.send_message.assert_called_once()

    # Verify message format
    call_args = mock_signal_client.send_message.call_args
    recipient, message = call_args[0]
    assert recipient == "+15551234567"
    assert "Error" in message
    assert "File not found" in message


@pytest.mark.asyncio
async def test_notify_respects_user_preferences(
    notification_manager, mock_signal_client, mock_preferences
):
    """Notification should respect user preferences for IMPORTANT events."""
    # Arrange - user disabled completion notifications
    mock_preferences.should_notify = AsyncMock(return_value=False)

    # Act
    result = await notification_manager.notify(
        event_type="completion",
        details={"message": "Task finished"},
        thread_id="thread-123",
        session_id="abc123de"
    )

    # Assert
    assert result is False
    mock_preferences.should_notify.assert_called_once()
    mock_signal_client.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_notify_skips_when_preference_disabled(
    notification_manager, mock_signal_client, mock_preferences
):
    """should_notify=False should prevent notification."""
    # Arrange
    mock_preferences.should_notify = AsyncMock(return_value=False)

    # Act
    result = await notification_manager.notify(
        event_type="progress",
        details={"tool": "Read", "target": "file.py"},
        thread_id="thread-123"
    )

    # Assert
    assert result is False
    mock_signal_client.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_notify_formats_message_correctly(
    notification_manager, mock_signal_client, mock_preferences
):
    """Notification message should be formatted correctly."""
    # Act
    await notification_manager.notify(
        event_type="approval_needed",
        details={"tool": "Edit", "target": "config.json"},
        thread_id="thread-123",
        session_id="abc123de-f456-7890-1234-567890abcdef"
    )

    # Assert
    call_args = mock_signal_client.send_message.call_args
    _, message = call_args[0]

    # Should include urgency emoji, event type, and details
    assert "🚨" in message  # URGENT emoji
    assert "Approval Needed" in message
    assert "Edit" in message
    assert "config.json" in message


@pytest.mark.asyncio
async def test_notify_returns_true_when_sent_false_when_skipped(
    notification_manager, mock_signal_client, mock_preferences
):
    """Return value should indicate whether notification was sent."""
    # Test sent
    mock_preferences.should_notify = AsyncMock(return_value=True)
    result = await notification_manager.notify(
        event_type="error",
        details={"message": "Error occurred"},
        thread_id="thread-123"
    )
    assert result is True

    # Reset mock
    mock_signal_client.send_message.reset_mock()

    # Test skipped
    mock_preferences.should_notify = AsyncMock(return_value=False)
    result = await notification_manager.notify(
        event_type="progress",
        details={"tool": "Read"},
        thread_id="thread-123"
    )
    assert result is False


@pytest.mark.asyncio
async def test_notify_handles_send_failure(
    notification_manager, mock_signal_client, mock_preferences
):
    """Send failure should be logged and return False."""
    # Arrange - simulate send failure
    mock_signal_client.send_message = AsyncMock(side_effect=Exception("Network error"))

    # Act
    result = await notification_manager.notify(
        event_type="error",
        details={"message": "Test error"},
        thread_id="thread-123"
    )

    # Assert - should return False on send failure
    assert result is False


@pytest.mark.asyncio
async def test_notify_with_completion_event(
    notification_manager, mock_signal_client, mock_preferences
):
    """Completion events should format correctly."""
    # Act
    await notification_manager.notify(
        event_type="completion",
        details={"message": "Task finished", "status": "complete"},
        thread_id="thread-123",
        session_id="abc123de"
    )

    # Assert
    call_args = mock_signal_client.send_message.call_args
    _, message = call_args[0]

    assert "⚠️" in message  # IMPORTANT emoji
    assert "Complete" in message
    assert "abc123de" in message  # Session ID truncated


@pytest.mark.asyncio
async def test_notify_categorizes_unknown_events_as_informational(
    notification_manager, mock_signal_client, mock_preferences
):
    """Unknown event types should default to INFORMATIONAL urgency."""
    # Act
    await notification_manager.notify(
        event_type="unknown_event",
        details={"message": "Something happened"},
        thread_id="thread-123"
    )

    # Assert - should call should_notify with INFORMATIONAL urgency
    call = mock_preferences.should_notify.call_args
    _, kwargs = call
    # The urgency is passed as the third positional argument
    urgency = call[0][2] if len(call[0]) > 2 else None
    assert urgency == UrgencyLevel.INFORMATIONAL
