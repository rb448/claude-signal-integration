"""
Notification system types.

Shared types for notification categorization and preferences.
"""

from enum import IntEnum


class UrgencyLevel(IntEnum):
    """
    Notification urgency levels.

    Lower numeric values = higher urgency.
    Controls notification priority and default user preferences.
    """
    URGENT = 0          # Always notify (errors, approvals) - Immediate attention
    IMPORTANT = 1       # Notify by default (completions, reconnection) - Notable events
    INFORMATIONAL = 2   # Don't notify by default (progress) - Background activity
    SILENT = 3          # Never notify - No notification sent
