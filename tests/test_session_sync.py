"""
Tests for session state synchronization.

RED Phase: Write failing tests first.
"""

import pytest
from src.session.sync import SessionSynchronizer


class TestSessionSynchronizer:
    """Test session state diff and merge logic."""

    @pytest.fixture
    def synchronizer(self):
        """Create SessionSynchronizer instance."""
        return SessionSynchronizer()

    def test_no_changes_detected(self, synchronizer):
        """Test that identical contexts produce empty diff."""
        local_context = {"last_output": "A", "commands_run": 5}
        remote_context = {"last_output": "A", "commands_run": 5}

        diff = synchronizer.calculate_diff(local_context, remote_context)

        assert diff == {}

    def test_remote_newer_detected(self, synchronizer):
        """Test that remote changes are detected when remote is newer."""
        local_context = {"last_output": "A", "commands_run": 5}
        remote_context = {"last_output": "B", "commands_run": 6}

        diff = synchronizer.calculate_diff(local_context, remote_context)

        assert diff == {"last_output": "B", "commands_run": 6}

    def test_local_newer_detected(self, synchronizer):
        """Test that local wins when local has newer timestamp."""
        local_context = {
            "last_output": "C",
            "commands_run": 7,
            "updated_at": "2026-01-27T16:00:00Z"
        }
        remote_context = {
            "last_output": "B",
            "commands_run": 6,
            "updated_at": "2026-01-27T15:00:00Z"
        }

        diff = synchronizer.calculate_diff(local_context, remote_context)

        assert diff == {}  # Local wins - no changes needed

    def test_merge_applies_diff_correctly(self, synchronizer):
        """Test that merge correctly applies diff to local context."""
        local_context = {"a": 1, "b": 2}
        diff = {"b": 3, "c": 4}

        merged = synchronizer.merge(local_context, diff)

        assert merged == {"a": 1, "b": 3, "c": 4}

    @pytest.mark.asyncio
    async def test_sync_returns_correct_result_when_changed(self, synchronizer):
        """Test that sync returns correct result when contexts differ."""
        local = {"last_output": "A"}
        remote = {"last_output": "B"}

        result = await synchronizer.sync("test-session-123", local, remote)

        assert result.changed is True
        assert result.diff == {"last_output": "B"}
        assert result.merged_context == {"last_output": "B"}

    @pytest.mark.asyncio
    async def test_sync_returns_correct_result_when_unchanged(self, synchronizer):
        """Test that sync returns correct result when contexts are identical."""
        local = {"last_output": "A"}
        remote = {"last_output": "A"}

        result = await synchronizer.sync("test-session-123", local, remote)

        assert result.changed is False
        assert result.diff == {}
        assert result.merged_context == {"last_output": "A"}
