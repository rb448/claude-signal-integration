"""
Test approval state machine and lifecycle management.

Tests follow TDD RED-GREEN-REFACTOR:
1. RED: Write failing tests (this file)
2. GREEN: Implement minimal code to pass
3. REFACTOR: Clean up if needed
"""

import asyncio
import pytest
from datetime import datetime, UTC, timedelta

from src.approval.models import ApprovalState
from src.approval.manager import ApprovalManager, ApprovalRequest


class TestApprovalStateTransitions:
    """Test core state transitions: PENDING → APPROVED/REJECTED/TIMEOUT"""

    def test_create_approval_starts_pending(self):
        """New approval request should start in PENDING state"""
        manager = ApprovalManager()

        tool_call = {"tool": "Edit", "target": "src/main.py"}
        request = manager.request(tool_call, reason="Edit modifies file")

        assert request.state == ApprovalState.PENDING
        assert request.tool_call == tool_call
        assert request.reason == "Edit modifies file"
        assert request.id is not None
        assert isinstance(request.timestamp, datetime)

    def test_approve_transitions_pending_to_approved(self):
        """Approving pending request transitions to APPROVED"""
        manager = ApprovalManager()

        request = manager.request({"tool": "Write"}, reason="Creates file")
        approval_id = request.id

        manager.approve(approval_id)

        updated = manager.get(approval_id)
        assert updated.state == ApprovalState.APPROVED

    def test_reject_transitions_pending_to_rejected(self):
        """Rejecting pending request transitions to REJECTED"""
        manager = ApprovalManager()

        request = manager.request({"tool": "Bash"}, reason="Runs command")
        approval_id = request.id

        manager.reject(approval_id)

        updated = manager.get(approval_id)
        assert updated.state == ApprovalState.REJECTED


class TestApprovalTimeout:
    """Test timeout detection and transition after 10 minutes"""

    def test_timeout_transitions_after_10_minutes(self):
        """Pending request times out after 10 minutes"""
        manager = ApprovalManager()

        # Create request with timestamp 11 minutes ago
        request = manager.request({"tool": "Edit"}, reason="Modifies file")
        request.timestamp = datetime.now(UTC) - timedelta(minutes=11)
        manager._requests[request.id] = request  # Manually update timestamp

        manager.check_timeouts()

        updated = manager.get(request.id)
        assert updated.state == ApprovalState.TIMEOUT

    def test_no_timeout_before_10_minutes(self):
        """Pending request does not timeout before 10 minutes"""
        manager = ApprovalManager()

        # Create request with timestamp 9 minutes ago
        request = manager.request({"tool": "Edit"}, reason="Modifies file")
        request.timestamp = datetime.now(UTC) - timedelta(minutes=9)
        manager._requests[request.id] = request

        manager.check_timeouts()

        updated = manager.get(request.id)
        assert updated.state == ApprovalState.PENDING

    def test_check_timeouts_scans_all_pending(self):
        """check_timeouts() scans all pending requests"""
        manager = ApprovalManager()

        # Create 3 requests with different ages
        req1 = manager.request({"tool": "Edit"}, reason="Recent")
        req1.timestamp = datetime.now(UTC) - timedelta(minutes=5)
        manager._requests[req1.id] = req1

        req2 = manager.request({"tool": "Write"}, reason="Old")
        req2.timestamp = datetime.now(UTC) - timedelta(minutes=15)
        manager._requests[req2.id] = req2

        req3 = manager.request({"tool": "Bash"}, reason="Older")
        req3.timestamp = datetime.now(UTC) - timedelta(minutes=20)
        manager._requests[req3.id] = req3

        manager.check_timeouts()

        # Only recent one still pending
        assert manager.get(req1.id).state == ApprovalState.PENDING
        assert manager.get(req2.id).state == ApprovalState.TIMEOUT
        assert manager.get(req3.id).state == ApprovalState.TIMEOUT


class TestApprovalEdgeCases:
    """Test edge cases and concurrent request handling"""

    def test_approve_already_approved_is_idempotent(self):
        """Approving already-approved request is safe (idempotent)"""
        manager = ApprovalManager()

        request = manager.request({"tool": "Edit"}, reason="Modifies file")
        approval_id = request.id

        manager.approve(approval_id)
        manager.approve(approval_id)  # Second approve

        updated = manager.get(approval_id)
        assert updated.state == ApprovalState.APPROVED

    def test_reject_timed_out_request_preserves_timeout(self):
        """Rejecting timed-out request does not change state"""
        manager = ApprovalManager()

        request = manager.request({"tool": "Edit"}, reason="Modifies file")
        request.timestamp = datetime.now(UTC) - timedelta(minutes=15)
        manager._requests[request.id] = request

        manager.check_timeouts()
        manager.reject(request.id)  # Try to reject after timeout

        updated = manager.get(request.id)
        assert updated.state == ApprovalState.TIMEOUT

    def test_multiple_pending_requests_tracked_independently(self):
        """Multiple pending requests tracked with separate IDs"""
        manager = ApprovalManager()

        req1 = manager.request({"tool": "Edit"}, reason="File 1")
        req2 = manager.request({"tool": "Write"}, reason="File 2")
        req3 = manager.request({"tool": "Bash"}, reason="Command")

        assert req1.id != req2.id
        assert req2.id != req3.id
        assert req1.id != req3.id

        # Approve one, reject another, leave third pending
        manager.approve(req1.id)
        manager.reject(req2.id)

        assert manager.get(req1.id).state == ApprovalState.APPROVED
        assert manager.get(req2.id).state == ApprovalState.REJECTED
        assert manager.get(req3.id).state == ApprovalState.PENDING

    def test_get_nonexistent_approval_returns_none(self):
        """Getting non-existent approval returns None"""
        manager = ApprovalManager()

        result = manager.get("nonexistent-id")

        assert result is None

    def test_approve_nonexistent_approval_raises_error(self):
        """Approving non-existent approval raises KeyError"""
        manager = ApprovalManager()

        with pytest.raises(KeyError):
            manager.approve("nonexistent-id")

    def test_reject_nonexistent_approval_raises_error(self):
        """Rejecting non-existent approval raises KeyError"""
        manager = ApprovalManager()

        with pytest.raises(KeyError):
            manager.reject("nonexistent-id")


class TestApprovalRequestTracking:
    """Test approval request tracking and retrieval"""

    def test_get_retrieves_created_approval(self):
        """get() retrieves approval by ID"""
        manager = ApprovalManager()

        request = manager.request({"tool": "Edit"}, reason="Modifies file")

        retrieved = manager.get(request.id)

        assert retrieved is not None
        assert retrieved.id == request.id
        assert retrieved.tool_call == request.tool_call
        assert retrieved.reason == request.reason

    def test_list_pending_returns_only_pending(self):
        """list_pending() returns only PENDING requests"""
        manager = ApprovalManager()

        req1 = manager.request({"tool": "Edit"}, reason="File 1")
        req2 = manager.request({"tool": "Write"}, reason="File 2")
        req3 = manager.request({"tool": "Bash"}, reason="Command")

        manager.approve(req1.id)
        manager.reject(req2.id)
        # req3 stays pending

        pending = manager.list_pending()

        assert len(pending) == 1
        assert pending[0].id == req3.id
        assert pending[0].state == ApprovalState.PENDING


class TestApprovalBatchOperations:
    """Test batch approval operations"""

    def test_approve_all_with_empty_pending_returns_zero(self):
        """approve_all() with no pending requests returns 0"""
        manager = ApprovalManager()

        count = manager.approve_all()

        assert count == 0

    def test_approve_all_approves_multiple_pending(self):
        """approve_all() approves all pending requests and returns count"""
        manager = ApprovalManager()

        # Create 3 pending requests
        req1 = manager.request({"tool": "Edit"}, reason="File 1")
        req2 = manager.request({"tool": "Write"}, reason="File 2")
        req3 = manager.request({"tool": "Bash"}, reason="Command")

        count = manager.approve_all()

        assert count == 3
        assert manager.get(req1.id).state == ApprovalState.APPROVED
        assert manager.get(req2.id).state == ApprovalState.APPROVED
        assert manager.get(req3.id).state == ApprovalState.APPROVED

    def test_approve_all_skips_non_pending(self):
        """approve_all() only approves PENDING, skips other states"""
        manager = ApprovalManager()

        # Create 3 requests, approve one, reject another
        req1 = manager.request({"tool": "Edit"}, reason="File 1")
        req2 = manager.request({"tool": "Write"}, reason="File 2")
        req3 = manager.request({"tool": "Bash"}, reason="Command")

        manager.approve(req1.id)
        manager.reject(req2.id)

        count = manager.approve_all()

        # Should only count the one pending request
        assert count == 1
        assert manager.get(req1.id).state == ApprovalState.APPROVED  # unchanged
        assert manager.get(req2.id).state == ApprovalState.REJECTED  # unchanged
        assert manager.get(req3.id).state == ApprovalState.APPROVED  # newly approved

    def test_approve_all_uses_list_pending_internally(self):
        """approve_all() uses existing list_pending() method"""
        manager = ApprovalManager()

        # Create 3 requests, approve one, reject another
        req1 = manager.request({"tool": "Edit"}, reason="File 1")
        req2 = manager.request({"tool": "Write"}, reason="File 2")
        req3 = manager.request({"tool": "Bash"}, reason="Command")

        manager.approve(req1.id)
        manager.reject(req2.id)

        # Verify list_pending shows only the one pending
        pending = manager.list_pending()
        assert len(pending) == 1
        assert pending[0].id == req3.id

        # approve_all should approve just that one
        count = manager.approve_all()
        assert count == 1
