"""
Approval Manager - State machine for approval lifecycle.

Manages approval requests from creation through approval/rejection/timeout.
Follows Phase 2 session lifecycle pattern for state machine implementation.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, UTC, timedelta
from typing import Dict, Any, List, Optional

from src.approval.models import ApprovalState


@dataclass
class ApprovalRequest:
    """Approval request with state tracking"""
    id: str
    tool_call: Dict[str, Any]
    reason: str
    state: ApprovalState
    timestamp: datetime


class ApprovalManager:
    """
    Manages approval request lifecycle.

    State transitions:
    - PENDING → APPROVED (user approves)
    - PENDING → REJECTED (user rejects)
    - PENDING → TIMEOUT (10 minutes elapse)

    Follows set-based transition pattern from SessionLifecycle (02-02).
    """

    # 10 minute timeout for pending approvals
    TIMEOUT_MINUTES = 10

    def __init__(self):
        """Initialize approval manager with empty request tracking"""
        self._requests: Dict[str, ApprovalRequest] = {}

    def request(self, tool_call: Dict[str, Any], reason: str) -> ApprovalRequest:
        """
        Create new approval request.

        Args:
            tool_call: Tool call requiring approval
            reason: Human-readable reason for approval request

        Returns:
            ApprovalRequest in PENDING state
        """
        approval_id = str(uuid.uuid4())
        timestamp = datetime.now(UTC)

        request = ApprovalRequest(
            id=approval_id,
            tool_call=tool_call,
            reason=reason,
            state=ApprovalState.PENDING,
            timestamp=timestamp
        )

        self._requests[approval_id] = request
        return request

    def approve(self, approval_id: str) -> None:
        """
        Approve a pending request.

        Idempotent: Approving already-approved request is safe.
        Terminal states (TIMEOUT, REJECTED) are preserved.

        Args:
            approval_id: ID of request to approve

        Raises:
            KeyError: If approval_id does not exist
        """
        request = self._requests[approval_id]  # Raises KeyError if not found

        # Only transition if currently PENDING (idempotent for APPROVED)
        if request.state == ApprovalState.PENDING or request.state == ApprovalState.APPROVED:
            request.state = ApprovalState.APPROVED

    def reject(self, approval_id: str) -> None:
        """
        Reject a pending request.

        Terminal states (TIMEOUT, APPROVED) are preserved.

        Args:
            approval_id: ID of request to reject

        Raises:
            KeyError: If approval_id does not exist
        """
        request = self._requests[approval_id]  # Raises KeyError if not found

        # Only transition if currently PENDING (preserve terminal states)
        if request.state == ApprovalState.PENDING:
            request.state = ApprovalState.REJECTED

    def check_timeouts(self) -> None:
        """
        Check for and timeout old pending requests.

        Scans all pending requests and marks those older than
        TIMEOUT_MINUTES as TIMEOUT state.
        """
        now = datetime.now(UTC)
        timeout_threshold = now - timedelta(minutes=self.TIMEOUT_MINUTES)

        for request in self._requests.values():
            if request.state == ApprovalState.PENDING:
                if request.timestamp < timeout_threshold:
                    request.state = ApprovalState.TIMEOUT

    def get(self, approval_id: str) -> Optional[ApprovalRequest]:
        """
        Get approval by ID.

        Args:
            approval_id: ID of approval to retrieve

        Returns:
            ApprovalRequest if found, None otherwise
        """
        return self._requests.get(approval_id)

    def list_pending(self) -> List[ApprovalRequest]:
        """
        List all pending approvals.

        Returns:
            List of ApprovalRequest objects in PENDING state
        """
        return [
            request for request in self._requests.values()
            if request.state == ApprovalState.PENDING
        ]

    def approve_all(self) -> int:
        """
        Approve all pending requests.

        Returns:
            Count of approvals that were approved
        """
        pending = self.list_pending()

        for request in pending:
            self.approve(request.id)

        return len(pending)
