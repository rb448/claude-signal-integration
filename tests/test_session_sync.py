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
