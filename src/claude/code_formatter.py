"""Mobile-optimized code formatting and length detection."""


class CodeFormatter:
    """Format code for mobile display with width constraints."""

    MAX_WIDTH = 50  # chars for 320px mobile screens (~6px per monospace char)
    CONTINUATION = " ↪ "

    def format_code(self, code: str, language: str = None) -> str:
        """Format code for mobile display with width constraints.

        Args:
            code: Source code to format
            language: Optional language hint (unused in basic implementation)

        Returns:
            Formatted code with lines wrapped at MAX_WIDTH
        """
        if not code:
            return ""

        lines = code.split('\n')
        formatted_lines = []

        for line in lines:
            if len(line) <= self.MAX_WIDTH:
                # Line fits within width constraint
                formatted_lines.append(line)
            else:
                # Line needs wrapping
                wrapped = self._wrap_line(line)
                formatted_lines.extend(wrapped)

        return '\n'.join(formatted_lines)

    def _wrap_line(self, line: str) -> list[str]:
        """Wrap a single line at MAX_WIDTH, preserving indentation.

        Args:
            line: Line to wrap

        Returns:
            List of wrapped lines with continuation markers
        """
        # Detect leading whitespace (indentation)
        indent = self._get_indent(line)
        content = line[len(indent):]

        # Calculate effective width (account for continuation marker on wrapped lines)
        first_line_width = self.MAX_WIDTH
        continuation_width = self.MAX_WIDTH - len(self.CONTINUATION)

        wrapped_lines = []
        remaining = content

        # First line gets full width
        if len(indent + remaining) <= first_line_width:
            return [line]

        # Need to wrap
        first_chunk = self._break_at_boundary(remaining, first_line_width - len(indent))
        wrapped_lines.append(indent + first_chunk)
        remaining = remaining[len(first_chunk):].lstrip()

        # Subsequent lines get continuation marker
        while remaining:
            chunk = self._break_at_boundary(remaining, continuation_width - len(indent))
            wrapped_lines.append(indent + self.CONTINUATION + chunk)
            remaining = remaining[len(chunk):].lstrip()

        return wrapped_lines

    def _get_indent(self, line: str) -> str:
        """Extract leading whitespace from line.

        Args:
            line: Line to analyze

        Returns:
            Leading whitespace string
        """
        indent_len = len(line) - len(line.lstrip())
        return line[:indent_len]

    def _break_at_boundary(self, text: str, max_width: int) -> str:
        """Break text at word boundary near max_width.

        Args:
            text: Text to break
            max_width: Maximum width for chunk

        Returns:
            Chunk of text at or below max_width, preferring word boundaries
        """
        if len(text) <= max_width:
            return text

        # Try to find last space before max_width
        chunk = text[:max_width]
        last_space = chunk.rfind(' ')

        if last_space > 0:
            # Break at space
            return chunk[:last_space]
        else:
            # No space found, hard break at max_width
            return chunk


class LengthDetector:
    """Detect whether code should display inline or as attachment."""

    INLINE_MAX = 20   # Max lines for inline display
    ATTACH_MIN = 100  # Min lines for forced attachment

    def should_attach(self, code: str) -> bool:
        """Determine if code should be sent as attachment vs inline.

        Args:
            code: Source code to analyze

        Returns:
            True if code should be sent as attachment, False for inline
        """
        if not code:
            return False

        lines = code.count('\n') + 1

        if lines > self.ATTACH_MIN:
            return True
        if lines <= self.INLINE_MAX:
            return False

        # Mid-range (20-100 lines): default to inline
        # User can request full view with /code full command (later task)
        return False

    def get_display_mode(self, code: str) -> str:
        """Return display mode for code.

        Args:
            code: Source code to analyze

        Returns:
            "inline" or "attachment"
        """
        return "attachment" if self.should_attach(code) else "inline"
