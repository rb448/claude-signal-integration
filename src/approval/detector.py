"""Operation detector for classifying Claude tool calls."""

from enum import Enum


class OperationType(Enum):
    """Type of operation."""

    SAFE = "safe"
    DESTRUCTIVE = "destructive"


class OperationDetector:
    """Detect and classify operations as safe or destructive."""

    def classify(self, tool_call):
        """
        Classify a tool call as safe or destructive.

        Args:
            tool_call: ToolCall object with tool name and target/command

        Returns:
            tuple: (OperationType, reason_string)
        """
        # Stub implementation - tests should fail
        raise NotImplementedError("classify() not implemented yet")
