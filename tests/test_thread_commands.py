"""
Tests for ThreadCommands - User-facing thread mapping commands.

RED Phase: Write failing tests for ThreadCommands class that doesn't exist yet.
"""

import pytest
from pathlib import Path
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock

from src.thread import ThreadMapper, ThreadMapping, ThreadMappingError
from src.thread.commands import ThreadCommands


@pytest.fixture
def mock_mapper():
    """Mock ThreadMapper for testing."""
    mapper = AsyncMock(spec=ThreadMapper)
    return mapper


@pytest.fixture
def thread_commands(mock_mapper):
    """Create ThreadCommands with mocked dependencies."""
    return ThreadCommands(mapper=mock_mapper)


@pytest.mark.asyncio
async def test_thread_map_creates_mapping(thread_commands, mock_mapper, tmp_path):
    """Test /thread map creates a thread-to-project mapping."""
    # Setup: Create a real directory
    project_path = str(tmp_path / "test-project")
    Path(project_path).mkdir()

    # Mock successful mapping
    now = datetime.now(UTC)
    mapping = ThreadMapping(
        thread_id="abc123de",
        project_path=project_path,
        created_at=now,
        updated_at=now
    )
    mock_mapper.map.return_value = mapping

    # Execute
    message = f"/thread map {project_path}"
    result = await thread_commands.handle("abc123de", message)

    # Verify
    mock_mapper.map.assert_called_once_with("abc123de", project_path)
    assert "✓" in result
    assert "abc123de" in result
    assert project_path in result


@pytest.mark.asyncio
async def test_thread_map_rejects_nonexistent_path(thread_commands, mock_mapper):
    """Test /thread map returns error for non-existent path."""
    # Setup: Mock mapper to raise error for non-existent path
    bad_path = "/path/that/does/not/exist"
    mock_mapper.map.side_effect = ThreadMappingError(f"Path does not exist: {bad_path}")

    # Execute
    message = f"/thread map {bad_path}"
    result = await thread_commands.handle("abc123de", message)

    # Verify
    assert "Error" in result
    assert bad_path in result


@pytest.mark.asyncio
async def test_thread_map_rejects_duplicate_thread(thread_commands, mock_mapper):
    """Test /thread map returns error if thread already mapped."""
    # Setup: Mock mapper to raise error for duplicate thread
    existing_path = "/existing/project"
    mock_mapper.map.side_effect = ThreadMappingError(f"Thread already mapped to {existing_path}")

    # Execute
    message = "/thread map /some/path"
    result = await thread_commands.handle("abc123de", message)

    # Verify
    assert "Error" in result
    assert "already mapped" in result
    assert existing_path in result


@pytest.mark.asyncio
async def test_thread_map_rejects_duplicate_path(thread_commands, mock_mapper):
    """Test /thread map returns error if path already mapped to another thread."""
    # Setup: Mock mapper to raise error for duplicate path
    existing_thread = "xyz789ab"
    mock_mapper.map.side_effect = ThreadMappingError(f"Path already mapped to thread {existing_thread}")

    # Execute
    message = "/thread map /some/path"
    result = await thread_commands.handle("abc123de", message)

    # Verify
    assert "Error" in result
    assert "already mapped" in result
    assert "xyz789ab" in result


@pytest.mark.asyncio
async def test_thread_list_shows_mappings(thread_commands, mock_mapper):
    """Test /thread list returns formatted list of mappings."""
    # Setup: Mock multiple mappings
    now = datetime.now(UTC)
    mappings = [
        ThreadMapping(
            thread_id="abc123de",
            project_path="/path/to/project1",
            created_at=now,
            updated_at=now
        ),
        ThreadMapping(
            thread_id="xyz789ab",
            project_path="/path/to/project2",
            created_at=now,
            updated_at=now
        ),
    ]
    mock_mapper.list_all.return_value = mappings

    # Execute
    message = "/thread list"
    result = await thread_commands.handle("any-thread", message)

    # Verify
    mock_mapper.list_all.assert_called_once()
    assert "abc123de" in result
    assert "xyz789ab" in result
    assert "/path/to/project1" in result
    assert "/path/to/project2" in result


@pytest.mark.asyncio
async def test_thread_list_empty(thread_commands, mock_mapper):
    """Test /thread list returns appropriate message when no mappings exist."""
    # Setup: Mock empty list
    mock_mapper.list_all.return_value = []

    # Execute
    message = "/thread list"
    result = await thread_commands.handle("any-thread", message)

    # Verify
    mock_mapper.list_all.assert_called_once()
    assert "No thread mappings" in result or "No mappings" in result


@pytest.mark.asyncio
async def test_thread_unmap_removes_mapping(thread_commands, mock_mapper):
    """Test /thread unmap removes the current thread's mapping."""
    # Setup: Mock successful unmap
    mock_mapper.unmap.return_value = None

    # Execute
    message = "/thread unmap"
    result = await thread_commands.handle("abc123de", message)

    # Verify
    mock_mapper.unmap.assert_called_once_with("abc123de")
    assert "✓" in result
    assert "abc123de" in result
    assert "unmap" in result.lower()


@pytest.mark.asyncio
async def test_thread_help_shows_usage(thread_commands):
    """Test /thread help returns command documentation."""
    # Execute
    message = "/thread help"
    result = await thread_commands.handle("any-thread", message)

    # Verify
    assert "/thread map" in result
    assert "/thread list" in result
    assert "/thread unmap" in result
    assert "/thread help" in result


@pytest.mark.asyncio
async def test_thread_invalid_subcommand(thread_commands):
    """Test /thread with invalid subcommand returns help."""
    # Execute
    message = "/thread invalid"
    result = await thread_commands.handle("any-thread", message)

    # Verify: Should return help text
    assert "/thread map" in result
    assert "/thread list" in result


@pytest.mark.asyncio
async def test_thread_no_subcommand(thread_commands):
    """Test /thread without subcommand returns help."""
    # Execute
    message = "/thread"
    result = await thread_commands.handle("any-thread", message)

    # Verify: Should return help text
    assert "/thread map" in result
    assert "/thread list" in result
