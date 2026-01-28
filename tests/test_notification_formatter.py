"""Tests for notification message formatting."""

import pytest
from src.notification.formatter import NotificationFormatter
from src.notification.categorizer import UrgencyLevel


class TestNotificationFormatter:
    """Test NotificationFormatter.format() mobile-friendly message creation."""

    def setup_method(self):
        """Create formatter instance for each test."""
        self.formatter = NotificationFormatter()

    def test_format_error_event(self):
        """Error events should format with URGENT emoji and error details."""
        event = {
            "type": "error",
            "details": {"message": "FileNotFoundError", "file": "config.json"},
            "urgency": UrgencyLevel.URGENT,
        }
        result = self.formatter.format(event)
        assert result.startswith("🚨")
        assert "*Error*" in result
        assert "config.json" in result

    def test_format_approval_needed_event(self):
        """Approval events should format with URGENT emoji and tool details."""
        event = {
            "type": "approval_needed",
            "details": {"tool": "Edit", "target": "src/main.py", "lines": 23},
            "urgency": UrgencyLevel.URGENT,
        }
        result = self.formatter.format(event)
        assert result.startswith("🚨")
        assert "*Approval Needed*" in result
        assert "Edit" in result
        assert "src/main.py" in result

    def test_format_completion_event(self):
        """Completion events should format with IMPORTANT emoji and session info."""
        event = {
            "type": "completion",
            "details": {"message": "Task finished"},
            "session_id": "abc123de",
            "urgency": UrgencyLevel.IMPORTANT,
        }
        result = self.formatter.format(event)
        assert result.startswith("⚠️")
        assert "*Complete*" in result
        assert "abc123de" in result

    def test_format_progress_event(self):
        """Progress events should format with INFO emoji and tool activity."""
        event = {
            "type": "progress",
            "details": {"tool": "Read", "target": "src/utils.py", "lines": 347},
            "urgency": UrgencyLevel.INFORMATIONAL,
        }
        result = self.formatter.format(event)
        assert result.startswith("ℹ️")
        assert "*Progress*" in result
        assert "Read" in result
        assert "src/utils.py" in result

    def test_format_reconnection_event(self):
        """Reconnection events should format with IMPORTANT emoji and state."""
        event = {
            "type": "reconnection",
            "details": {"state": "CONNECTED", "attempt": 3},
            "urgency": UrgencyLevel.IMPORTANT,
        }
        result = self.formatter.format(event)
        assert result.startswith("⚠️")
        assert "*Reconnection*" in result
        assert "CONNECTED" in result

    def test_format_truncates_long_details(self):
        """Messages longer than 300 chars should be truncated with ellipsis."""
        long_message = "x" * 350
        event = {
            "type": "error",
            "details": {"message": long_message},
            "urgency": UrgencyLevel.URGENT,
        }
        result = self.formatter.format(event)
        assert len(result) <= 300
        assert result.endswith("...")

    def test_format_missing_details_uses_generic_message(self):
        """Events without details should use generic message for that type."""
        event = {"type": "error", "urgency": UrgencyLevel.URGENT}
        result = self.formatter.format(event)
        assert result.startswith("🚨")
        assert "*Error*" in result
        # Should not crash, should have some content

    def test_format_includes_truncated_session_id(self):
        """Session IDs should be truncated to 8 characters."""
        event = {
            "type": "completion",
            "details": {},
            "session_id": "abc123de-f456-7890-1234-567890abcdef",
            "urgency": UrgencyLevel.IMPORTANT,
        }
        result = self.formatter.format(event)
        assert "abc123de" in result
        assert "abc123de-f456-7890-1234-567890abcdef" not in result

    def test_format_urgency_emoji_mapping(self):
        """Each urgency level should map to correct emoji."""
        urgent_event = {"type": "error", "details": {}, "urgency": UrgencyLevel.URGENT}
        important_event = {"type": "completion", "details": {}, "urgency": UrgencyLevel.IMPORTANT}
        info_event = {"type": "progress", "details": {}, "urgency": UrgencyLevel.INFORMATIONAL}

        assert self.formatter.format(urgent_event).startswith("🚨")
        assert self.formatter.format(important_event).startswith("⚠️")
        assert self.formatter.format(info_event).startswith("ℹ️")

    def test_format_silent_urgency_returns_empty_string(self):
        """SILENT urgency level should return empty string (no notification)."""
        event = {"type": "ignored", "details": {}, "urgency": UrgencyLevel.SILENT}
        result = self.formatter.format(event)
        assert result == ""
