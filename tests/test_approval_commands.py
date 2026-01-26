"""
Test approval command handlers.

Tests follow TDD RED-GREEN-REFACTOR:
1. RED: Write failing tests (this file)
2. GREEN: Implement minimal code to pass
3. REFACTOR: Clean up if needed
"""

import pytest
from src.approval.commands import ApprovalCommands
from src.approval.manager import ApprovalManager, ApprovalRequest
from src.approval.models import ApprovalState


class TestApprovalCommandParsing:
    """Test command parsing for approve/reject"""

    @pytest.mark.asyncio
    async def test_approve_with_id_returns_success_message(self):
        """approve {id} calls manager.approve() and returns success"""
        manager = ApprovalManager()
        commands = ApprovalCommands(manager)

        # Create pending approval
        request = manager.request({"tool": "Edit"}, reason="Modifies file")
        approval_id = request.id

        result = await commands.handle(f"approve {approval_id}")

        # Should approve and return truncated ID (8 chars)
        assert result == f"✅ Approved {approval_id[:8]}"
        assert manager.get(approval_id).state == ApprovalState.APPROVED

    @pytest.mark.asyncio
    async def test_reject_with_id_returns_success_message(self):
        """reject {id} calls manager.reject() and returns success"""
        manager = ApprovalManager()
        commands = ApprovalCommands(manager)

        # Create pending approval
        request = manager.request({"tool": "Write"}, reason="Creates file")
        approval_id = request.id

        result = await commands.handle(f"reject {approval_id}")

        # Should reject and return truncated ID (8 chars)
        assert result == f"❌ Rejected {approval_id[:8]}"
        assert manager.get(approval_id).state == ApprovalState.REJECTED

    @pytest.mark.asyncio
    async def test_approve_all_approves_multiple_pending(self):
        """approve all approves all pending requests"""
        manager = ApprovalManager()
        commands = ApprovalCommands(manager)

        # Create 3 pending approvals
        req1 = manager.request({"tool": "Edit"}, reason="File 1")
        req2 = manager.request({"tool": "Write"}, reason="File 2")
        req3 = manager.request({"tool": "Bash"}, reason="Command")

        result = await commands.handle("approve all")

        # Should approve all and return count
        assert result == "✅ Approved all pending (3)"
        assert manager.get(req1.id).state == ApprovalState.APPROVED
        assert manager.get(req2.id).state == ApprovalState.APPROVED
        assert manager.get(req3.id).state == ApprovalState.APPROVED

    @pytest.mark.asyncio
    async def test_unknown_command_returns_none(self):
        """Unknown commands return None (let SessionCommands handle)"""
        manager = ApprovalManager()
        commands = ApprovalCommands(manager)

        result = await commands.handle("some other command")

        assert result is None


class TestApprovalCommandEdgeCases:
    """Test edge cases and error handling"""

    @pytest.mark.asyncio
    async def test_approve_nonexistent_id_returns_error(self):
        """Approving non-existent ID returns error message"""
        manager = ApprovalManager()
        commands = ApprovalCommands(manager)

        result = await commands.handle("approve nonexistent-id")

        assert "Error" in result
        assert "not found" in result

    @pytest.mark.asyncio
    async def test_reject_nonexistent_id_returns_error(self):
        """Rejecting non-existent ID returns error message"""
        manager = ApprovalManager()
        commands = ApprovalCommands(manager)

        result = await commands.handle("reject nonexistent-id")

        assert "Error" in result
        assert "not found" in result

    @pytest.mark.asyncio
    async def test_approve_already_approved_is_idempotent(self):
        """Approving already-approved request returns success"""
        manager = ApprovalManager()
        commands = ApprovalCommands(manager)

        # Create and approve
        request = manager.request({"tool": "Edit"}, reason="Modifies file")
        manager.approve(request.id)

        # Approve again
        result = await commands.handle(f"approve {request.id}")

        assert result == f"✅ Approved {request.id[:8]}"
        assert manager.get(request.id).state == ApprovalState.APPROVED

    @pytest.mark.asyncio
    async def test_approve_all_with_no_pending_returns_zero_count(self):
        """approve all with no pending requests returns count 0"""
        manager = ApprovalManager()
        commands = ApprovalCommands(manager)

        result = await commands.handle("approve all")

        assert result == "✅ Approved all pending (0)"

    @pytest.mark.asyncio
    async def test_approve_all_skips_non_pending(self):
        """approve all only approves PENDING, skips already-approved/rejected"""
        manager = ApprovalManager()
        commands = ApprovalCommands(manager)

        # Create 3 requests, approve one, reject another
        req1 = manager.request({"tool": "Edit"}, reason="File 1")
        req2 = manager.request({"tool": "Write"}, reason="File 2")
        req3 = manager.request({"tool": "Bash"}, reason="Command")

        manager.approve(req1.id)
        manager.reject(req2.id)

        result = await commands.handle("approve all")

        # Should only approve the one pending (req3)
        assert result == "✅ Approved all pending (1)"
        assert manager.get(req1.id).state == ApprovalState.APPROVED  # unchanged
        assert manager.get(req2.id).state == ApprovalState.REJECTED  # unchanged
        assert manager.get(req3.id).state == ApprovalState.APPROVED  # newly approved


class TestApprovalCommandHelp:
    """Test help message generation"""

    def test_help_returns_command_reference(self):
        """help() returns formatted command reference"""
        manager = ApprovalManager()
        commands = ApprovalCommands(manager)

        help_text = commands.help()

        # Verify all commands documented
        assert "Approval Commands:" in help_text
        assert "approve {id}" in help_text
        assert "reject {id}" in help_text
        assert "approve all" in help_text
        assert "Approve pending operation" in help_text
        assert "Reject pending operation" in help_text
        assert "Approve all pending operations" in help_text


class TestApprovalCommandMessageFormat:
    """Test message format for mobile-friendly display"""

    @pytest.mark.asyncio
    async def test_approval_id_truncated_to_8_chars(self):
        """Approval IDs truncated to 8 chars (mobile-friendly)"""
        manager = ApprovalManager()
        commands = ApprovalCommands(manager)

        # Create request with full UUID
        request = manager.request({"tool": "Edit"}, reason="Modifies file")
        full_id = request.id
        assert len(full_id) == 36  # UUID4 format

        result = await commands.handle(f"approve {full_id}")

        # Response should have 8-char truncated ID
        assert full_id[:8] in result
        assert full_id not in result  # Full ID should not appear
