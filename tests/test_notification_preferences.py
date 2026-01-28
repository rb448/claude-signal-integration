"""
TDD RED Phase: Tests for NotificationPreferences.

Tests for per-thread notification preference storage with preference matching algorithm.
"""

import pytest
from pathlib import Path
from datetime import datetime, UTC
from src.notification.preferences import NotificationPreferences
from src.notification.types import UrgencyLevel


@pytest.fixture
async def preferences(tmp_path):
    """Create NotificationPreferences with temporary database."""
    db_path = str(tmp_path / "test_prefs.db")
    prefs = NotificationPreferences(db_path=db_path)
    await prefs.initialize()
    yield prefs
    await prefs.close()


@pytest.mark.asyncio
async def test_initialize_creates_database(tmp_path):
    """Test that initialize() creates database and schema."""
    db_path = tmp_path / "prefs.db"
    prefs = NotificationPreferences(db_path=str(db_path))

    await prefs.initialize()

    assert db_path.exists()
    await prefs.close()


@pytest.mark.asyncio
async def test_set_preference_stores_value(preferences):
    """Test that set_preference() stores preference to database."""
    thread_id = "thread-123"
    event_type = "completion"

    await preferences.set_preference(thread_id, event_type, enabled=False)

    # Verify stored
    result = await preferences.get_preference(thread_id, event_type)
    assert result is False


@pytest.mark.asyncio
async def test_set_preference_updates_existing(preferences):
    """Test that set_preference() updates existing preference (upsert)."""
    thread_id = "thread-123"
    event_type = "completion"

    # Set initial value
    await preferences.set_preference(thread_id, event_type, enabled=True)

    # Update value
    await preferences.set_preference(thread_id, event_type, enabled=False)

    # Verify updated
    result = await preferences.get_preference(thread_id, event_type)
    assert result is False


@pytest.mark.asyncio
async def test_get_preference_returns_none_when_not_set(preferences):
    """Test that get_preference() returns None for unset preference."""
    thread_id = "thread-123"
    event_type = "progress"

    result = await preferences.get_preference(thread_id, event_type)

    assert result is None


@pytest.mark.asyncio
async def test_get_all_preferences_returns_empty_dict_for_new_thread(preferences):
    """Test that get_all_preferences() returns empty dict for thread with no preferences."""
    thread_id = "thread-new"

    result = await preferences.get_all_preferences(thread_id)

    assert result == {}


@pytest.mark.asyncio
async def test_get_all_preferences_returns_all_thread_preferences(preferences):
    """Test that get_all_preferences() returns all preferences for a thread."""
    thread_id = "thread-123"

    # Set multiple preferences
    await preferences.set_preference(thread_id, "completion", enabled=True)
    await preferences.set_preference(thread_id, "progress", enabled=False)
    await preferences.set_preference(thread_id, "error", enabled=True)

    result = await preferences.get_all_preferences(thread_id)

    assert result == {
        "completion": True,
        "progress": False,
        "error": True,
    }


@pytest.mark.asyncio
async def test_should_notify_urgent_always_returns_true(preferences):
    """Test that should_notify() always returns True for URGENT regardless of preference."""
    thread_id = "thread-123"
    event_type = "error"

    # Set preference to disabled
    await preferences.set_preference(thread_id, event_type, enabled=False)

    # URGENT should override preference
    result = await preferences.should_notify(thread_id, event_type, UrgencyLevel.URGENT)

    assert result is True


@pytest.mark.asyncio
async def test_should_notify_silent_always_returns_false(preferences):
    """Test that should_notify() always returns False for SILENT regardless of preference."""
    thread_id = "thread-123"
    event_type = "debug"

    # Set preference to enabled
    await preferences.set_preference(thread_id, event_type, enabled=True)

    # SILENT should override preference
    result = await preferences.should_notify(thread_id, event_type, UrgencyLevel.SILENT)

    assert result is False


@pytest.mark.asyncio
async def test_should_notify_uses_preference_when_set(preferences):
    """Test that should_notify() uses stored preference for IMPORTANT/INFORMATIONAL."""
    thread_id = "thread-123"
    event_type = "completion"

    # Set preference to disabled
    await preferences.set_preference(thread_id, event_type, enabled=False)

    # Should respect preference
    result = await preferences.should_notify(thread_id, event_type, UrgencyLevel.IMPORTANT)

    assert result is False


@pytest.mark.asyncio
async def test_should_notify_uses_default_for_important_when_not_set(preferences):
    """Test that should_notify() defaults to True for IMPORTANT when no preference set."""
    thread_id = "thread-new"
    event_type = "completion"

    # No preference set
    result = await preferences.should_notify(thread_id, event_type, UrgencyLevel.IMPORTANT)

    # Default for IMPORTANT is True
    assert result is True


@pytest.mark.asyncio
async def test_should_notify_uses_default_for_informational_when_not_set(preferences):
    """Test that should_notify() defaults to False for INFORMATIONAL when no preference set."""
    thread_id = "thread-new"
    event_type = "progress"

    # No preference set
    result = await preferences.should_notify(thread_id, event_type, UrgencyLevel.INFORMATIONAL)

    # Default for INFORMATIONAL is False
    assert result is False


@pytest.mark.asyncio
async def test_preferences_persist_across_reconnection(tmp_path):
    """Test that preferences survive database reconnection."""
    db_path = str(tmp_path / "persist_test.db")
    thread_id = "thread-123"
    event_type = "completion"

    # Create first instance, set preference, close
    prefs1 = NotificationPreferences(db_path=db_path)
    await prefs1.initialize()
    await prefs1.set_preference(thread_id, event_type, enabled=False)
    await prefs1.close()

    # Create second instance, verify preference persists
    prefs2 = NotificationPreferences(db_path=db_path)
    await prefs2.initialize()
    result = await prefs2.get_preference(thread_id, event_type)
    await prefs2.close()

    assert result is False


@pytest.mark.asyncio
async def test_concurrent_access_safe_with_wal_mode(preferences):
    """Test that concurrent operations don't corrupt database (WAL mode)."""
    thread_id = "thread-concurrent"

    # Simulate concurrent writes
    import asyncio
    await asyncio.gather(
        preferences.set_preference(thread_id, "event1", enabled=True),
        preferences.set_preference(thread_id, "event2", enabled=False),
        preferences.set_preference(thread_id, "event3", enabled=True),
    )

    # Verify all written correctly
    result = await preferences.get_all_preferences(thread_id)
    assert result == {
        "event1": True,
        "event2": False,
        "event3": True,
    }
