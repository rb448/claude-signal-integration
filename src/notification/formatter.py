"""Notification message formatting for mobile-friendly Signal delivery."""

from src.notification.categorizer import UrgencyLevel


class NotificationFormatter:
    """Formats notification events as mobile-optimized Signal messages."""

    # Maximum message length for mobile readability
    MAX_MESSAGE_LENGTH = 300

    # Emoji mapping for urgency levels
    URGENCY_EMOJI: dict[UrgencyLevel, str] = {
        UrgencyLevel.URGENT: "🚨",
        UrgencyLevel.IMPORTANT: "⚠️",
        UrgencyLevel.INFORMATIONAL: "ℹ️",
        UrgencyLevel.SILENT: "",
    }

    # Display names for event types (title case with Signal markdown)
    EVENT_TYPE_DISPLAY: dict[str, str] = {
        "error": "*Error*",
        "approval_needed": "*Approval Needed*",
        "completion": "*Complete*",
        "progress": "*Progress*",
        "reconnection": "*Reconnection*",
    }

    def format(self, event: dict) -> str:
        """Format event as mobile-friendly notification message.

        Args:
            event: Event dict with {
                "type": str,
                "details": dict,
                "urgency": UrgencyLevel,
                "session_id": str (optional)
            }

        Returns:
            Formatted notification string ready for Signal delivery

        Examples:
            >>> formatter = NotificationFormatter()
            >>> event = {
            ...     "type": "error",
            ...     "details": {"message": "File not found"},
            ...     "urgency": UrgencyLevel.URGENT
            ... }
            >>> formatter.format(event)
            '🚨 *Error*: File not found'
        """
        # Handle SILENT urgency - no notification sent
        urgency = event.get("urgency", UrgencyLevel.INFORMATIONAL)
        if urgency == UrgencyLevel.SILENT:
            return ""

        # Build message components
        emoji = self.URGENCY_EMOJI.get(urgency, "")
        event_type = event.get("type", "notification")
        display_type = self.EVENT_TYPE_DISPLAY.get(
            event_type.lower(), f"*{event_type.title()}*"
        )

        # Extract summary from event details
        summary = self._extract_summary(event)

        # Construct message
        message_parts = [emoji, display_type]
        if summary:
            message_parts.append(f": {summary}")

        message = " ".join(message_parts)

        # Truncate if needed
        if len(message) > self.MAX_MESSAGE_LENGTH:
            message = message[: self.MAX_MESSAGE_LENGTH - 3] + "..."

        return message

    def _extract_summary(self, event: dict) -> str:
        """Extract concise summary from event details.

        Args:
            event: Event dict with "details" and optional "session_id"

        Returns:
            Summary string describing the event
        """
        details = event.get("details", {})
        event_type = event.get("type", "").lower()
        session_id = event.get("session_id", "")

        # Format session ID if present (truncate to 8 chars)
        session_part = ""
        if session_id:
            session_part = f"Session {self._format_session_id(session_id)}"

        # Event-specific summary extraction
        if event_type == "error":
            message = details.get("message", "An error occurred")
            file = details.get("file", "")
            if file:
                return f"{message} ({file})"
            return message

        elif event_type == "approval_needed":
            tool = details.get("tool", "Action")
            target = details.get("target", "")
            lines = details.get("lines", "")
            if target and lines:
                return f"{tool} {target} ({lines} lines changed)"
            elif target:
                return f"{tool} {target}"
            return f"{tool} requires approval"

        elif event_type == "completion":
            message = details.get("message", "Task finished")
            if session_part:
                return f"{session_part} - {message}"
            return message

        elif event_type == "progress":
            tool = details.get("tool", "")
            target = details.get("target", "")
            lines = details.get("lines", "")
            if tool and target and lines:
                return f"{tool} {target} ({lines} lines)"
            elif tool and target:
                return f"{tool} {target}"
            return "Processing..."

        elif event_type == "reconnection":
            # Check for catch-up summary first
            summary = details.get("summary", "")
            if summary:
                return summary

            # Fall back to connection state info
            state = details.get("state", "")
            attempt = details.get("attempt", "")
            if state and attempt:
                return f"{state} (attempt {attempt})"
            elif state:
                return state
            return "Connection state changed"

        # Generic fallback
        message = details.get("message", "")
        if message and session_part:
            return f"{session_part} - {message}"
        elif message:
            return message
        elif session_part:
            return session_part
        return ""

    def _format_session_id(self, session_id: str) -> str:
        """Format session ID as 8-character truncated string.

        Args:
            session_id: Full session ID (UUID)

        Returns:
            First 8 characters of session ID
        """
        return session_id[:8]
