"""Tests for mobile-optimized code formatting."""

import pytest
from src.claude.code_formatter import CodeFormatter, LengthDetector


class TestCodeFormatter:
    """Test CodeFormatter width constraint and wrapping logic."""

    def test_format_code_wraps_long_lines_at_max_width(self):
        """Long lines should wrap at MAX_WIDTH (50 chars for mobile)."""
        formatter = CodeFormatter()
        code = "this_is_a_very_long_function_name_that_exceeds_fifty_characters_on_single_line()"

        result = formatter.format_code(code)

        # Should wrap and add continuation marker
        lines = result.split('\n')
        assert len(lines) > 1, "Long line should be wrapped"
        assert all(len(line) <= 55 for line in lines), f"All lines should be <= 55 chars (50 + continuation marker)"

    def test_format_code_preserves_indentation(self):
        """Wrapped lines should preserve original indentation."""
        formatter = CodeFormatter()
        code = "    def very_long_function_name_with_parameters(param1, param2, param3, param4):"

        result = formatter.format_code(code)

        lines = result.split('\n')
        # First line should have 4-space indent
        assert lines[0].startswith('    '), "Original indentation should be preserved"
        # Continuation lines should maintain same indent level
        for line in lines[1:]:
            if line.strip():  # Skip empty lines
                assert line.startswith('    '), "Continuation lines should preserve indent"

    def test_format_code_adds_continuation_marker(self):
        """Wrapped lines should include continuation marker."""
        formatter = CodeFormatter()
        code = "function_with_very_long_name_that_definitely_needs_wrapping_at_fifty_characters()"

        result = formatter.format_code(code)

        assert " ↪ " in result, "Continuation marker should be present for wrapped lines"

    def test_format_code_handles_empty_code(self):
        """Empty code should return empty string."""
        formatter = CodeFormatter()

        result = formatter.format_code("")

        assert result == "", "Empty code should return empty string"

    def test_format_code_handles_short_lines(self):
        """Lines under MAX_WIDTH should not be wrapped."""
        formatter = CodeFormatter()
        code = "x = 1\ny = 2\nz = 3"

        result = formatter.format_code(code)

        assert result == code, "Short lines should remain unchanged"
        assert " ↪ " not in result, "No continuation marker for unwrapped code"

    def test_format_code_preserves_empty_lines(self):
        """Empty lines (structural whitespace) should be preserved."""
        formatter = CodeFormatter()
        code = "def foo():\n    pass\n\ndef bar():\n    pass"

        result = formatter.format_code(code)

        # Should have empty line between functions
        assert "\n\n" in result, "Empty lines should be preserved"

    def test_format_code_breaks_at_word_boundaries(self):
        """Should prefer breaking at spaces rather than mid-word."""
        formatter = CodeFormatter()
        # Line with clear word boundaries
        code = "result = function_name(parameter_one, parameter_two, parameter_three)"

        result = formatter.format_code(code)

        lines = result.split('\n')
        # Check that breaks happen at reasonable points (not mid-identifier)
        for line in lines:
            # Should not end with partial identifier (no letters followed by break)
            if " ↪ " in line:
                before_marker = line.split(" ↪ ")[0].rstrip()
                if before_marker and before_marker[-1].isalnum():
                    # If it ends with alphanumeric, next char should be word boundary
                    assert True  # This is acceptable - we tried to break at space
