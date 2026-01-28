"""
Integration tests for emergency mode approval override.

Verifies end-to-end emergency mode behavior with real components (not mocked).
"""

import pytest
from src.emergency.mode import EmergencyMode
from src.emergency.auto_approver import EmergencyAutoApprover
from src.approval.detector import OperationDetector
from src.approval.manager import ApprovalManager
from src.approval.workflow import ApprovalWorkflow
from src.claude.parser import ToolCall, OutputType


@pytest.fixture
async def emergency_mode(tmp_path):
    """Create real EmergencyMode instance."""
    db_path = str(tmp_path / "test_emergency.db")
    mode = EmergencyMode(db_path=db_path)
    await mode.initialize()
    return mode


@pytest.fixture
def auto_approver():
    """Create real EmergencyAutoApprover instance."""
    return EmergencyAutoApprover()


@pytest.fixture
def detector():
    """Create real OperationDetector instance."""
    return OperationDetector()


@pytest.fixture
def manager():
    """Create real ApprovalManager instance."""
    return ApprovalManager()


@pytest.fixture
def workflow(detector, manager, auto_approver, emergency_mode):
    """Create real ApprovalWorkflow with emergency components."""
    return ApprovalWorkflow(
        detector=detector,
        manager=manager,
        emergency_auto_approver=auto_approver,
        emergency_mode=emergency_mode
    )


@pytest.mark.asyncio
async def test_emergency_approval_override_lifecycle(workflow, emergency_mode, manager):
    """
    Test complete lifecycle of emergency mode approval override.

    Scenario:
    1. Normal mode: Read tool → approval request created
    2. Activate emergency mode
    3. Read tool → auto-approved, no request created
    4. Edit tool → approval request created (still requires approval)
    5. Deactivate emergency mode
    6. Read tool → approval request created (back to normal)
    """
    thread_id = "+1234567890"

    # Step 1: Normal mode - Read should create approval request
    read_call = ToolCall(type=OutputType.TOOL_CALL, tool="Read", target="/path/to/file.py")
    result1 = await workflow.request_approval(read_call, thread_id)

    assert result1 is not None  # Request created
    assert isinstance(result1, str)
    assert len(manager.list_pending()) == 1

    # Clear pending approvals
    manager.approve(result1)

    # Step 2: Activate emergency mode
    await emergency_mode.activate(thread_id)
    assert await emergency_mode.is_active()

    # Step 3: Read should be auto-approved in emergency mode
    read_call2 = ToolCall(type=OutputType.TOOL_CALL, tool="Read", target="/another/file.py")
    result2 = await workflow.request_approval(read_call2, thread_id)

    assert result2 is None  # Auto-approved, no request
    assert len(manager.list_pending()) == 0

    # Step 4: Edit should still require approval in emergency mode
    edit_call = ToolCall(type=OutputType.TOOL_CALL, tool="Edit", target="/path/to/file.py")
    result3 = await workflow.request_approval(edit_call, thread_id)

    assert result3 is not None  # Request created
    assert isinstance(result3, str)
    assert len(manager.list_pending()) == 1

    # Clear pending approvals
    manager.approve(result3)

    # Step 5: Deactivate emergency mode
    await emergency_mode.deactivate()
    assert not await emergency_mode.is_active()

    # Step 6: Read should create approval request again (back to normal)
    read_call3 = ToolCall(type=OutputType.TOOL_CALL, tool="Read", target="/third/file.py")
    result4 = await workflow.request_approval(read_call3, thread_id)

    assert result4 is not None  # Request created
    assert isinstance(result4, str)
    assert len(manager.list_pending()) == 1


@pytest.mark.asyncio
async def test_emergency_auto_approval_only_when_both_conditions_met(workflow, emergency_mode, manager):
    """
    Auto-approval should only apply when BOTH conditions are true:
    1. Emergency mode is active
    2. Tool is classified as SAFE

    Test all combinations of conditions.
    """
    thread_id = "+1234567890"

    # Condition matrix:
    # Emergency=False, Tool=SAFE (Read) → Request created
    # Emergency=False, Tool=DESTRUCTIVE (Edit) → Request created
    # Emergency=True, Tool=SAFE (Read) → Auto-approved
    # Emergency=True, Tool=DESTRUCTIVE (Edit) → Request created

    # Test 1: Emergency=False, Tool=SAFE
    assert not await emergency_mode.is_active()
    read_call = ToolCall(type=OutputType.TOOL_CALL, tool="Read", target="/file.py")
    result1 = await workflow.request_approval(read_call, thread_id)
    assert result1 is not None  # Request created
    assert len(manager.list_pending()) == 1
    manager.approve(result1)

    # Test 2: Emergency=False, Tool=DESTRUCTIVE
    edit_call = ToolCall(type=OutputType.TOOL_CALL, tool="Edit", target="/file.py")
    result2 = await workflow.request_approval(edit_call, thread_id)
    assert result2 is not None  # Request created
    assert len(manager.list_pending()) == 1
    manager.approve(result2)

    # Activate emergency mode
    await emergency_mode.activate(thread_id)

    # Test 3: Emergency=True, Tool=SAFE
    grep_call = ToolCall(type=OutputType.TOOL_CALL, tool="Grep", target="pattern")
    result3 = await workflow.request_approval(grep_call, thread_id)
    assert result3 is None  # Auto-approved
    assert len(manager.list_pending()) == 0

    # Test 4: Emergency=True, Tool=DESTRUCTIVE
    write_call = ToolCall(type=OutputType.TOOL_CALL, tool="Write", target="/file.py")
    result4 = await workflow.request_approval(write_call, thread_id)
    assert result4 is not None  # Request created
    assert len(manager.list_pending()) == 1


@pytest.mark.asyncio
async def test_all_safe_tools_auto_approved_in_emergency(workflow, emergency_mode, manager):
    """
    Verify all SAFE tools (Read, Grep, Glob) are auto-approved in emergency mode.
    """
    thread_id = "+1234567890"

    # Activate emergency mode
    await emergency_mode.activate(thread_id)

    # Test Read
    read_call = ToolCall(type=OutputType.TOOL_CALL, tool="Read", target="/file.py")
    result1 = await workflow.request_approval(read_call, thread_id)
    assert result1 is None
    assert len(manager.list_pending()) == 0

    # Test Grep
    grep_call = ToolCall(type=OutputType.TOOL_CALL, tool="Grep", target="pattern")
    result2 = await workflow.request_approval(grep_call, thread_id)
    assert result2 is None
    assert len(manager.list_pending()) == 0

    # Test Glob
    glob_call = ToolCall(type=OutputType.TOOL_CALL, tool="Glob", target="*.py")
    result3 = await workflow.request_approval(glob_call, thread_id)
    assert result3 is None
    assert len(manager.list_pending()) == 0


@pytest.mark.asyncio
async def test_all_destructive_tools_require_approval_in_emergency(workflow, emergency_mode, manager):
    """
    Verify all DESTRUCTIVE tools (Edit, Write, Bash) still require approval in emergency mode.
    """
    thread_id = "+1234567890"

    # Activate emergency mode
    await emergency_mode.activate(thread_id)

    # Test Edit
    edit_call = ToolCall(type=OutputType.TOOL_CALL, tool="Edit", target="/file.py")
    result1 = await workflow.request_approval(edit_call, thread_id)
    assert result1 is not None
    assert len(manager.list_pending()) == 1
    manager.approve(result1)

    # Test Write
    write_call = ToolCall(type=OutputType.TOOL_CALL, tool="Write", target="/file.py")
    result2 = await workflow.request_approval(write_call, thread_id)
    assert result2 is not None
    assert len(manager.list_pending()) == 1
    manager.approve(result2)

    # Test Bash
    bash_call = ToolCall(type=OutputType.TOOL_CALL, tool="Bash", command="git commit")
    result3 = await workflow.request_approval(bash_call, thread_id)
    assert result3 is not None
    assert len(manager.list_pending()) == 1
