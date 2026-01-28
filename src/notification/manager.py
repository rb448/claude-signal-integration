"""NotificationManager orchestrates event categorization, preferences, and delivery."""

import structlog
from typing import TYPE_CHECKING

from src.notification.categorizer import EventCategorizer
from src.notification.preferences import NotificationPreferences
from src.notification.formatter import NotificationFormatter
from src.notification.types import UrgencyLevel

if TYPE_CHECKING:
    from src.signal.client import SignalClient

logger = structlog.get_logger(__name__)


class NotificationManager:
    """
    Orchestrate notification flow from event to Signal delivery.

    Coordinates:
    - Event categorization (urgency levels)
    - User preference checking
    - Message formatting
    - Signal delivery
    """

    def __init__(
        self,
        categorizer: EventCategorizer,
        preferences: NotificationPreferences,
        signal_client: "SignalClient",
        authorized_number: str
    ):
        """
        Initialize NotificationManager.

        Args:
            categorizer: EventCategorizer for urgency classification
            preferences: NotificationPreferences for user preference storage
            signal_client: SignalClient for message delivery
            authorized_number: E.164 phone number for notification delivery
        """
        self.categorizer = categorizer
        self.preferences = preferences
        self.signal_client = signal_client
        self.authorized_number = authorized_number
        self.formatter = NotificationFormatter()
        self._log = logger.bind(recipient=authorized_number)

    async def notify(
        self,
        event_type: str,
        details: dict,
        thread_id: str,
        session_id: str | None = None
    ) -> bool:
        """
        Send notification if event meets criteria.

        Process:
        1. Categorize event (determine urgency)
        2. Check user preferences
        3. Format message
        4. Send via Signal

        Args:
            event_type: Event type name (e.g., "error", "completion")
            details: Event-specific details dict
            thread_id: Signal thread identifier
            session_id: Optional session ID for context

        Returns:
            True if notification sent, False if skipped

        Examples:
            >>> await manager.notify(
            ...     event_type="error",
            ...     details={"message": "File not found"},
            ...     thread_id="thread-123",
            ...     session_id="abc123de"
            ... )
            True
        """
        # 1. Categorize event
        event = {"type": event_type, "details": details}
        urgency = self.categorizer.categorize(event)

        self._log.debug(
            "notification_event",
            event_type=event_type,
            urgency=urgency.name,
            thread_id=thread_id[:8] if len(thread_id) > 8 else thread_id
        )

        # 2. Check preferences
        should_send = await self.preferences.should_notify(thread_id, event_type, urgency)
        if not should_send:
            self._log.debug(
                "notification_skipped",
                event_type=event_type,
                reason="user_preference_disabled"
            )
            return False

        # 3. Format message
        event_with_session = {
            "type": event_type,
            "details": details,
            "urgency": urgency,
            "session_id": session_id
        }
        message = self.formatter.format(event_with_session)

        # Handle SILENT urgency (formatter returns empty string)
        if not message:
            self._log.debug(
                "notification_skipped",
                event_type=event_type,
                reason="silent_urgency"
            )
            return False

        # 4. Send via Signal
        try:
            await self.signal_client.send_message(self.authorized_number, message)
            self._log.info(
                "notification_sent",
                event_type=event_type,
                urgency=urgency.name,
                message_preview=message[:50]
            )
            return True
        except Exception as e:
            self._log.error(
                "notification_send_failed",
                event_type=event_type,
                error=str(e)
            )
            return False
