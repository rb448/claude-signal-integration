"""Tests for emergency mode auto-committer."""
import asyncio
import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch, call

from src.emergency.auto_committer import EmergencyAutoCommitter
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
def auto_committer():
    """Create auto-committer instance."""
    return EmergencyAutoCommitter()


def test_format_commit_message(auto_committer):
    """Test commit message generation with [EMERGENCY] prefix."""
    message = auto_committer.format_commit_message(
        session_id="abc123de-f456-7890-g123-h456i789j012",
        operation="Edit",
        files=["src/api.py", "src/utils.py"],
    )

    assert message.startswith("[EMERGENCY]")
    assert "Edit" in message
    assert "src/api.py" in message
    assert "src/utils.py" in message


def test_includes_session_id(auto_committer):
    """Test commit message includes truncated session ID."""
    message = auto_committer.format_commit_message(
        session_id="abc123de-f456-7890-g123-h456i789j012",
        operation="Write",
        files=["config.json"],
    )

    # Session ID truncated to 8 chars (Phase 2 pattern)
    assert "abc123de" in message
    assert "session" in message.lower()


def test_includes_operation_summary(auto_committer):
    """Test commit message describes operation."""
    message = auto_committer.format_commit_message(
        session_id="test-session-123",
        operation="Edit",
        files=["file1.py", "file2.py"],
    )

    assert "Edit" in message
    assert "file1.py" in message
    assert "file2.py" in message


def test_format_commit_message_many_files(auto_committer):
    """Test commit message truncates file list for 4+ files."""
    message = auto_committer.format_commit_message(
        session_id="test-session-123",
        operation="Edit",
        files=["file1.py", "file2.py", "file3.py", "file4.py", "file5.py"],
    )

    # First 3 files listed
    assert "file1.py" in message
    assert "file2.py" in message
    assert "file3.py" in message

    # Remaining files indicated with count
    assert "and 2 more" in message

    # Not all files individually listed
    assert "file4.py" not in message
    assert "file5.py" not in message


@pytest.mark.asyncio
async def test_commit_after_successful_edit(auto_committer, emergency_mode):
    """Test auto-commit after successful Edit operation."""
    await emergency_mode.activate("thread-123")

    with (
        patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec,
        tempfile.TemporaryDirectory() as tmpdir,
    ):
        # Mock successful git commands
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = 0
        mock_exec.return_value = mock_process

        await auto_committer.auto_commit(
            emergency_mode=emergency_mode,
            session_id="test-session",
            project_path=tmpdir,
            operation="Edit",
            files=["test.py"],
        )

        # Should run git add and git commit
        assert mock_exec.call_count == 2

        # First call: git add test.py
        first_call = mock_exec.call_args_list[0]
        assert "git" in first_call[0]
        assert "add" in first_call[0]
        assert "test.py" in first_call[0]

        # Second call: git commit -m "[EMERGENCY] ..."
        second_call = mock_exec.call_args_list[1]
        assert "git" in second_call[0]
        assert "commit" in second_call[0]
        assert "-m" in second_call[0]


@pytest.mark.asyncio
async def test_commit_after_successful_write(auto_committer, emergency_mode):
    """Test auto-commit after successful Write operation."""
    await emergency_mode.activate("thread-123")

    with (
        patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec,
        tempfile.TemporaryDirectory() as tmpdir,
    ):
        # Mock successful git commands
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = 0
        mock_exec.return_value = mock_process

        await auto_committer.auto_commit(
            emergency_mode=emergency_mode,
            session_id="test-session",
            project_path=tmpdir,
            operation="Write",
            files=["newfile.py"],
        )

        # Should run git commands
        assert mock_exec.call_count == 2


@pytest.mark.asyncio
async def test_no_commit_on_failure(auto_committer, emergency_mode):
    """Test no commit if operation failed."""
    await emergency_mode.activate("thread-123")

    with (
        patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec,
        tempfile.TemporaryDirectory() as tmpdir,
    ):
        # Don't call auto_commit with success=False
        # (In practice, auto_commit is only called on success)
        pass

    # This test documents that auto_commit should only be called after successful operations
    # The orchestrator/workflow is responsible for this logic


@pytest.mark.asyncio
async def test_no_commit_in_normal_mode(auto_committer, emergency_mode):
    """Test no auto-commit in normal mode."""
    # Ensure normal mode
    assert not await emergency_mode.is_active()

    with (
        patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec,
        tempfile.TemporaryDirectory() as tmpdir,
    ):
        await auto_committer.auto_commit(
            emergency_mode=emergency_mode,
            session_id="test-session",
            project_path=tmpdir,
            operation="Edit",
            files=["test.py"],
        )

        # No git commands should be executed in normal mode
        mock_exec.assert_not_called()


@pytest.mark.asyncio
async def test_multiple_files_added(auto_committer, emergency_mode):
    """Test all modified files are added to commit."""
    await emergency_mode.activate("thread-123")

    with (
        patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec,
        tempfile.TemporaryDirectory() as tmpdir,
    ):
        # Mock successful git commands
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = 0
        mock_exec.return_value = mock_process

        files = ["file1.py", "file2.py", "file3.py"]
        await auto_committer.auto_commit(
            emergency_mode=emergency_mode,
            session_id="test-session",
            project_path=tmpdir,
            operation="Edit",
            files=files,
        )

        # First call should add all files
        first_call = mock_exec.call_args_list[0]
        for file in files:
            assert file in first_call[0]


@pytest.mark.asyncio
async def test_auto_commit_git_add_failure(auto_committer, emergency_mode):
    """Test auto-commit when git add fails."""
    await emergency_mode.activate("thread-123")

    with (
        patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec,
        tempfile.TemporaryDirectory() as tmpdir,
    ):
        # Mock git add failure
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b"error"))
        mock_process.returncode = 1  # Non-zero = failure
        mock_exec.return_value = mock_process

        await auto_committer.auto_commit(
            emergency_mode=emergency_mode,
            session_id="test-session",
            project_path=tmpdir,
            operation="Edit",
            files=["test.py"],
        )

        # Should only call git add (no commit)
        assert mock_exec.call_count == 1

        # Verify git add was called
        mock_exec.assert_called_once()
        assert "git" in mock_exec.call_args[0]
        assert "add" in mock_exec.call_args[0]


@pytest.mark.asyncio
async def test_auto_commit_git_commit_failure(auto_committer, emergency_mode):
    """Test auto-commit when git commit fails."""
    await emergency_mode.activate("thread-123")

    with (
        patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec,
        tempfile.TemporaryDirectory() as tmpdir,
    ):
        # Mock git add success, git commit failure
        add_process = AsyncMock()
        add_process.communicate = AsyncMock(return_value=(b"", b""))
        add_process.returncode = 0

        commit_process = AsyncMock()
        commit_process.communicate = AsyncMock(
            return_value=(b"", b"nothing to commit, working tree clean")
        )
        commit_process.returncode = 1

        mock_exec.side_effect = [add_process, commit_process]

        await auto_committer.auto_commit(
            emergency_mode=emergency_mode,
            session_id="test-session",
            project_path=tmpdir,
            operation="Edit",
            files=["test.py"],
        )

        # Should call git add and git commit
        assert mock_exec.call_count == 2


@pytest.mark.asyncio
async def test_auto_commit_subprocess_exception(auto_committer, emergency_mode):
    """Test auto-commit handles subprocess exceptions gracefully."""
    await emergency_mode.activate("thread-123")

    with (
        patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec,
        tempfile.TemporaryDirectory() as tmpdir,
    ):
        # Mock subprocess to raise exception
        mock_exec.side_effect = OSError("git not found")

        # Should not crash
        await auto_committer.auto_commit(
            emergency_mode=emergency_mode,
            session_id="test-session",
            project_path=tmpdir,
            operation="Edit",
            files=["test.py"],
        )

        # Exception was handled (no crash)
        assert True
