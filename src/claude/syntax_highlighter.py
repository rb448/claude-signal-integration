"""Syntax highlighting for mobile display using ANSI terminal colors."""

from pygments import highlight as pygments_highlight
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.formatters import Terminal256Formatter
from pygments.util import ClassNotFound


class SyntaxHighlighter:
    """Syntax highlighting for mobile display using ANSI terminal colors.

    Uses Pygments with Terminal256Formatter and monokai style for high-contrast,
    mobile-friendly code display in Signal messages.
    """

    def __init__(self):
        """Initialize highlighter with mobile-optimized formatter.

        Uses Terminal256Formatter with monokai style:
        - Signal mobile app supports ANSI color codes in monospace text
        - 256-color palette provides good syntax distinction
        - Monokai style has high contrast (readable on mobile screens)
        """
        self.formatter = Terminal256Formatter(style='monokai')

    def highlight(self, code: str, language: str | None = None) -> str:
        """Apply syntax highlighting with ANSI color codes.

        Args:
            code: Source code to highlight
            language: Language name (e.g., 'python', 'javascript'). If None, auto-detect.

        Returns:
            Code with ANSI color escape codes for terminal display.
            Returns empty string for empty input.
            Returns plain text if language unknown or detection fails.

        Examples:
            >>> highlighter = SyntaxHighlighter()
            >>> code = "def hello():\\n    print('world')"
            >>> result = highlighter.highlight(code, language='python')
            >>> '\\x1b[' in result  # Contains ANSI codes
            True
            >>> highlighter.highlight("", language='python')
            ''
        """
        if not code:
            return ""

        try:
            if language:
                lexer = get_lexer_by_name(language)
            else:
                lexer = guess_lexer(code)  # Auto-detect

            return pygments_highlight(code, lexer, self.formatter)
        except ClassNotFound:
            # Unknown language - return plain text (no crash)
            return code
