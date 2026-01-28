"""
Tests for EmergencyCommands handler.

TDD RED phase: Tests for emergency mode command interface.
"""

import pytest
from src.emergency.commands import EmergencyCommands
from src.emergency.mode import EmergencyMode


@pytest.fixture
async def emergency_mode(tmp_path):
    """Create EmergencyMode instance for testing."""
    db_path = str(tmp_path / "test_emergency.db")
    mode = EmergencyMode(db_path=db_path)
    await mode.initialize()
    return mode


@pytest.fixture
async def emergency_commands(emergency_mode):
    """Create EmergencyCommands instance for testing."""
    return EmergencyCommands(emergency_mode)


@pytest.mark.asyncio
async def test_handle_activate(emergency_commands):
    """Test /emergency activate activates mode and returns confirmation."""
    thread_id = "+1234567890"
    response = await emergency_commands.handle(thread_id, "/emergency activate")

    # Should confirm activation
    assert "⚡" in response
    assert "ACTIVATED" in response.upper()
    assert "auto-approved" in response.lower()

    # Should actually activate emergency mode
    assert await emergency_commands.emergency_mode.is_active()


@pytest.mark.asyncio
async def test_handle_deactivate(emergency_commands):
    """Test /emergency deactivate deactivates mode and returns confirmation."""
    thread_id = "+1234567890"

    # Activate first
    await emergency_commands.emergency_mode.activate(thread_id)
    assert await emergency_commands.emergency_mode.is_active()

    # Deactivate
    response = await emergency_commands.handle(thread_id, "/emergency deactivate")

    # Should confirm deactivation
    assert "✅" in response
    assert "deactivated" in response.lower()

    # Should actually deactivate emergency mode
    assert not await emergency_commands.emergency_mode.is_active()


@pytest.mark.asyncio
async def test_handle_status_active(emergency_commands):
    """Test /emergency status returns EMERGENCY when active."""
    thread_id = "+1234567890"

    # Activate emergency mode
    await emergency_commands.emergency_mode.activate(thread_id)

    # Check status
    response = await emergency_commands.handle(thread_id, "/emergency status")

    assert "⚡" in response
    assert "EMERGENCY" in response.upper()
    assert "activated" in response.lower()


@pytest.mark.asyncio
async def test_handle_status_normal(emergency_commands):
    """Test /emergency status returns NORMAL when not active."""
    thread_id = "+1234567890"

    # Check status (should be normal by default)
    response = await emergency_commands.handle(thread_id, "/emergency status")

    assert "✅" in response
    assert "NORMAL" in response.upper()


@pytest.mark.asyncio
async def test_handle_help(emergency_commands):
    """Test /emergency help returns usage instructions."""
    thread_id = "+1234567890"
    response = await emergency_commands.handle(thread_id, "/emergency help")

    # Should contain usage information
    assert "usage" in response.lower() or "commands" in response.lower()
    assert "activate" in response
    assert "deactivate" in response
    assert "status" in response


@pytest.mark.asyncio
async def test_unknown_subcommand(emergency_commands):
    """Test /emergency unknown returns help text."""
    thread_id = "+1234567890"
    response = await emergency_commands.handle(thread_id, "/emergency unknown")

    # Should show help for unknown subcommand
    response_lower = response.lower()
    assert "usage" in response_lower or "unknown" in response_lower or "commands" in response_lower
    assert "activate" in response_lower
    assert "deactivate" in response_lower


@pytest.mark.asyncio
async def test_activate_records_thread(emergency_commands):
    """Test activation records which thread activated it."""
    thread_id = "+1234567890"

    # Activate
    await emergency_commands.handle(thread_id, "/emergency activate")

    # Check that the thread was recorded
    state = await emergency_commands.emergency_mode.get_state()
    assert state["activated_by_thread"] == thread_id
