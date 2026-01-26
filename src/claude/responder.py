"""Format Claude output for mobile-friendly Signal display."""

import re
import time
from typing import List

from .parser import ParsedOutput, ToolCall, Progress, Error, Response
from .code_formatter import CodeFormatter, LengthDetector
from .syntax_highlighter import SyntaxHighlighter
from .diff_processor import DiffParser, SummaryGenerator
from .diff_renderer import DiffRenderer
from ..signal.attachment_handler import AttachmentHandler


class SignalResponder:
    """Format parsed Claude events into readable Signal messages."""

    # Emoji constants for tool visualization
    TOOL_EMOJIS = {
        "Read": "📖",
        "Edit": "✏️",
        "Write": "💾",
        "Bash": "🔧",
        "Grep": "🔍",
        "Glob": "📁",
    }

    # Emoji constants for status messages
    PROGRESS_EMOJI = "⏳"
    ERROR_EMOJI = "❌"

    def __init__(self, signal_api_url: str = "http://localhost:8080"):
        """
        Initialize SignalResponder with code display components.

        Args:
            signal_api_url: Signal API URL for attachments
        """
        # Code display components
        self.code_formatter = CodeFormatter()
        self.syntax_highlighter = SyntaxHighlighter()
        self.length_detector = LengthDetector()
        self.diff_parser = DiffParser()
        self.diff_renderer = DiffRenderer()
        self.summary_generator = SummaryGenerator()
        self.attachment_handler = AttachmentHandler(signal_api_url)
        self.signal_api_url = signal_api_url

    def format(self, parsed: ParsedOutput) -> str:
        """
        Format a parsed output event for Signal display.

        Args:
            parsed: ParsedOutput event from parser

        Returns:
            Formatted string optimized for mobile display
        """
        if isinstance(parsed, ToolCall):
            return self._format_tool_call(parsed)
        elif isinstance(parsed, Progress):
            return self._format_progress(parsed)
        elif isinstance(parsed, Error):
            return self._format_error(parsed)
        elif isinstance(parsed, Response):
            return self._format_response(parsed)
        else:
            # Fallback for unknown types
            return str(parsed)

    def _format_tool_call(self, tool_call: ToolCall) -> str:
        """Format a tool call with emoji and target/command."""
        emoji = self.TOOL_EMOJIS.get(tool_call.tool, "🔧")

        if tool_call.tool == "Bash" and tool_call.command:
            return f"{emoji} Bash: {tool_call.command}"
        elif tool_call.target:
            return f"{emoji} {tool_call.tool}: {tool_call.target}"
        else:
            return f"{emoji} {tool_call.tool}"

    def _format_progress(self, progress: Progress) -> str:
        """Format a progress message with emoji."""
        message = progress.message
        if not message.endswith("..."):
            message += "..."
        return f"{self.PROGRESS_EMOJI} {message}"

    def _format_error(self, error: Error) -> str:
        """Format an error message with emoji."""
        return f"{self.ERROR_EMOJI} Error: {error.message}"

    def _format_response(self, response: Response) -> str:
        """Format a response with code/diff detection and formatting."""
        return self._format_response_with_code(response.text)

    def _format_response_with_code(self, content: str) -> str:
        """Format response with code/diff detection and formatting."""
        # Detect git diff output (highest priority - most structured)
        if self._is_diff(content):
            return self._format_diff(content)

        # Detect code blocks ```language...```
        if "```" in content:
            return self._format_code_blocks(content)

        # Plain text - no special formatting
        return content

    def _is_diff(self, content: str) -> bool:
        """Check if content is git diff output."""
        return content.strip().startswith("diff --git")

    def _format_diff(self, content: str) -> str:
        """Format git diff with summary and rendering."""
        # Parse diff
        file_diffs = self.diff_parser.parse(content)

        if not file_diffs:
            # Parsing failed, return as-is
            return content

        # Generate plain-English summary
        summary = self.summary_generator.generate(file_diffs)

        # Render diff
        rendered = self.diff_renderer.render(file_diffs)

        return f"**Changes:**\n{summary}\n\n{rendered}"

    def _format_code_blocks(self, content: str) -> str:
        """Format embedded code blocks."""
        # Find all code blocks: ```language\ncode\n```
        pattern = r'```(\w+)?\n(.*?)\n```'

        def replace_code(match):
            language = match.group(1)
            code = match.group(2)

            # Check length - attachment vs inline
            if self.length_detector.should_attach(code):
                line_count = code.count('\n') + 1
                return f"[Code too long ({line_count} lines) - attachment coming...]"

            # Format and highlight for inline display
            formatted = self.code_formatter.format_code(code, language)
            highlighted = self.syntax_highlighter.highlight(formatted, language)
            return f"```\n{highlighted}\n```"

        return re.sub(pattern, replace_code, content, flags=re.DOTALL)

    async def send_with_attachments(
        self,
        formatted_message: str,
        code_blocks: List[tuple[str, str]],
        recipient: str
    ) -> str:
        """
        Upload code attachments and update message with attachment confirmations.

        Args:
            formatted_message: Message with [attachment needed] markers
            code_blocks: List of (code_content, filename) tuples for attachments
            recipient: Phone number to send attachments to (E.164 format)

        Returns:
            Updated message with attachment confirmations replacing markers
        """
        for code, filename in code_blocks:
            # Calculate line count for the marker
            line_count = code.count('\n') + 1
            marker = f"[Code too long ({line_count} lines) - attachment coming...]"

            # Upload attachment
            attachment_id = await self.attachment_handler.send_code_file(
                recipient, code, filename
            )

            if attachment_id:
                # Replace marker with confirmation
                confirmation = f"📎 Sent {filename} ({line_count} lines)"
                formatted_message = formatted_message.replace(marker, confirmation)
            # If upload fails, leave marker in place (attachment_handler logs the error)

        return formatted_message

    def split_for_signal(self, text: str, max_len: int = 1600) -> List[str]:
        """
        Split long text into Signal-safe chunks.

        Args:
            text: Text to split
            max_len: Maximum length per chunk (default 1600 for mobile safety)

        Returns:
            List of text chunks, each under max_len
        """
        if len(text) <= max_len:
            return [text]

        chunks = []
        remaining = text
        continuation_marker = "...continued"

        while remaining:
            # If remaining fits, add it and we're done
            if len(remaining) <= max_len:
                chunks.append(remaining)
                break

            # Find code block boundaries and avoid splitting them
            code_block_start = remaining.find("```")
            if code_block_start != -1 and code_block_start < max_len:
                # Find the closing ```
                code_block_end = remaining.find("```", code_block_start + 3)
                if code_block_end != -1:
                    # If entire code block fits in max_len, keep it together
                    block_end = code_block_end + 3
                    if block_end <= max_len:
                        chunk = remaining[:block_end]
                        chunks.append(chunk)
                        remaining = remaining[block_end:].lstrip()
                        continue
                    # Code block is too large but starts soon - split before it
                    if code_block_start > 0:
                        chunk = remaining[:code_block_start].rstrip()
                        chunks.append(chunk)
                        remaining = remaining[code_block_start:]
                        continue

            # Reserve space for continuation marker
            effective_max = max_len - len(continuation_marker)

            # Try to split on sentence boundary
            chunk = remaining[:effective_max]

            # Look for sentence endings (. ! ?) near the end
            split_point = None
            for delimiter in [". ", "! ", "? ", "\n\n"]:
                last_delim = chunk.rfind(delimiter)
                if last_delim > effective_max * 0.7:  # Must be in last 30% to be useful
                    split_point = last_delim + len(delimiter)
                    break

            if split_point:
                chunk = remaining[:split_point]
            else:
                chunk = remaining[:effective_max]

            # Add continuation marker if there's more text coming
            chunk = chunk.rstrip() + continuation_marker

            chunks.append(chunk)
            remaining = remaining[len(chunk) - len(continuation_marker):].lstrip()

        return chunks


class MessageBatcher:
    """Batch rapid message updates to prevent Signal flooding."""

    def __init__(self, min_batch_interval: float = 0.5):
        """
        Initialize message batcher.

        Args:
            min_batch_interval: Minimum time (seconds) between message sends
        """
        self.min_batch_interval = min_batch_interval
        self._buffer: List[str] = []
        self._last_flush_time = time.time()

    def add(self, message: str) -> None:
        """
        Add a message to the buffer.

        Args:
            message: Message to buffer
        """
        self._buffer.append(message)

    def should_flush(self) -> bool:
        """
        Check if buffer should be flushed.

        Returns:
            True if buffer has messages AND min interval has passed
        """
        if not self._buffer:
            return False

        time_since_flush = time.time() - self._last_flush_time
        return time_since_flush >= self.min_batch_interval

    def flush(self) -> List[str]:
        """
        Get buffered messages and reset buffer.

        Returns:
            List of buffered messages
        """
        messages = self._buffer.copy()
        self._buffer.clear()
        self._last_flush_time = time.time()
        return messages
