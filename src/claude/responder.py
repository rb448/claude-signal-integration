"""Format Claude output for mobile-friendly Signal display."""

import re
from typing import List

from .parser import ParsedOutput, ToolCall, Progress, Error, Response


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
        """Format a response as plain text."""
        return response.text

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
