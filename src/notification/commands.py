"""
Notification command handlers for Signal bot.

Handles notification preference commands from users.
Follows Phase 5 ApprovalCommands pattern.
"""

from typing import Optional
from src.notification.preferences import NotificationPreferences
from src.notification.categorizer import EventCategorizer
from src.notification.types import UrgencyLevel


class NotificationCommands:
    """
    Handles notification preference commands from Signal messages.

    Parses and routes:
    - /notify list - Show current preferences for this thread
    - /notify enable <event_type> - Enable notifications for event type
    - /notify disable <event_type> - Disable notifications for event type
    - /notify help - Show command reference
    """

    def __init__(self, preferences: NotificationPreferences):
        """
        Initialize NotificationCommands.

        Args:
            preferences: NotificationPreferences for preference CRUD operations
        """
        self.preferences = preferences
        self.categorizer = EventCategorizer()

    async def handle(self, message: str, thread_id: str) -> Optional[str]:
        """
        Handle notification command.

        Args:
            message: Command message (e.g., "/notify list")
            thread_id: Signal thread identifier

        Returns:
            Response message (None if unknown command)
        """
        # Parse command
        parts = message.strip().split()
        if not parts or parts[0].lower() != "/notify":
            return None

        if len(parts) < 2:
            return self.help()

        subcommand = parts[1].lower()

        if subcommand == "list":
            return await self._list_preferences(thread_id)
        elif subcommand == "enable":
            if len(parts) < 3:
                return "Error: Missing event type\n\nUsage: /notify enable <event_type>"
            event_type = parts[2].lower()
            return await self._enable_preference(thread_id, event_type)
        elif subcommand == "disable":
            if len(parts) < 3:
                return "Error: Missing event type\n\nUsage: /notify disable <event_type>"
            event_type = parts[2].lower()
            return await self._disable_preference(thread_id, event_type)
        elif subcommand == "help":
            return self.help()
        else:
            return f"Unknown subcommand: /notify {subcommand}\n\nUse /notify help for usage."

    async def _list_preferences(self, thread_id: str) -> str:
        """
        List current notification preferences for thread.

        Args:
            thread_id: Signal thread identifier

        Returns:
            Formatted table of preferences with urgency levels
        """
        # Get all stored preferences
        stored_prefs = await self.preferences.get_all_preferences(thread_id)

        # Build output showing all event types with their status
        lines = ["Notification Preferences", ""]

        # Get all event types from categorizer rules
        event_types = self.categorizer.URGENCY_RULES.keys()

        for event_type in sorted(event_types):
            urgency = self.categorizer.URGENCY_RULES[event_type]

            # Determine if enabled (using preference matching logic)
            enabled = await self.preferences.should_notify(thread_id, event_type, urgency)

            # Format display
            status_emoji = "✅" if enabled else "❌"
            urgency_name = urgency.name.lower()
            lines.append(f"{status_emoji} {event_type} ({urgency_name})")

        lines.append("")
        lines.append("Use /notify enable/disable <type>")

        return "\n".join(lines)

    async def _enable_preference(self, thread_id: str, event_type: str) -> str:
        """
        Enable notifications for event type.

        Args:
            thread_id: Signal thread identifier
            event_type: Event type name (e.g., "completion", "error")

        Returns:
            Success or error message
        """
        # Validate event type exists
        if event_type not in self.categorizer.URGENCY_RULES:
            return f"Unknown event type: {event_type}. Use /notify list to see options."

        # Check urgency level
        urgency = self.categorizer.URGENCY_RULES[event_type]

        # Cannot enable SILENT events
        if urgency == UrgencyLevel.SILENT:
            return "Cannot enable silent notifications"

        # URGENT events are always enabled - user attempting to enable is redundant but harmless
        if urgency == UrgencyLevel.URGENT:
            return f"✅ {event_type} is already enabled (urgent notifications cannot be disabled)"

        # Set preference
        await self.preferences.set_preference(thread_id, event_type, enabled=True)

        return f"✅ Enabled notifications for {event_type}"

    async def _disable_preference(self, thread_id: str, event_type: str) -> str:
        """
        Disable notifications for event type.

        Args:
            thread_id: Signal thread identifier
            event_type: Event type name (e.g., "completion", "error")

        Returns:
            Success or error message
        """
        # Validate event type exists
        if event_type not in self.categorizer.URGENCY_RULES:
            return f"Unknown event type: {event_type}. Use /notify list to see options."

        # Check urgency level
        urgency = self.categorizer.URGENCY_RULES[event_type]

        # Cannot disable URGENT events
        if urgency == UrgencyLevel.URGENT:
            return "⚠️ Cannot disable urgent notifications (error, approval_needed)"

        # SILENT events are already disabled - user attempting to disable is redundant but harmless
        if urgency == UrgencyLevel.SILENT:
            return f"❌ {event_type} is already disabled (silent events never notify)"

        # Set preference
        await self.preferences.set_preference(thread_id, event_type, enabled=False)

        return f"❌ Disabled notifications for {event_type}"

    def help(self) -> str:
        """
        Return help message.

        Returns:
            Help text with available commands
        """
        return """Notification Commands:
  /notify list - Show current preferences
  /notify enable <type> - Enable notifications
  /notify disable <type> - Disable notifications
  /notify help - Show this help

Event Types:
  • error (urgent) - Cannot disable
  • approval_needed (urgent) - Cannot disable
  • completion (important)
  • reconnection (important)
  • progress (info)"""
