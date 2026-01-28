"""
Notification system types.

Shared types for notification categorization and preferences.
"""

from enum import Enum


class UrgencyLevel(Enum):
    """
    Notification urgency levels.

    Controls notification priority and default user preferences.
    """
    URGENT = "URGENT"          # Always notify (errors, approvals)
    IMPORTANT = "IMPORTANT"    # Notify by default (completions, reconnection)
    INFORMATIONAL = "INFORMATIONAL"  # Don't notify by default (progress)
    SILENT = "SILENT"          # Never notify
