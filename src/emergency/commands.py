"""
Emergency mode command handler.

Provides /emergency command interface for activating, deactivating, and checking emergency mode status.
"""

from datetime import datetime, timezone
from src.emergency.mode import EmergencyMode


class EmergencyCommands:
    """
    Handler for /emergency commands.

    Routes subcommands (activate, deactivate, status, help) to appropriate emergency mode operations.
    Follows ApprovalCommands pattern from Phase 5-04.
    """

    def __init__(self, emergency_mode: EmergencyMode):
        """
        Initialize emergency command handler.

        Args:
            emergency_mode: EmergencyMode instance for state management
        """
        self.emergency_mode = emergency_mode

    async def handle(self, thread_id: str, message: str) -> str:
        """
        Handle /emergency command and route to appropriate subcommand.

        Args:
            thread_id: Signal thread ID
            message: Full message text (e.g., "/emergency activate")

        Returns:
            Response message for user
        """
        # Parse subcommand
        parts = message.strip().split(maxsplit=1)
        subcommand = parts[1].lower() if len(parts) > 1 else "help"

        # Route to subcommand handler
        if subcommand == "activate":
            return await self._activate(thread_id)
        elif subcommand == "deactivate":
            return await self._deactivate()
        elif subcommand == "status":
            return await self._status()
        elif subcommand == "help":
            return self._help()
        else:
            # Unknown subcommand - show help
            return self._help()

    async def _activate(self, thread_id: str) -> str:
        """
        Activate emergency mode for the given thread.

        Args:
            thread_id: Signal thread ID that initiated activation

        Returns:
            Confirmation message
        """
        await self.emergency_mode.activate(thread_id)

        return (
            "⚡ Emergency mode ACTIVATED\n\n"
            "Safe operations (Read, Grep, Glob) will be auto-approved.\n"
            "Destructive operations (Edit, Write, Bash) still need approval."
        )

    async def _deactivate(self) -> str:
        """
        Deactivate emergency mode.

        Returns:
            Confirmation message
        """
        await self.emergency_mode.deactivate()

        return "✅ Emergency mode deactivated\n\nNormal approval workflow restored."

    async def _status(self) -> str:
        """
        Get current emergency mode status.

        Returns:
            Status message with emoji indicator
        """
        is_active = await self.emergency_mode.is_active()

        if is_active:
            state = await self.emergency_mode.get_state()
            activated_at = state.get("activated_at")
            thread_id = state.get("activated_by_thread", "unknown")

            # Format timestamp if available
            timestamp_str = ""
            if activated_at:
                try:
                    dt = datetime.fromisoformat(activated_at)
                    timestamp_str = f"\nActivated: {dt.strftime('%Y-%m-%d %H:%M:%S UTC')}"
                except (ValueError, TypeError):
                    pass

            return (
                f"⚡ EMERGENCY mode\n"
                f"Thread: {thread_id[:8]}"
                f"{timestamp_str}"
            )
        else:
            return "✅ NORMAL mode\n\nAll operations require approval."

    def _help(self) -> str:
        """
        Get help text for emergency commands.

        Returns:
            Help message with usage examples
        """
        return (
            "Emergency Mode Commands:\n\n"
            "/emergency activate - Enable emergency mode (auto-approve safe ops)\n"
            "/emergency deactivate - Disable emergency mode\n"
            "/emergency status - Check current mode\n"
            "/emergency help - Show this help\n\n"
            "In emergency mode:\n"
            "✅ Auto-approved: Read, Grep, Glob\n"
            "⚠️ Still require approval: Edit, Write, Bash"
        )
