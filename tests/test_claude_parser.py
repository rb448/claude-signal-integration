"""Tests for Claude Code CLI output parser."""

import pytest
from src.claude.parser import OutputParser, OutputType, ToolCall, Progress, Error, Response


class TestOutputParser:
    """Test OutputParser pattern matching."""

    def setup_method(self):
        """Create parser for each test."""
        self.parser = OutputParser()

    def test_parse_tool_call_read(self):
        """Test parsing Read tool call."""
        result = self.parser.parse("Using Read tool on src/main.py")
        assert isinstance(result, ToolCall)
        assert result.type == OutputType.TOOL_CALL
        assert result.tool == "Read"
        assert result.target == "src/main.py"

    def test_parse_tool_call_edit(self):
        """Test parsing Edit tool call."""
        result = self.parser.parse("Using Edit tool on config/settings.json")
        assert isinstance(result, ToolCall)
        assert result.type == OutputType.TOOL_CALL
        assert result.tool == "Edit"
        assert result.target == "config/settings.json"

    def test_parse_tool_call_write(self):
        """Test parsing Write tool call."""
        result = self.parser.parse("Using Write tool on output.txt")
        assert isinstance(result, ToolCall)
        assert result.type == OutputType.TOOL_CALL
        assert result.tool == "Write"
        assert result.target == "output.txt"

    def test_parse_tool_call_grep(self):
        """Test parsing Grep tool call."""
        result = self.parser.parse("Using Grep tool on *.py")
        assert isinstance(result, ToolCall)
        assert result.type == OutputType.TOOL_CALL
        assert result.tool == "Grep"
        assert result.target == "*.py"

    def test_parse_tool_call_glob(self):
        """Test parsing Glob tool call."""
        result = self.parser.parse("Using Glob tool on **/*.ts")
        assert isinstance(result, ToolCall)
        assert result.type == OutputType.TOOL_CALL
        assert result.tool == "Glob"
        assert result.target == "**/*.ts"

    def test_parse_tool_call_bash(self):
        """Test parsing Bash tool call."""
        result = self.parser.parse("Running: ls -la")
        assert isinstance(result, ToolCall)
        assert result.type == OutputType.TOOL_CALL
        assert result.tool == "Bash"
        assert result.command == "ls -la"

    def test_parse_progress(self):
        """Test parsing progress messages."""
        result = self.parser.parse("Analyzing code...")
        assert isinstance(result, Progress)
        assert result.type == OutputType.PROGRESS
        assert result.message == "Analyzing code..."

    def test_parse_progress_writing(self):
        """Test parsing 'Writing' progress messages."""
        result = self.parser.parse("Writing file to disk...")
        assert isinstance(result, Progress)
        assert result.type == OutputType.PROGRESS
        assert result.message == "Writing file to disk..."

    def test_parse_progress_reading(self):
        """Test parsing 'Reading' progress messages."""
        result = self.parser.parse("Reading configuration...")
        assert isinstance(result, Progress)
        assert result.type == OutputType.PROGRESS
        assert result.message == "Reading configuration..."

    def test_parse_error(self):
        """Test parsing error messages."""
        result = self.parser.parse("Error: Failed to read file")
        assert isinstance(result, Error)
        assert result.type == OutputType.ERROR
        assert result.message == "Failed to read file"

    def test_parse_error_with_details(self):
        """Test parsing error with detailed message."""
        result = self.parser.parse("Error: Permission denied accessing /etc/passwd")
        assert isinstance(result, Error)
        assert result.type == OutputType.ERROR
        assert result.message == "Permission denied accessing /etc/passwd"

    def test_parse_response(self):
        """Test parsing regular response text."""
        result = self.parser.parse("Here is the implementation for your feature.")
        assert isinstance(result, Response)
        assert result.type == OutputType.RESPONSE
        assert result.text == "Here is the implementation for your feature."

    def test_parse_empty_line(self):
        """Test parsing empty line."""
        result = self.parser.parse("")
        assert isinstance(result, Response)
        assert result.type == OutputType.RESPONSE
        assert result.text == ""
