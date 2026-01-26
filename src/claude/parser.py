"""Parse Claude Code CLI output into structured events."""

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Generator, Optional


class OutputType(Enum):
    """Types of Claude CLI output."""
    
    TOOL_CALL = auto()
    PROGRESS = auto()
    ERROR = auto()
    RESPONSE = auto()


@dataclass
class ParsedOutput:
    """Base class for parsed output."""
    
    type: OutputType


@dataclass
class ToolCall(ParsedOutput):
    """A tool call made by Claude."""
    
    tool: str
    target: Optional[str] = None
    command: Optional[str] = None
    
    def __post_init__(self):
        """Set type to TOOL_CALL."""
        self.type = OutputType.TOOL_CALL


@dataclass
class Progress(ParsedOutput):
    """A progress/status message."""
    
    message: str
    
    def __post_init__(self):
        """Set type to PROGRESS."""
        self.type = OutputType.PROGRESS


@dataclass
class Error(ParsedOutput):
    """An error message."""
    
    message: str
    
    def __post_init__(self):
        """Set type to ERROR."""
        self.type = OutputType.ERROR


@dataclass
class Response(ParsedOutput):
    """A regular response text."""
    
    text: str
    
    def __post_init__(self):
        """Set type to RESPONSE."""
        self.type = OutputType.RESPONSE


class OutputParser:
    """Parse Claude Code CLI output into structured events."""
    
    # Regex patterns for matching output
    TOOL_CALL_PATTERN = re.compile(r"Using (Read|Edit|Write|Grep|Glob) tool on (.+)")
    BASH_PATTERN = re.compile(r"Running: (.+)")
    ERROR_PATTERN = re.compile(r"Error: (.+)")
    PROGRESS_PATTERNS = [
        re.compile(r"Analyzing\s+.+"),
        re.compile(r"Writing\s+.+"),
        re.compile(r"Reading\s+.+"),
    ]
    
    def parse(self, line: str) -> ParsedOutput:
        """
        Parse a line of Claude output.
        
        Args:
            line: A line of CLI output
            
        Returns:
            ParsedOutput: Structured representation of the output
        """
        # Check for tool calls (Read, Edit, Write, Grep, Glob)
        match = self.TOOL_CALL_PATTERN.match(line)
        if match:
            return ToolCall(
                type=OutputType.TOOL_CALL,
                tool=match.group(1),
                target=match.group(2)
            )
        
        # Check for Bash commands
        match = self.BASH_PATTERN.match(line)
        if match:
            return ToolCall(
                type=OutputType.TOOL_CALL,
                tool="Bash",
                command=match.group(1)
            )
        
        # Check for errors
        match = self.ERROR_PATTERN.match(line)
        if match:
            return Error(
                type=OutputType.ERROR,
                message=match.group(1)
            )
        
        # Check for progress patterns
        for pattern in self.PROGRESS_PATTERNS:
            if pattern.match(line):
                return Progress(
                    type=OutputType.PROGRESS,
                    message=line
                )
        
        # Default to response
        return Response(
            type=OutputType.RESPONSE,
            text=line
        )


class StreamingParser:
    """Parse streaming Claude CLI output that may arrive in chunks."""

    def __init__(self):
        """Initialize streaming parser."""
        self.parser = OutputParser()
        self.buffer = ""

    def feed(self, chunk: str) -> Generator[ParsedOutput, None, None]:
        """
        Feed a chunk of output and yield complete parsed lines.

        Args:
            chunk: A chunk of CLI output (may contain partial lines)

        Yields:
            ParsedOutput: Structured representation of complete lines
        """
        # Add chunk to buffer
        self.buffer += chunk

        # Split by newlines
        lines = self.buffer.split("\n")

        # Keep the last incomplete line in buffer
        self.buffer = lines[-1]

        # Parse and yield complete lines
        for line in lines[:-1]:
            yield self.parser.parse(line)

    def flush(self) -> Optional[ParsedOutput]:
        """
        Parse and return any remaining buffered content.

        Returns:
            ParsedOutput if buffer is non-empty, None otherwise
        """
        if self.buffer:
            result = self.parser.parse(self.buffer)
            self.buffer = ""
            return result
        return None
