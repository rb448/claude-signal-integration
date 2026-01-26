"""Tests for ApprovalWorkflow coordinator."""

import asyncio
import pytest
from unittest.mock import Mock

from src.approval.detector import OperationDetector, OperationType
from src.approval.manager import ApprovalManager
from src.approval.models import ApprovalState
from src.approval.workflow import ApprovalWorkflow
from src.claude.parser import ToolCall, OutputType


@pytest.fixture
def detector():
    """Create OperationDetector instance."""
    return OperationDetector()


@pytest.fixture
def manager():
    """Create ApprovalManager instance."""
    return ApprovalManager()


@pytest.fixture
def workflow(detector, manager):
    """Create ApprovalWorkflow instance."""
    return ApprovalWorkflow(detector, manager)


class TestIntercept:
    """Tests for ApprovalWorkflow.intercept()."""

    def test_safe_operation_auto_approved(self, workflow):
        """Safe operations should be auto-approved."""
        tool_call = ToolCall(type=OutputType.TOOL_CALL, tool="Read", target="/path/to/file.py")

        approved, request_id = workflow.intercept(tool_call)

        assert approved is True
        assert request_id is None

    def test_destructive_operation_requires_approval(self, workflow):
        """Destructive operations should create approval request."""
        tool_call = ToolCall(type=OutputType.TOOL_CALL, tool="Edit", target="/path/to/file.py")

        approved, request_id = workflow.intercept(tool_call)

        assert approved is False
        assert request_id is not None
        assert isinstance(request_id, str)

    def test_bash_requires_approval(self, workflow):
        """Bash commands should require approval."""
        tool_call = ToolCall(type=OutputType.TOOL_CALL, tool="Bash", command="rm -rf /")

        approved, request_id = workflow.intercept(tool_call)

        assert approved is False
        assert request_id is not None

    def test_approval_request_stored_in_manager(self, workflow, manager):
        """Approval request should be stored in manager."""
        tool_call = ToolCall(type=OutputType.TOOL_CALL, tool="Write", target="/path/to/file.py")

        approved, request_id = workflow.intercept(tool_call)

        request = manager.get(request_id)
        assert request is not None
        assert request.state == ApprovalState.PENDING


class TestWaitForApproval:
    """Tests for ApprovalWorkflow.wait_for_approval()."""

    @pytest.mark.asyncio
    async def test_returns_true_when_approved(self, workflow, manager):
        """wait_for_approval should return True when request approved."""
        # Create a request
        tool_call = ToolCall(type=OutputType.TOOL_CALL, tool="Edit", target="/path/to/file.py")
        approved, request_id = workflow.intercept(tool_call)

        # Approve it in background after 0.1s
        async def approve_later():
            await asyncio.sleep(0.1)
            manager.approve(request_id)

        approval_task = asyncio.create_task(approve_later())

        # Wait for approval
        result = await workflow.wait_for_approval(request_id, timeout=2)

        await approval_task
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_rejected(self, workflow, manager):
        """wait_for_approval should return False when request rejected."""
        # Create a request
        tool_call = ToolCall(type=OutputType.TOOL_CALL, tool="Write", target="/path/to/file.py")
        approved, request_id = workflow.intercept(tool_call)

        # Reject it in background after 0.1s
        async def reject_later():
            await asyncio.sleep(0.1)
            manager.reject(request_id)

        rejection_task = asyncio.create_task(reject_later())

        # Wait for approval
        result = await workflow.wait_for_approval(request_id, timeout=2)

        await rejection_task
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_timeout(self, workflow):
        """wait_for_approval should return False when timeout expires."""
        # Create a request
        tool_call = ToolCall(type=OutputType.TOOL_CALL, tool="Bash", command="echo hello")
        approved, request_id = workflow.intercept(tool_call)

        # Wait with very short timeout
        result = await workflow.wait_for_approval(request_id, timeout=0.2)

        assert result is False

    @pytest.mark.asyncio
    async def test_polls_at_1_second_intervals(self, workflow, manager, monkeypatch):
        """wait_for_approval should check state every 1 second."""
        # Create a request
        tool_call = ToolCall(type=OutputType.TOOL_CALL, tool="Edit", target="/path/to/file.py")
        approved, request_id = workflow.intercept(tool_call)

        # Track sleep calls
        sleep_calls = []
        original_sleep = asyncio.sleep

        async def mock_sleep(duration):
            sleep_calls.append(duration)
            # Approve after 2 sleep calls
            if len(sleep_calls) >= 2:
                manager.approve(request_id)
            await original_sleep(0.01)  # Use short delay for test speed

        monkeypatch.setattr(asyncio, "sleep", mock_sleep)

        # Wait for approval
        result = await workflow.wait_for_approval(request_id, timeout=5)

        assert result is True
        assert len(sleep_calls) >= 2
        assert all(duration == 1 for duration in sleep_calls)


class TestFormatApprovalMessage:
    """Tests for ApprovalWorkflow.format_approval_message()."""

    def test_format_edit_message(self, workflow):
        """Format approval message for Edit operation."""
        tool_call = ToolCall(type=OutputType.TOOL_CALL, tool="Edit", target="/path/to/file.py")
        request_id = "abc123"
        reason = "Edit modifies existing files - requires approval"

        message = workflow.format_approval_message(tool_call, reason, request_id)

        assert "⚠️ Approval needed" in message
        assert "Edit" in message
        assert "/path/to/file.py" in message
        assert reason in message
        assert f"approve {request_id}" in message
        assert f"reject {request_id}" in message

    def test_format_bash_message(self, workflow):
        """Format approval message for Bash operation."""
        tool_call = ToolCall(type=OutputType.TOOL_CALL, tool="Bash", command="git commit -m 'test'")
        request_id = "xyz789"
        reason = "Shell commands can modify system state - requires approval"

        message = workflow.format_approval_message(tool_call, reason, request_id)

        assert "⚠️ Approval needed" in message
        assert "Bash" in message
        assert "git commit" in message
        assert reason in message
        assert f"approve {request_id}" in message
        assert f"reject {request_id}" in message

    def test_format_write_message(self, workflow):
        """Format approval message for Write operation."""
        tool_call = ToolCall(type=OutputType.TOOL_CALL, tool="Write", target="/new/file.py")
        request_id = "def456"
        reason = "Write creates or overwrites files - requires approval"

        message = workflow.format_approval_message(tool_call, reason, request_id)

        assert "⚠️ Approval needed" in message
        assert "Write" in message
        assert "/new/file.py" in message
        assert reason in message
