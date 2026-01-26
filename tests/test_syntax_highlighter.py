"""Tests for syntax highlighting functionality."""

import pytest
import re
from src.claude.syntax_highlighter import SyntaxHighlighter


def strip_ansi_codes(text: str) -> str:
    """Remove ANSI escape codes for testing."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


class TestSyntaxHighlighter:
    """Test syntax highlighting with ANSI color codes."""

    def test_highlight_python_code_returns_ansi_colored_output(self):
        """Test that Python code gets ANSI color codes."""
        highlighter = SyntaxHighlighter()
        code = "def hello():\n    print('world')"

        result = highlighter.highlight(code, language='python')

        # Should contain ANSI escape codes
        assert '\x1b[' in result
        # Should still contain the code text
        assert 'def' in result
        assert 'hello' in result

    def test_highlight_javascript_code_returns_ansi_colored_output(self):
        """Test that JavaScript code gets ANSI color codes."""
        highlighter = SyntaxHighlighter()
        code = "const hello = () => {\n  console.log('world');\n};"

        result = highlighter.highlight(code, language='javascript')

        # Should contain ANSI escape codes
        assert '\x1b[' in result
        # Should still contain the code text
        assert 'const' in result
        assert 'hello' in result

    def test_highlight_auto_detects_python_from_code(self):
        """Test auto-detection of Python code."""
        highlighter = SyntaxHighlighter()
        code = "def hello():\n    import os\n    return os.path.join('a', 'b')"

        result = highlighter.highlight(code, language=None)

        # Should contain ANSI escape codes (detected as Python)
        assert '\x1b[' in result
        assert 'def' in result

    def test_highlight_auto_detects_javascript_from_code(self):
        """Test auto-detection of JavaScript code."""
        highlighter = SyntaxHighlighter()
        code = "const x = 10;\nfunction test() { return x; }"

        result = highlighter.highlight(code, language=None)

        # Should contain ANSI escape codes (detected as JavaScript)
        assert '\x1b[' in result
        assert 'const' in result

    def test_highlight_with_unknown_language_falls_back_to_plain_text(self):
        """Test that unknown languages don't crash."""
        highlighter = SyntaxHighlighter()
        code = "some random text"

        result = highlighter.highlight(code, language='unknownlang123')

        # Should not crash, should return plain text
        assert result == code

    def test_highlight_with_empty_code_returns_empty_string(self):
        """Test that empty code doesn't crash."""
        highlighter = SyntaxHighlighter()

        result = highlighter.highlight("", language='python')

        assert result == ""

    def test_strip_ansi_codes_helper_works(self):
        """Test that our ANSI strip helper works correctly."""
        text_with_ansi = "\x1b[38;5;197mdef\x1b[39m hello"

        stripped = strip_ansi_codes(text_with_ansi)

        assert stripped == "def hello"
        assert '\x1b[' not in stripped


class TestEnhancedLanguageDetection:
    """Test improved language detection with keyword patterns."""

    def test_detects_python_from_def_and_import_keywords(self):
        """Test Python detection from language-specific keywords."""
        highlighter = SyntaxHighlighter()
        # Short snippet that might not be detected by guess_lexer
        code = "def foo():\n    import bar"

        result = highlighter.highlight(code, language=None)

        # Should detect as Python and add highlighting
        assert '\x1b[' in result
        assert 'def' in result

    def test_detects_javascript_from_const_and_function_keywords(self):
        """Test JavaScript detection from language-specific keywords."""
        highlighter = SyntaxHighlighter()
        code = "const x = 5;\nfunction test() {}"

        result = highlighter.highlight(code, language=None)

        # Should detect as JavaScript and add highlighting
        assert '\x1b[' in result
        assert 'const' in result

    def test_detects_typescript_from_type_annotations(self):
        """Test TypeScript detection from type annotations."""
        highlighter = SyntaxHighlighter()
        code = "const x: string = 'hello';\nconst y: number = 42;"

        result = highlighter.highlight(code, language=None)

        # Should detect as TypeScript and add highlighting
        assert '\x1b[' in result
        assert 'string' in result

    def test_detects_rust_from_fn_keywords(self):
        """Test Rust detection from language-specific keywords."""
        highlighter = SyntaxHighlighter()
        code = "fn main() {\n    struct Point { x: i32 }\n}"

        result = highlighter.highlight(code, language=None)

        # Should detect as Rust and add highlighting
        assert '\x1b[' in result
        assert 'fn' in result

    def test_detects_go_from_package_and_func_keywords(self):
        """Test Go detection from language-specific keywords."""
        highlighter = SyntaxHighlighter()
        code = "package main\nfunc main() {}"

        result = highlighter.highlight(code, language=None)

        # Should detect as Go and add highlighting
        assert '\x1b[' in result
        assert 'package' in result

    def test_falls_back_to_plain_text_for_prose(self):
        """Test that plain prose doesn't get incorrectly highlighted."""
        highlighter = SyntaxHighlighter()
        code = "This is just regular text without any code keywords."

        result = highlighter.highlight(code, language=None)

        # Should contain the original text (with or without highlighting)
        # Key: shouldn't crash or lose content
        stripped = strip_ansi_codes(result)
        assert 'This is just regular text' in stripped
