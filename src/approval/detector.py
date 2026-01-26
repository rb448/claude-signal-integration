"""Operation detector for classifying Claude tool calls."""

from enum import Enum
from typing import Tuple


class OperationType(Enum):
    """Type of operation."""

    SAFE = "safe"
    DESTRUCTIVE = "destructive"


class OperationDetector:
    """Detect and classify operations as safe or destructive."""

    # Safe operations - read-only, don't modify state
    SAFE_TOOLS = {"read", "grep", "glob"}

    # Destructive operations - can modify files or system state
    DESTRUCTIVE_TOOLS = {"edit", "write", "bash"}

    def classify(self, tool_call) -> Tuple[OperationType, str]:
        """
        Classify a tool call as safe or destructive.

        Args:
            tool_call: ToolCall object with tool name and target/command

        Returns:
            tuple: (OperationType, reason_string)
        """
        # Handle missing tool name
        if not tool_call.tool:
            return (
                OperationType.DESTRUCTIVE,
                "Missing tool name - defaulting to destructive for safety",
            )

        # Normalize tool name to lowercase for case-insensitive matching
        tool_name = tool_call.tool.lower()

        # Check if tool is safe
        if tool_name in self.SAFE_TOOLS:
            return self._classify_safe(tool_name)

        # Check if tool is known destructive
        if tool_name in self.DESTRUCTIVE_TOOLS:
            return self._classify_destructive(tool_name)

        # Unknown tools default to destructive (fail-safe)
        return (
            OperationType.DESTRUCTIVE,
            f"Unknown tool '{tool_call.tool}' - defaulting to destructive for safety",
        )

    def _classify_safe(self, tool_name: str) -> Tuple[OperationType, str]:
        """Get classification for safe operations."""
        reasons = {
            "read": "Read operations don't modify files - safe to execute",
            "grep": "Searching content is read-only - safe to execute",
            "glob": "Listing files is read-only - safe to execute",
        }
        return (OperationType.SAFE, reasons[tool_name])

    def _classify_destructive(self, tool_name: str) -> Tuple[OperationType, str]:
        """Get classification for destructive operations."""
        reasons = {
            "edit": "Edit modifies existing files - requires approval",
            "write": "Write creates or overwrites files - requires approval",
            "bash": "Shell commands can modify system state - requires approval",
        }
        return (OperationType.DESTRUCTIVE, reasons[tool_name])
