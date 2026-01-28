"""Tests for emergency mode auto-approver."""
import pytest
import tempfile
from pathlib import Path

from src.emergency.auto_approver import EmergencyAutoApprover
from src.emergency.mode import EmergencyMode


@pytest.fixture
async def emergency_mode():
    """Create emergency mode instance for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    mode = EmergencyMode(str(db_path))
    await mode.initialize()

    yield mode

    # Cleanup
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def auto_approver():
    """Create auto-approver instance."""
    return EmergencyAutoApprover()


@pytest.mark.asyncio
async def test_auto_approve_read(auto_approver, emergency_mode):
    """Test Read tool auto-approved in emergency mode."""
    await emergency_mode.activate("thread-123")

    result = await auto_approver.should_auto_approve("Read", emergency_mode)

    assert result is True


@pytest.mark.asyncio
async def test_auto_approve_grep(auto_approver, emergency_mode):
    """Test Grep tool auto-approved in emergency mode."""
    await emergency_mode.activate("thread-123")

    result = await auto_approver.should_auto_approve("Grep", emergency_mode)

    assert result is True


@pytest.mark.asyncio
async def test_auto_approve_glob(auto_approver, emergency_mode):
    """Test Glob tool auto-approved in emergency mode."""
    await emergency_mode.activate("thread-123")

    result = await auto_approver.should_auto_approve("Glob", emergency_mode)

    assert result is True


@pytest.mark.asyncio
async def test_require_approval_edit(auto_approver, emergency_mode):
    """Test Edit tool requires approval even in emergency mode."""
    await emergency_mode.activate("thread-123")

    result = await auto_approver.should_auto_approve("Edit", emergency_mode)

    assert result is False


@pytest.mark.asyncio
async def test_require_approval_write(auto_approver, emergency_mode):
    """Test Write tool requires approval even in emergency mode."""
    await emergency_mode.activate("thread-123")

    result = await auto_approver.should_auto_approve("Write", emergency_mode)

    assert result is False


@pytest.mark.asyncio
async def test_require_approval_bash(auto_approver, emergency_mode):
    """Test Bash tool requires approval even in emergency mode."""
    await emergency_mode.activate("thread-123")

    result = await auto_approver.should_auto_approve("Bash", emergency_mode)

    assert result is False


@pytest.mark.asyncio
async def test_not_emergency_mode(auto_approver, emergency_mode):
    """Test all tools follow normal approval rules when mode=NORMAL."""
    # Ensure NORMAL mode
    assert not await emergency_mode.is_active()

    # All tools should NOT auto-approve in NORMAL mode
    assert not await auto_approver.should_auto_approve("Read", emergency_mode)
    assert not await auto_approver.should_auto_approve("Grep", emergency_mode)
    assert not await auto_approver.should_auto_approve("Glob", emergency_mode)
    assert not await auto_approver.should_auto_approve("Edit", emergency_mode)
    assert not await auto_approver.should_auto_approve("Write", emergency_mode)
    assert not await auto_approver.should_auto_approve("Bash", emergency_mode)


@pytest.mark.asyncio
async def test_case_insensitive_tool_names(auto_approver, emergency_mode):
    """Test tool name matching is case-insensitive."""
    await emergency_mode.activate("thread-123")

    # Different case variations should work
    assert await auto_approver.should_auto_approve("read", emergency_mode) is True
    assert await auto_approver.should_auto_approve("READ", emergency_mode) is True
    assert await auto_approver.should_auto_approve("grep", emergency_mode) is True
    assert await auto_approver.should_auto_approve("GREP", emergency_mode) is True
    assert await auto_approver.should_auto_approve("edit", emergency_mode) is False
    assert await auto_approver.should_auto_approve("EDIT", emergency_mode) is False
