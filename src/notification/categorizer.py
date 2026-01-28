"""Event categorization with urgency levels for notification system."""

from enum import IntEnum


class UrgencyLevel(IntEnum):
    """Urgency levels for notification events.

    Lower numeric values = higher urgency.
    """

    URGENT = 0  # Immediate attention required (errors, approvals)
    IMPORTANT = 1  # Notable events (completion, reconnection)
    INFORMATIONAL = 2  # Background activity (progress updates)
    SILENT = 3  # No notification sent


class EventCategorizer:
    """Categorizes events by urgency level for notification routing."""

    # Urgency rules: event type → UrgencyLevel
    URGENCY_RULES: dict[str, UrgencyLevel] = {
        "error": UrgencyLevel.URGENT,
        "approval_needed": UrgencyLevel.URGENT,
        "completion": UrgencyLevel.IMPORTANT,
        "reconnection": UrgencyLevel.IMPORTANT,
        "progress": UrgencyLevel.INFORMATIONAL,
    }

    def categorize(self, event: dict) -> UrgencyLevel:
        """Categorize event by urgency level.

        Args:
            event: Event dict with {"type": str, "details": dict}

        Returns:
            UrgencyLevel enum indicating notification urgency

        Examples:
            >>> categorizer = EventCategorizer()
            >>> categorizer.categorize({"type": "error", "details": {}})
            UrgencyLevel.URGENT
            >>> categorizer.categorize({"type": "progress", "details": {}})
            UrgencyLevel.INFORMATIONAL
        """
        # Extract event type with defensive defaults
        event_type = event.get("type", "")
        if not event_type:
            return UrgencyLevel.INFORMATIONAL

        # Case-insensitive lookup in urgency rules
        event_type_lower = event_type.lower()
        return self.URGENCY_RULES.get(event_type_lower, UrgencyLevel.INFORMATIONAL)
