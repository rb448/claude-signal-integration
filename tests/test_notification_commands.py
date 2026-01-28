"""Tests for NotificationCommands handler."""

import pytest
from src.notification.commands import NotificationCommands
from src.notification.preferences import NotificationPreferences
from src.notification.categorizer import UrgencyLevel


@pytest.fixture
async def preferences(tmp_path):
    """Create test NotificationPreferences with temporary database."""
    db_path = tmp_path / "test_notification_prefs.db"
    prefs = NotificationPreferences(db_path=str(db_path))
    await prefs.initialize()
    yield prefs
    await prefs.close()


@pytest.fixture
def commands(preferences):
    """Create NotificationCommands with test preferences."""
    return NotificationCommands(preferences=preferences)


@pytest.mark.asyncio
async def test_notify_list_shows_current_preferences(commands):
    """Test /notify list shows all event types with their status."""
    thread_id = "test-thread-123"

    response = await commands.handle("/notify list", thread_id)

    # Should show all event types with their urgency levels
    assert "Notification Preferences" in response
    assert "error (urgent)" in response
    assert "approval_needed (urgent)" in response
    assert "completion (important)" in response
    assert "reconnection (important)" in response
    assert "progress (informational)" in response

    # Should include usage hint
    assert "/notify enable/disable" in response


@pytest.mark.asyncio
async def test_notify_list_shows_defaults_before_customization(commands):
    """Test /notify list shows default preferences before user customization."""
    thread_id = "test-thread-456"

    response = await commands.handle("/notify list", thread_id)

    # URGENT events always enabled
    assert "✅ error" in response
    assert "✅ approval_needed" in response

    # IMPORTANT events enabled by default
    assert "✅ completion" in response
    assert "✅ reconnection" in response

    # INFORMATIONAL events disabled by default
    assert "❌ progress" in response


@pytest.mark.asyncio
async def test_notify_enable_updates_preference(commands, preferences):
    """Test /notify enable sets preference to enabled."""
    thread_id = "test-thread-789"
    event_type = "progress"

    # Initially disabled (INFORMATIONAL default)
    initial = await preferences.should_notify(thread_id, event_type, UrgencyLevel.INFORMATIONAL)
    assert initial is False

    # Enable it
    response = await commands.handle("/notify enable progress", thread_id)
    assert response == "✅ Enabled notifications for progress"

    # Verify preference updated
    updated = await preferences.should_notify(thread_id, event_type, UrgencyLevel.INFORMATIONAL)
    assert updated is True


@pytest.mark.asyncio
async def test_notify_disable_updates_preference(commands, preferences):
    """Test /notify disable sets preference to disabled."""
    thread_id = "test-thread-012"
    event_type = "completion"

    # Initially enabled (IMPORTANT default)
    initial = await preferences.should_notify(thread_id, event_type, UrgencyLevel.IMPORTANT)
    assert initial is True

    # Disable it
    response = await commands.handle("/notify disable completion", thread_id)
    assert response == "❌ Disabled notifications for completion"

    # Verify preference updated
    updated = await preferences.should_notify(thread_id, event_type, UrgencyLevel.IMPORTANT)
    assert updated is False


@pytest.mark.asyncio
async def test_notify_help_returns_help_text(commands):
    """Test /notify help returns command reference."""
    response = await commands.handle("/notify help", "any-thread")

    # Should include all commands
    assert "/notify list" in response
    assert "/notify enable" in response
    assert "/notify disable" in response
    assert "/notify help" in response

    # Should list event types
    assert "error" in response
    assert "approval_needed" in response
    assert "completion" in response
    assert "reconnection" in response
    assert "progress" in response


@pytest.mark.asyncio
async def test_notify_no_subcommand_returns_help(commands):
    """Test /notify without subcommand returns help."""
    response = await commands.handle("/notify", "any-thread")

    # Should return help text
    assert "Notification Commands" in response


@pytest.mark.asyncio
async def test_notify_unknown_command_returns_error(commands):
    """Test /notify with unknown subcommand returns error."""
    response = await commands.handle("/notify unknown", "any-thread")

    assert "Unknown subcommand: /notify unknown" in response
    assert "/notify help" in response


@pytest.mark.asyncio
async def test_notify_cannot_disable_urgent(commands):
    """Test /notify disable rejects URGENT event types."""
    thread_id = "test-thread-urgent"

    # Try to disable error notifications
    response = await commands.handle("/notify disable error", thread_id)
    assert "Cannot disable urgent notifications" in response

    # Try to disable approval_needed notifications
    response = await commands.handle("/notify disable approval_needed", thread_id)
    assert "Cannot disable urgent notifications" in response


@pytest.mark.asyncio
async def test_notify_enable_urgent_is_redundant_but_allowed(commands):
    """Test /notify enable on URGENT events provides informative message."""
    thread_id = "test-thread-urgent-enable"

    response = await commands.handle("/notify enable error", thread_id)

    # Should inform user that urgent events are always enabled
    assert "error is already enabled" in response
    assert "cannot be disabled" in response


@pytest.mark.asyncio
async def test_notify_unknown_event_type_error(commands):
    """Test /notify enable/disable with unknown event type returns error."""
    thread_id = "test-thread-unknown"

    # Try to enable unknown event type
    response = await commands.handle("/notify enable unknown_event", thread_id)
    assert "Unknown event type: unknown_event" in response
    assert "/notify list" in response

    # Try to disable unknown event type
    response = await commands.handle("/notify disable another_unknown", thread_id)
    assert "Unknown event type: another_unknown" in response
    assert "/notify list" in response


@pytest.mark.asyncio
async def test_notify_enable_missing_event_type(commands):
    """Test /notify enable without event type returns error."""
    response = await commands.handle("/notify enable", "any-thread")

    assert "Error: Missing event type" in response
    assert "/notify enable <event_type>" in response


@pytest.mark.asyncio
async def test_notify_disable_missing_event_type(commands):
    """Test /notify disable without event type returns error."""
    response = await commands.handle("/notify disable", "any-thread")

    assert "Error: Missing event type" in response
    assert "/notify disable <event_type>" in response


@pytest.mark.asyncio
async def test_notify_unknown_command_returns_none(commands):
    """Test non-/notify commands return None for fallthrough."""
    # Not a /notify command
    response = await commands.handle("/session list", "any-thread")
    assert response is None

    # Random text
    response = await commands.handle("hello world", "any-thread")
    assert response is None

    # approve command
    response = await commands.handle("approve abc123", "any-thread")
    assert response is None


@pytest.mark.asyncio
async def test_notify_list_reflects_custom_preferences(commands, preferences):
    """Test /notify list shows user-customized preferences."""
    thread_id = "test-thread-custom"

    # Customize preferences
    await preferences.set_preference(thread_id, "progress", enabled=True)
    await preferences.set_preference(thread_id, "completion", enabled=False)

    response = await commands.handle("/notify list", thread_id)

    # Should reflect custom preferences
    assert "✅ progress" in response  # Changed from default disabled
    assert "❌ completion" in response  # Changed from default enabled

    # URGENT events still enabled (cannot be changed)
    assert "✅ error" in response
    assert "✅ approval_needed" in response


@pytest.mark.asyncio
async def test_notify_commands_are_thread_specific(commands, preferences):
    """Test notification preferences are isolated per thread."""
    thread_a = "thread-aaa"
    thread_b = "thread-bbb"

    # Enable progress for thread A
    await commands.handle("/notify enable progress", thread_a)

    # Disable completion for thread B
    await commands.handle("/notify disable completion", thread_b)

    # Verify thread A preferences
    progress_a = await preferences.should_notify(thread_a, "progress", UrgencyLevel.INFORMATIONAL)
    completion_a = await preferences.should_notify(thread_a, "completion", UrgencyLevel.IMPORTANT)
    assert progress_a is True  # Enabled in thread A
    assert completion_a is True  # Still default enabled in thread A

    # Verify thread B preferences
    progress_b = await preferences.should_notify(thread_b, "progress", UrgencyLevel.INFORMATIONAL)
    completion_b = await preferences.should_notify(thread_b, "completion", UrgencyLevel.IMPORTANT)
    assert progress_b is False  # Still default disabled in thread B
    assert completion_b is False  # Disabled in thread B
