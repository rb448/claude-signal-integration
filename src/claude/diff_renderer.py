"""Mobile-optimized diff rendering with overlay layout."""

from src.claude.code_formatter import CodeFormatter
from src.claude.syntax_highlighter import SyntaxHighlighter
from src.claude.diff_processor import FileDiff, DiffHunk
from typing import List


class DiffRenderer:
    """Render diffs in mobile-friendly overlay format.

    Uses emoji markers for visual distinction:
    - ➕ for added lines (green in terminal)
    - ➖ for removed lines (red in terminal)
    - ≈ for context lines (unchanged code)

    Integrates with CodeFormatter for width constraints and
    SyntaxHighlighter for colored code display.
    """

    # Emoji markers for mobile visual distinction
    ADDED_MARKER = "➕"
    REMOVED_MARKER = "➖"
    CONTEXT_MARKER = "≈"
    CONTEXT_LINES = 3  # Lines of context before/after changes
    COLLAPSED_MARKER = "  ... ({n} lines unchanged)"

    def __init__(self):
        """Initialize renderer with formatter and highlighter."""
        self.formatter = CodeFormatter()
        self.highlighter = SyntaxHighlighter()

    def render(self, file_diffs: List[FileDiff], language: str = None) -> str:
        """Render diffs for mobile display.

        Args:
            file_diffs: List of FileDiff objects from DiffParser
            language: Optional language hint for syntax highlighting

        Returns:
            Formatted diff text with emoji markers, syntax highlighting,
            and width constraints for 320px mobile screens
        """
        if not file_diffs:
            return "No changes to display"

        sections = []
        for file_diff in file_diffs:
            if file_diff.is_binary:
                sections.append(f"📄 {file_diff.new_path} (binary file changed)")
                continue

            # File header
            header = f"📄 {file_diff.new_path}"
            sections.append(header)

            # Render each hunk
            for hunk in file_diff.hunks:
                hunk_text = self._render_hunk(hunk, language)
                sections.append(hunk_text)

        return "\n\n".join(sections)

    def _render_hunk(self, hunk: DiffHunk, language: str = None) -> str:
        """Render a single hunk with context collapse.

        Args:
            hunk: DiffHunk object containing diff lines
            language: Optional language hint for syntax highlighting

        Returns:
            Formatted hunk text with emoji markers and collapsed context
        """
        lines = []
        context_buffer = []

        for line in hunk.lines:
            if line.startswith('+') and not line.startswith('+++'):
                # Added line - flush context, add line
                lines.extend(self._flush_context(context_buffer))
                context_buffer = []
                content = line[1:]  # Remove + prefix
                formatted = self._format_and_highlight(content, self.ADDED_MARKER, language)
                lines.append(formatted)

            elif line.startswith('-') and not line.startswith('---'):
                # Removed line - flush context, add line
                lines.extend(self._flush_context(context_buffer))
                context_buffer = []
                content = line[1:]  # Remove - prefix
                formatted = self._format_and_highlight(content, self.REMOVED_MARKER, language)
                lines.append(formatted)

            elif line.startswith(' '):
                # Context line - add to buffer
                content = line[1:]  # Remove space prefix
                context_buffer.append(content)

        # Flush remaining context
        lines.extend(self._flush_context(context_buffer, final=True))

        return "\n".join(lines)

    def _format_and_highlight(self, content: str, marker: str, language: str = None) -> str:
        """Format and highlight a single line.

        Args:
            content: Line content (without diff prefix)
            marker: Emoji marker (ADDED_MARKER or REMOVED_MARKER)
            language: Optional language hint for syntax highlighting

        Returns:
            Formatted line with marker prefix and syntax highlighting
        """
        # Format first (width constraints on plain text)
        formatted = self.formatter.format_code(content, language)

        # Then highlight the entire formatted result
        highlighted = self.highlighter.highlight(formatted, language)

        # Add marker to first line, preserve continuation markers
        lines = highlighted.split('\n')
        result_lines = []
        for i, line in enumerate(lines):
            if i == 0:
                # First line gets the diff marker
                result_lines.append(f"{marker} {line}")
            else:
                # Continuation lines already have ↪ marker from formatter
                result_lines.append(line)

        return '\n'.join(result_lines)

    def _flush_context(self, buffer: List[str], final: bool = False) -> List[str]:
        """Flush context buffer with collapse logic.

        Args:
            buffer: List of context lines to flush
            final: True if this is the final context flush (end of hunk)

        Returns:
            List of formatted context lines with collapse markers if needed
        """
        if not buffer:
            return []

        if len(buffer) <= self.CONTEXT_LINES * 2:
            # Small context - show all
            return [f"{self.CONTEXT_MARKER} {line}" for line in buffer]

        # Large context - show first N and last N, collapse middle
        result = []
        for line in buffer[:self.CONTEXT_LINES]:
            result.append(f"{self.CONTEXT_MARKER} {line}")

        collapsed_count = len(buffer) - (self.CONTEXT_LINES * 2)
        if collapsed_count > 0:
            result.append(self.COLLAPSED_MARKER.format(n=collapsed_count))

        if not final:
            for line in buffer[-self.CONTEXT_LINES:]:
                result.append(f"{self.CONTEXT_MARKER} {line}")

        return result
