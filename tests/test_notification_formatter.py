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

    def test_format_approval_needed_with_target_only(self):
        """Approval events with target but no lines should format without line count."""
        event = {
            "type": "approval_needed",
            "details": {"tool": "Write", "target": "config.json"},
            "urgency": UrgencyLevel.URGENT,
        }
        result = self.formatter.format(event)
        assert result.startswith("🚨")
        assert "*Approval Needed*" in result
        assert "Write config.json" in result
        assert "lines" not in result

    def test_format_approval_needed_with_tool_only(self):
        """Approval events with only tool should use generic message."""
        event = {
            "type": "approval_needed",
            "details": {"tool": "Bash"},
            "urgency": UrgencyLevel.URGENT,
        }
        result = self.formatter.format(event)
        assert result.startswith("🚨")
        assert "Bash requires approval" in result

    def test_format_progress_with_tool_and_target_no_lines(self):
        """Progress events with tool and target but no lines should format without line count."""
        event = {
            "type": "progress",
            "details": {"tool": "Grep", "target": "src/"},
            "urgency": UrgencyLevel.INFORMATIONAL,
        }
        result = self.formatter.format(event)
        assert result.startswith("ℹ️")
        assert "Grep src/" in result
        assert "lines" not in result

    def test_format_progress_with_no_details(self):
        """Progress events without details should use generic Processing message."""
        event = {
            "type": "progress",
            "details": {},
            "urgency": UrgencyLevel.INFORMATIONAL,
        }
        result = self.formatter.format(event)
        assert result.startswith("ℹ️")
        assert "Processing..." in result

    def test_format_reconnection_with_catch_up_summary(self):
        """Reconnection events with catch-up summary should prioritize summary over state."""
        event = {
            "type": "reconnection",
            "details": {
                "summary": "Back online. 5 commands executed, 12 tool calls completed.",
                "state": "CONNECTED",
            },
            "urgency": UrgencyLevel.IMPORTANT,
        }
        result = self.formatter.format(event)
        assert result.startswith("⚠️")
        assert "Back online" in result
        assert "5 commands executed" in result

    def test_format_reconnection_with_state_and_attempt(self):
        """Reconnection events with state and attempt should format both."""
        event = {
            "type": "reconnection",
            "details": {"state": "RECONNECTING", "attempt": 2},
            "urgency": UrgencyLevel.IMPORTANT,
        }
        result = self.formatter.format(event)
        assert result.startswith("⚠️")
        assert "RECONNECTING (attempt 2)" in result

    def test_format_reconnection_with_state_only(self):
        """Reconnection events with only state should show state."""
        event = {
            "type": "reconnection",
            "details": {"state": "DISCONNECTED"},
            "urgency": UrgencyLevel.IMPORTANT,
        }
        result = self.formatter.format(event)
        assert result.startswith("⚠️")
        assert "DISCONNECTED" in result

    def test_format_reconnection_with_no_details(self):
        """Reconnection events without details should use generic message."""
        event = {
            "type": "reconnection",
            "details": {},
            "urgency": UrgencyLevel.IMPORTANT,
        }
        result = self.formatter.format(event)
        assert result.startswith("⚠️")
        assert "Connection state changed" in result

    def test_format_unknown_event_type_with_message(self):
        """Unknown event types should use generic fallback with message."""
        event = {
            "type": "custom_event",
            "details": {"message": "Something happened"},
            "urgency": UrgencyLevel.INFORMATIONAL,
        }
        result = self.formatter.format(event)
        assert result.startswith("ℹ️")
        assert "*Custom_Event*" in result  # .title() keeps underscores
        assert "Something happened" in result

    def test_format_unknown_event_type_with_session_id_and_message(self):
        """Unknown events with session ID and message should show both."""
        event = {
            "type": "custom",
            "details": {"message": "Action completed"},
            "session_id": "xyz789ab-1234-5678-9012-345678901234",
            "urgency": UrgencyLevel.INFORMATIONAL,
        }
        result = self.formatter.format(event)
        assert "Session xyz789ab" in result
        assert "Action completed" in result

    def test_format_unknown_event_type_with_session_id_only(self):
        """Unknown events with only session ID should show session."""
        event = {
            "type": "custom",
            "details": {},
            "session_id": "abc123de-f456-7890-1234-567890abcdef",
            "urgency": UrgencyLevel.INFORMATIONAL,
        }
        result = self.formatter.format(event)
        assert "Session abc123de" in result

    def test_format_empty_event(self):
        """Events with no details or session should return empty summary."""
        event = {
            "type": "unknown",
            "details": {},
            "urgency": UrgencyLevel.INFORMATIONAL,
        }
        result = self.formatter.format(event)
        # Should not crash, emoji and title should be present
        assert result.startswith("ℹ️")
        assert "*Unknown*" in result
