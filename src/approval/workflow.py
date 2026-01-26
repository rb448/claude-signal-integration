"""
Approval Workflow - Coordinates operation detection and approval management.

Integrates OperationDetector and ApprovalManager to provide a high-level
interface for approval workflow coordination.
"""

import asyncio
from typing import Tuple, Optional

from src.approval.detector import OperationDetector, OperationType
from src.approval.manager import ApprovalManager
from src.approval.models import ApprovalState
from src.claude.parser import ToolCall


class ApprovalWorkflow:
    """
    Coordinate approval workflow for Claude operations.

    Combines operation detection and approval state management into
    a single high-level interface.
    """

    def __init__(self, detector: OperationDetector, manager: ApprovalManager):
        """
        Initialize approval workflow.

        Args:
            detector: OperationDetector for classifying operations
            manager: ApprovalManager for state tracking
        """
        self.detector = detector
        self.manager = manager

    def intercept(self, tool_call: ToolCall) -> Tuple[bool, Optional[str]]:
        """
        Intercept a tool call and determine if approval is needed.

        Args:
            tool_call: ToolCall object from parser

        Returns:
            tuple: (approved, request_id)
                - approved: True if safe (auto-approved), False if needs approval
                - request_id: None if auto-approved, approval ID if needs approval
        """
        # Classify operation
        operation_type, reason = self.detector.classify(tool_call)

        # Safe operations are auto-approved
        if operation_type == OperationType.SAFE:
            return (True, None)

        # Destructive operations require approval
        # Create approval request
        tool_call_dict = {
            "tool": tool_call.tool,
            "target": tool_call.target,
            "command": tool_call.command,
        }
        request = self.manager.request(tool_call_dict, reason)

        return (False, request.id)

    async def wait_for_approval(self, request_id: str, timeout: int = 600) -> bool:
        """
        Wait for approval request to be approved or rejected.

        Polls approval state every 1 second until:
        - Request is approved (returns True)
        - Request is rejected (returns False)
        - Timeout expires (returns False)

        Args:
            request_id: ID of approval request to wait for
            timeout: Maximum time to wait in seconds (default: 600 = 10 minutes)

        Returns:
            True if approved, False if rejected or timeout
        """
        elapsed = 0
        poll_interval = 1  # Poll every 1 second

        while elapsed < timeout:
            # Get current state
            request = self.manager.get(request_id)

            if request is None:
                # Request disappeared - treat as rejection
                return False

            # Check terminal states
            if request.state == ApprovalState.APPROVED:
                return True
            elif request.state in (ApprovalState.REJECTED, ApprovalState.TIMEOUT):
                return False

            # Wait before next poll
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        # Timeout expired without approval
        return False

    def format_approval_message(
        self, tool_call: ToolCall, reason: str, request_id: str
    ) -> str:
        """
        Format user-friendly approval request message.

        Args:
            tool_call: ToolCall object requiring approval
            reason: Human-readable reason for approval
            request_id: ID of approval request

        Returns:
            Formatted message string ready for Signal
        """
        # Determine what to display (target for file operations, command for bash)
        detail = tool_call.target if tool_call.target else tool_call.command

        message_lines = [
            f"⚠️ Approval needed: {tool_call.tool} on {detail}",
            "",
            f"Reason: {reason}",
            "",
            f"Reply 'approve {request_id}' or 'reject {request_id}'",
        ]

        return "\n".join(message_lines)
