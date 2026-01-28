"""Tests for event categorization with urgency levels."""

import pytest
from src.notification.categorizer import EventCategorizer, UrgencyLevel


class TestEventCategorizer:
    """Test EventCategorizer.categorize() urgency classification."""

    def setup_method(self):
        """Create categorizer instance for each test."""
        self.categorizer = EventCategorizer()

    def test_categorize_error_event_as_urgent(self):
        """Error events should be categorized as URGENT."""
        event = {"type": "error", "details": {"message": "Connection failed"}}
        assert self.categorizer.categorize(event) == UrgencyLevel.URGENT

    def test_categorize_approval_needed_as_urgent(self):
        """Approval events should be categorized as URGENT."""
        event = {"type": "approval_needed", "details": {"tool": "Edit", "target": "main.py"}}
        assert self.categorizer.categorize(event) == UrgencyLevel.URGENT

    def test_categorize_completion_as_important(self):
        """Completion events should be categorized as IMPORTANT."""
        event = {"type": "completion", "details": {"session_id": "abc123"}}
        assert self.categorizer.categorize(event) == UrgencyLevel.IMPORTANT

    def test_categorize_progress_as_informational(self):
        """Progress events should be categorized as INFORMATIONAL."""
        event = {"type": "progress", "details": {"tool": "Read", "target": "config.json"}}
        assert self.categorizer.categorize(event) == UrgencyLevel.INFORMATIONAL

    def test_categorize_reconnection_as_important(self):
        """Reconnection events should be categorized as IMPORTANT."""
        event = {"type": "reconnection", "details": {"state": "CONNECTED"}}
        assert self.categorizer.categorize(event) == UrgencyLevel.IMPORTANT

    def test_categorize_unknown_event_as_informational(self):
        """Unknown event types should default to INFORMATIONAL."""
        event = {"type": "unknown_type", "details": {}}
        assert self.categorizer.categorize(event) == UrgencyLevel.INFORMATIONAL

    def test_categorize_case_insensitive_type_matching(self):
        """Event type matching should be case-insensitive."""
        event_upper = {"type": "ERROR", "details": {}}
        event_mixed = {"type": "Error", "details": {}}
        assert self.categorizer.categorize(event_upper) == UrgencyLevel.URGENT
        assert self.categorizer.categorize(event_mixed) == UrgencyLevel.URGENT

    def test_categorize_missing_type_field_defaults_to_informational(self):
        """Events without 'type' field should default to INFORMATIONAL."""
        event = {"details": {"message": "No type field"}}
        assert self.categorizer.categorize(event) == UrgencyLevel.INFORMATIONAL

    def test_categorize_empty_event_defaults_to_informational(self):
        """Empty event dict should default to INFORMATIONAL."""
        event = {}
        assert self.categorizer.categorize(event) == UrgencyLevel.INFORMATIONAL
