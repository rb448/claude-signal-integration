"""
TDD RED Phase: Failing tests for ThreadMapper.

Tests for persistent thread-to-project mapping storage.
"""

import pytest
import tempfile
import aiosqlite
from pathlib import Path
from datetime import datetime, UTC

from src.thread import ThreadMapper, ThreadMappingError


@pytest.fixture
async def temp_db():
    """Create temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    yield db_path

    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
async def mapper(temp_db):
    """Create and initialize ThreadMapper."""
    mapper = ThreadMapper(temp_db)
    await mapper.initialize()
    yield mapper
    await mapper.close()


@pytest.fixture
def temp_project_dir():
    """Create temporary project directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def nonexistent_path():
    """Return path that doesn't exist."""
    return "/tmp/this_path_does_not_exist_12345"


@pytest.mark.asyncio
async def test_map_creates_new_mapping(mapper, temp_project_dir):
    """Test that map() creates a new thread-project mapping."""
    thread_id = "thread-123"

    mapping = await mapper.map(thread_id, temp_project_dir)

    assert mapping.thread_id == thread_id
    assert mapping.project_path == temp_project_dir
    assert isinstance(mapping.created_at, datetime)
    assert isinstance(mapping.updated_at, datetime)


@pytest.mark.asyncio
async def test_map_rejects_nonexistent_path(mapper, nonexistent_path):
    """Test that map() raises ThreadMappingError if path doesn't exist."""
    thread_id = "thread-456"

    with pytest.raises(ThreadMappingError, match="Path does not exist"):
        await mapper.map(thread_id, nonexistent_path)


@pytest.mark.asyncio
async def test_map_rejects_duplicate_thread(mapper, temp_project_dir):
    """Test that map() raises ThreadMappingError if thread already mapped."""
    thread_id = "thread-789"

    # First mapping succeeds
    await mapper.map(thread_id, temp_project_dir)

    # Create another temp dir for second attempt
    with tempfile.TemporaryDirectory() as another_dir:
        # Second mapping with same thread_id should fail
        with pytest.raises(ThreadMappingError, match="Thread already mapped"):
            await mapper.map(thread_id, another_dir)


@pytest.mark.asyncio
async def test_map_rejects_duplicate_path(mapper, temp_project_dir):
    """Test that map() raises ThreadMappingError if path already mapped."""
    thread_id_1 = "thread-abc"
    thread_id_2 = "thread-def"

    # First mapping succeeds
    await mapper.map(thread_id_1, temp_project_dir)

    # Second mapping with same path but different thread should fail
    with pytest.raises(ThreadMappingError, match="Path already mapped"):
        await mapper.map(thread_id_2, temp_project_dir)


@pytest.mark.asyncio
async def test_get_by_thread(mapper, temp_project_dir):
    """Test that get_by_thread() retrieves mapping by thread_id."""
    thread_id = "thread-get-123"

    # Create mapping
    created = await mapper.map(thread_id, temp_project_dir)

    # Retrieve by thread_id
    retrieved = await mapper.get_by_thread(thread_id)

    assert retrieved is not None
    assert retrieved.thread_id == created.thread_id
    assert retrieved.project_path == created.project_path


@pytest.mark.asyncio
async def test_get_by_thread_nonexistent(mapper):
    """Test that get_by_thread() returns None for non-existent thread."""
    result = await mapper.get_by_thread("nonexistent-thread")
    assert result is None


@pytest.mark.asyncio
async def test_get_by_path(mapper, temp_project_dir):
    """Test that get_by_path() retrieves mapping by project_path (reverse lookup)."""
    thread_id = "thread-path-123"

    # Create mapping
    created = await mapper.map(thread_id, temp_project_dir)

    # Retrieve by project_path
    retrieved = await mapper.get_by_path(temp_project_dir)

    assert retrieved is not None
    assert retrieved.thread_id == created.thread_id
    assert retrieved.project_path == created.project_path


@pytest.mark.asyncio
async def test_get_by_path_nonexistent(mapper):
    """Test that get_by_path() returns None for non-existent path."""
    result = await mapper.get_by_path("/some/nonexistent/path")
    assert result is None


@pytest.mark.asyncio
async def test_list_all(mapper):
    """Test that list_all() returns all mappings ordered by created_at DESC."""
    # Create multiple mappings
    with tempfile.TemporaryDirectory() as dir1:
        with tempfile.TemporaryDirectory() as dir2:
            with tempfile.TemporaryDirectory() as dir3:
                await mapper.map("thread-1", dir1)
                await mapper.map("thread-2", dir2)
                await mapper.map("thread-3", dir3)

    # List all mappings
    mappings = await mapper.list_all()

    assert len(mappings) == 3
    assert mappings[0].thread_id == "thread-3"  # Most recent first
    assert mappings[1].thread_id == "thread-2"
    assert mappings[2].thread_id == "thread-1"


@pytest.mark.asyncio
async def test_list_all_empty(mapper):
    """Test that list_all() returns empty list when no mappings exist."""
    mappings = await mapper.list_all()
    assert mappings == []


@pytest.mark.asyncio
async def test_unmap_removes_mapping(mapper, temp_project_dir):
    """Test that unmap() removes a thread-project mapping."""
    thread_id = "thread-unmap-123"

    # Create mapping
    await mapper.map(thread_id, temp_project_dir)

    # Verify it exists
    mapping = await mapper.get_by_thread(thread_id)
    assert mapping is not None

    # Remove mapping
    await mapper.unmap(thread_id)

    # Verify it's gone
    mapping = await mapper.get_by_thread(thread_id)
    assert mapping is None


@pytest.mark.asyncio
async def test_unmap_nonexistent_noop(mapper):
    """Test that unmap() on non-existent thread doesn't raise error (idempotent)."""
    # Should not raise any exception
    await mapper.unmap("nonexistent-thread-12345")
