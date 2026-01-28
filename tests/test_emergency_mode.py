"""Tests for emergency mode state machine."""
import asyncio
import pytest
import tempfile
from pathlib import Path

from src.emergency.mode import EmergencyMode, EmergencyStatus


@pytest.fixture
async def temp_db():
    """Create temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    mode = EmergencyMode(str(db_path))
    await mode.initialize()

    yield mode

    # Cleanup
    if db_path.exists():
        db_path.unlink()


@pytest.mark.asyncio
async def test_activate(temp_db):
    """Test activation transitions NORMAL → EMERGENCY."""
    mode = temp_db

    # Initially NORMAL
    assert not await mode.is_active()

    # Activate
    await mode.activate("thread-123")

    # Now EMERGENCY
    assert await mode.is_active()


@pytest.mark.asyncio
async def test_deactivate(temp_db):
    """Test deactivation transitions EMERGENCY → NORMAL."""
    mode = temp_db

    # Activate first
    await mode.activate("thread-123")
    assert await mode.is_active()

    # Deactivate
    await mode.deactivate()

    # Now NORMAL
    assert not await mode.is_active()


@pytest.mark.asyncio
async def test_is_active(temp_db):
    """Test is_active returns correct status."""
    mode = temp_db

    # NORMAL → False
    assert not await mode.is_active()

    # EMERGENCY → True
    await mode.activate("thread-123")
    assert await mode.is_active()

    # NORMAL → False
    await mode.deactivate()
    assert not await mode.is_active()


@pytest.mark.asyncio
async def test_persistence():
    """Test state persists across restarts."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    try:
        # First instance - activate
        mode1 = EmergencyMode(str(db_path))
        await mode1.initialize()
        await mode1.activate("thread-123")
        assert await mode1.is_active()

        # Second instance - should still be active
        mode2 = EmergencyMode(str(db_path))
        await mode2.initialize()
        assert await mode2.is_active()
    finally:
        if db_path.exists():
            db_path.unlink()


@pytest.mark.asyncio
async def test_activated_at_timestamp(temp_db):
    """Test activation records timestamp."""
    mode = temp_db

    await mode.activate("thread-123")

    # Should have timestamp
    state = await mode.get_state()
    assert state["activated_at"] is not None
    assert "T" in state["activated_at"]  # ISO format with T separator


@pytest.mark.asyncio
async def test_activated_by_thread(temp_db):
    """Test activation tracks which thread activated."""
    mode = temp_db

    await mode.activate("thread-456")

    # Should track thread
    state = await mode.get_state()
    assert state["activated_by_thread"] == "thread-456"


@pytest.mark.asyncio
async def test_idempotent_activate(temp_db):
    """Test activate when EMERGENCY is no-op."""
    mode = temp_db

    # First activation
    await mode.activate("thread-123")
    state1 = await mode.get_state()

    # Second activation (should be no-op)
    await mode.activate("thread-456")
    state2 = await mode.get_state()

    # State unchanged (still EMERGENCY, same timestamp, same original thread)
    assert state2["status"] == EmergencyStatus.EMERGENCY.value
    assert state2["activated_at"] == state1["activated_at"]
    assert state2["activated_by_thread"] == "thread-123"  # Original thread preserved


@pytest.mark.asyncio
async def test_idempotent_deactivate(temp_db):
    """Test deactivate when NORMAL is no-op."""
    mode = temp_db

    # Already NORMAL
    assert not await mode.is_active()

    # Deactivate (should be no-op, no error)
    await mode.deactivate()

    # Still NORMAL
    assert not await mode.is_active()
