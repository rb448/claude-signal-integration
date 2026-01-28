"""Auto-approval rules for emergency mode."""
from src.approval.detector import OperationDetector, OperationType
from src.emergency.mode import EmergencyMode


class EmergencyAutoApprover:
    """
    Auto-approval rules for emergency mode.

    In emergency mode:
    - SAFE operations (Read, Grep, Glob) are auto-approved
    - DESTRUCTIVE operations (Edit, Write, Bash) still require approval

    In normal mode:
    - All operations follow normal approval workflow
    """

    def __init__(self):
        """Initialize auto-approver with operation detector."""
        self.detector = OperationDetector()

    async def should_auto_approve(self, tool_name: str, emergency_mode: EmergencyMode) -> bool:
        """
        Determine if tool should be auto-approved in current mode.

        Args:
            tool_name: Name of the tool being called (e.g., "Read", "Edit")
            emergency_mode: Emergency mode instance to check status

        Returns:
            True if tool should be auto-approved, False otherwise
        """
        # Not in emergency mode → no auto-approval
        if not await emergency_mode.is_active():
            return False

        # In emergency mode → auto-approve only SAFE tools
        # Create a minimal tool call object for classification
        class ToolCall:
            def __init__(self, tool: str):
                self.tool = tool

        tool_call = ToolCall(tool_name)
        operation_type, _ = self.detector.classify(tool_call)

        return operation_type == OperationType.SAFE
