"""Integration tests for approval workflow.

Tests approval detection, request management, timeouts, and batch operations.
"""

import pytest

from src.claude.parser import OutputType, ToolCall


@pytest.mark.asyncio
async def test_approval_request_lifecycle(approval_components, authorized_number):
    """Test complete approval request lifecycle.

    Flow:
    1. Create approval request
    2. Verify pending status
    3. Approve request
    4. Verify approved status
    """
    detector = approval_components["detector"]
    manager = approval_components["manager"]

    # Create tool call requiring approval
    tool_call = ToolCall(type=OutputType.TOOL_CALL, tool="Edit", target="config.py")

    # Classify as destructive
    op_type, reason = detector.classify(tool_call)
    assert op_type.value == "destructive"

    # Create approval request
    request = manager.request(
        tool_call={"tool": tool_call.tool, "target": tool_call.target},
        reason=reason,
    )

    # Verify pending
    assert request.state.value == "pending"

    # Approve
    manager.approve(request.id)

    # Verify approved
    retrieved = manager.get(request.id)
    assert retrieved.state.value == "approved"


@pytest.mark.asyncio
async def test_approval_rejection(approval_components, authorized_number):
    """Test approval request rejection.

    Verifies:
    - Requests can be rejected
    - Rejected requests have correct state
    """
    manager = approval_components["manager"]

    # Create request
    request = manager.request(
        tool_call={"tool": "Write", "target": "new_file.txt"},
        reason="Test rejection",
    )

    # Reject
    manager.reject(request.id)

    # Verify rejected
    retrieved = manager.get(request.id)
    assert retrieved.state.value == "rejected"


@pytest.mark.asyncio
async def test_batch_approval(approval_components, authorized_number):
    """Test approving multiple requests at once.

    Verifies:
    - Multiple requests can be pending simultaneously
    - approve_all() approves all pending requests
    """
    manager = approval_components["manager"]

    # Create multiple requests
    for i in range(3):
        manager.request(
            tool_call={"tool": "Edit", "target": f"file{i}.py"},
            reason=f"Edit file {i}",
        )

    # Verify all pending
    pending = manager.list_pending()
    assert len(pending) == 3

    # Approve all
    count = manager.approve_all()
    assert count == 3

    # Verify none pending
    pending_after = manager.list_pending()
    assert len(pending_after) == 0


@pytest.mark.asyncio
async def test_safe_tool_detection(approval_components):
    """Test that safe tools are correctly classified.

    Verifies:
    - Read, Grep, Glob classified as SAFE
    - No approval required for safe operations
    """
    detector = approval_components["detector"]

    safe_tools = ["Read", "Grep", "Glob"]

    for tool_name in safe_tools:
        tool_call = ToolCall(type=OutputType.TOOL_CALL, tool=tool_name, target="test.py")
        op_type, reason = detector.classify(tool_call)

        assert op_type.value == "safe"
        assert "safe" in reason.lower()


@pytest.mark.asyncio
async def test_destructive_tool_detection(approval_components):
    """Test that destructive tools are correctly classified.

    Verifies:
    - Edit, Write, Bash classified as DESTRUCTIVE
    - Approval required for destructive operations
    """
    detector = approval_components["detector"]

    destructive_tools = ["Edit", "Write", "Bash"]

    for tool_name in destructive_tools:
        tool_call = ToolCall(type=OutputType.TOOL_CALL, tool=tool_name, target="test.py")
        op_type, reason = detector.classify(tool_call)

        assert op_type.value == "destructive"
        assert "approval" in reason.lower()
