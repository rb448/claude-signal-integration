"""
Approval command handlers for Signal bot.

Handles approval/rejection commands from users.
Follows SessionCommands pattern from Phase 2-5.
"""

from typing import Optional
from src.approval.manager import ApprovalManager


class ApprovalCommands:
    """
    Handles approval/rejection commands from Signal messages.

    Parses and routes:
    - approve {id} - Approve pending operation
    - reject {id} - Reject pending operation
    - approve all - Approve all pending operations
    """

    def __init__(self, manager: ApprovalManager):
        """
        Initialize ApprovalCommands.

        Args:
            manager: ApprovalManager for state transitions
        """
        self.manager = manager

    async def handle(self, message: str) -> Optional[str]:
        """
        Handle approval command.

        Args:
            message: Command message (e.g., "approve {id}")

        Returns:
            Response message (None if unknown command)
        """
        # Parse command
        parts = message.strip().split()
        if not parts:
            return None

        command = parts[0].lower()

        if command == "approve":
            if len(parts) < 2:
                return None  # Let SessionCommands handle

            # Check for "approve all"
            if parts[1].lower() == "all":
                return await self._approve_all()

            # Regular "approve {id}"
            approval_id = parts[1]
            return await self._approve(approval_id)

        elif command == "reject":
            if len(parts) < 2:
                return None  # Let SessionCommands handle

            approval_id = parts[1]
            return await self._reject(approval_id)

        # Unknown command - let SessionCommands handle
        return None

    async def _approve(self, approval_id: str) -> str:
        """
        Approve single request.

        Args:
            approval_id: ID of request to approve

        Returns:
            Success or error message
        """
        try:
            self.manager.approve(approval_id)
            # Truncate ID to 8 chars for mobile-friendly display
            return f"✅ Approved {approval_id[:8]}"
        except KeyError:
            return f"Error: Approval not found: {approval_id[:8]}"

    async def _reject(self, approval_id: str) -> str:
        """
        Reject single request.

        Args:
            approval_id: ID of request to reject

        Returns:
            Success or error message
        """
        try:
            self.manager.reject(approval_id)
            # Truncate ID to 8 chars for mobile-friendly display
            return f"❌ Rejected {approval_id[:8]}"
        except KeyError:
            return f"Error: Approval not found: {approval_id[:8]}"

    async def _approve_all(self) -> str:
        """
        Approve all pending requests.

        Returns:
            Success message with count
        """
        count = self.manager.approve_all()
        return f"✅ Approved all pending ({count})"

    def help(self) -> str:
        """
        Return help message.

        Returns:
            Help text with available commands
        """
        return """Approval Commands:
  approve {id} - Approve pending operation
  reject {id} - Reject pending operation
  approve all - Approve all pending operations"""
