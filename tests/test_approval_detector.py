"""Tests for operation detector (TDD RED phase)."""

import pytest
from src.approval.detector import OperationDetector, OperationType
from src.claude.parser import ToolCall, OutputType


class TestOperationDetector:
    """Test operation classification."""

    def test_read_is_safe(self):
        """Read operations should be classified as safe."""
        detector = OperationDetector()
        tool_call = ToolCall(type=OutputType.TOOL_CALL, tool="Read", target="file.py")

        op_type, reason = detector.classify(tool_call)

        assert op_type == OperationType.SAFE
        assert "read" in reason.lower() or "safe" in reason.lower()

    def test_grep_is_safe(self):
        """Grep operations should be classified as safe."""
        detector = OperationDetector()
        tool_call = ToolCall(type=OutputType.TOOL_CALL, tool="Grep", target="pattern")

        op_type, reason = detector.classify(tool_call)

        assert op_type == OperationType.SAFE
        assert "search" in reason.lower() or "safe" in reason.lower()

    def test_glob_is_safe(self):
        """Glob operations should be classified as safe."""
        detector = OperationDetector()
        tool_call = ToolCall(type=OutputType.TOOL_CALL, tool="Glob", target="*.py")

        op_type, reason = detector.classify(tool_call)

        assert op_type == OperationType.SAFE
        assert "list" in reason.lower() or "safe" in reason.lower()

    def test_edit_is_destructive(self):
        """Edit operations should be classified as destructive."""
        detector = OperationDetector()
        tool_call = ToolCall(type=OutputType.TOOL_CALL, tool="Edit", target="file.py")

        op_type, reason = detector.classify(tool_call)

        assert op_type == OperationType.DESTRUCTIVE
        assert "modif" in reason.lower() or "edit" in reason.lower()

    def test_write_is_destructive(self):
        """Write operations should be classified as destructive."""
        detector = OperationDetector()
        tool_call = ToolCall(type=OutputType.TOOL_CALL, tool="Write", target="file.py")

        op_type, reason = detector.classify(tool_call)

        assert op_type == OperationType.DESTRUCTIVE
        assert "creat" in reason.lower() or "overwrit" in reason.lower() or "write" in reason.lower()

    def test_bash_is_destructive(self):
        """Bash operations should be classified as destructive."""
        detector = OperationDetector()
        tool_call = ToolCall(type=OutputType.TOOL_CALL, tool="Bash", command="git push")

        op_type, reason = detector.classify(tool_call)

        assert op_type == OperationType.DESTRUCTIVE
        assert "shell" in reason.lower() or "command" in reason.lower()

    def test_bash_read_only_still_destructive(self):
        """Even read-only bash commands are destructive (conservative)."""
        detector = OperationDetector()
        tool_call = ToolCall(type=OutputType.TOOL_CALL, tool="Bash", command="ls -la")

        op_type, reason = detector.classify(tool_call)

        assert op_type == OperationType.DESTRUCTIVE
        assert "shell" in reason.lower() or "command" in reason.lower()

    def test_unknown_tool_defaults_to_destructive(self):
        """Unknown tools should default to destructive (fail-safe)."""
        detector = OperationDetector()
        tool_call = ToolCall(type=OutputType.TOOL_CALL, tool="UnknownTool", target="something")

        op_type, reason = detector.classify(tool_call)

        assert op_type == OperationType.DESTRUCTIVE
        assert "unknown" in reason.lower()

    def test_missing_tool_name_handled(self):
        """Missing tool name should be handled gracefully."""
        detector = OperationDetector()
        tool_call = ToolCall(type=OutputType.TOOL_CALL, tool=None, target="file.py")

        op_type, reason = detector.classify(tool_call)

        assert op_type == OperationType.DESTRUCTIVE
        assert len(reason) > 0

    def test_all_safe_operations_covered(self):
        """Verify all safe operations are correctly classified."""
        detector = OperationDetector()
        safe_tools = ["Read", "Grep", "Glob"]

        for tool in safe_tools:
            tool_call = ToolCall(type=OutputType.TOOL_CALL, tool=tool, target="test")
            op_type, reason = detector.classify(tool_call)
            assert op_type == OperationType.SAFE, f"{tool} should be SAFE"

    def test_all_destructive_operations_covered(self):
        """Verify all destructive operations are correctly classified."""
        detector = OperationDetector()
        destructive_tools = ["Edit", "Write", "Bash"]

        for tool in destructive_tools:
            if tool == "Bash":
                tool_call = ToolCall(type=OutputType.TOOL_CALL, tool=tool, command="echo test")
            else:
                tool_call = ToolCall(type=OutputType.TOOL_CALL, tool=tool, target="file.py")
            op_type, reason = detector.classify(tool_call)
            assert op_type == OperationType.DESTRUCTIVE, f"{tool} should be DESTRUCTIVE"

    def test_case_insensitive_tool_matching(self):
        """Tool names should be matched case-insensitively."""
        detector = OperationDetector()

        # Test lowercase
        tool_call = ToolCall(type=OutputType.TOOL_CALL, tool="read", target="file.py")
        op_type, _ = detector.classify(tool_call)
        assert op_type == OperationType.SAFE

        # Test uppercase
        tool_call = ToolCall(type=OutputType.TOOL_CALL, tool="EDIT", target="file.py")
        op_type, _ = detector.classify(tool_call)
        assert op_type == OperationType.DESTRUCTIVE
