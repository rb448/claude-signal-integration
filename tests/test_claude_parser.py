"""Tests for Claude Code CLI output parser."""

import pytest
from src.claude.parser import (
    OutputParser,
    StreamingParser,
    OutputType,
    ToolCall,
    Progress,
    Error,
    Response,
)


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


class TestStreamingParser:
    """Test StreamingParser for chunked input."""

    def setup_method(self):
        """Create streaming parser for each test."""
        self.parser = StreamingParser()

    def test_feed_complete_line(self):
        """Test feeding a complete line with newline."""
        results = list(self.parser.feed("Using Read tool on file.py\n"))
        assert len(results) == 1
        assert isinstance(results[0], ToolCall)
        assert results[0].tool == "Read"

    def test_feed_multiple_lines(self):
        """Test feeding multiple lines at once."""
        chunk = "Using Read tool on file.py\nAnalyzing code...\nError: Failed\n"
        results = list(self.parser.feed(chunk))
        assert len(results) == 3
        assert isinstance(results[0], ToolCall)
        assert isinstance(results[1], Progress)
        assert isinstance(results[2], Error)

    def test_feed_partial_line(self):
        """Test feeding partial line (no newline)."""
        results = list(self.parser.feed("Using Read tool on"))
        assert len(results) == 0  # Incomplete line buffered

        # Complete the line
        results = list(self.parser.feed(" file.py\n"))
        assert len(results) == 1
        assert isinstance(results[0], ToolCall)
        assert results[0].target == "file.py"

    def test_feed_chunks_across_lines(self):
        """Test feeding chunks that break across line boundaries."""
        # First chunk ends mid-line
        results1 = list(self.parser.feed("Using Read tool on file1.py\nUsing"))
        assert len(results1) == 1
        assert results1[0].target == "file1.py"

        # Second chunk completes previous line and starts new one
        results2 = list(self.parser.feed(" Edit tool on file2.py\nAnalyzing"))
        assert len(results2) == 1
        assert results2[0].target == "file2.py"

        # Third chunk completes the line
        results3 = list(self.parser.feed(" code...\n"))
        assert len(results3) == 1
        assert isinstance(results3[0], Progress)

    def test_flush_empty_buffer(self):
        """Test flushing with empty buffer."""
        result = self.parser.flush()
        assert result is None

    def test_flush_with_buffered_content(self):
        """Test flushing with content in buffer."""
        # Feed incomplete line
        list(self.parser.feed("Using Read tool on file.py"))

        # Flush should return the buffered content
        result = self.parser.flush()
        assert result is not None
        assert isinstance(result, ToolCall)
        assert result.target == "file.py"

        # Buffer should be empty after flush
        result2 = self.parser.flush()
        assert result2 is None

    def test_flush_clears_buffer(self):
        """Test that flush clears the buffer."""
        self.parser.feed("Partial line")
        self.parser.flush()

        # Buffer should be empty
        assert self.parser.buffer == ""

    def test_mixed_streaming(self):
        """Test realistic streaming scenario."""
        # Simulate chunks arriving
        all_results = []

        all_results.extend(self.parser.feed("Using Read tool"))
        all_results.extend(self.parser.feed(" on src/main.py\nAnalyzing"))
        all_results.extend(self.parser.feed(" code...\nError: File not"))
        all_results.extend(self.parser.feed(" found\nWriting file...\n"))

        # Should have parsed 4 complete lines
        assert len(all_results) == 4
        assert isinstance(all_results[0], ToolCall)
        assert isinstance(all_results[1], Progress)
        assert isinstance(all_results[2], Error)
        assert isinstance(all_results[3], Progress)

        # No remaining buffer
        assert self.parser.buffer == ""
