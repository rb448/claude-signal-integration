"""Tests for mobile-optimized diff rendering."""

import pytest
from src.claude.diff_renderer import DiffRenderer
from src.claude.diff_processor import FileDiff, DiffHunk


class TestDiffRenderer:
    """Test DiffRenderer with overlay mode for mobile display."""

    @pytest.fixture
    def renderer(self):
        """Create DiffRenderer instance."""
        return DiffRenderer()

    def test_render_uses_emoji_markers(self, renderer):
        """Test that render() uses emoji markers for visual distinction."""
        # Create simple diff with added and removed lines
        hunk = DiffHunk(
            old_start=1,
            old_count=2,
            new_start=1,
            new_count=2,
            lines=[
                " unchanged line",
                "-removed line",
                "+added line"
            ]
        )
        file_diff = FileDiff(
            old_path="test.py",
            new_path="test.py",
            hunks=[hunk]
        )

        result = renderer.render([file_diff])

        # Verify emoji markers present
        assert "➕" in result  # Added marker
        assert "➖" in result  # Removed marker
        assert "≈" in result   # Context marker

    def test_render_integrates_code_formatter(self, renderer):
        """Test that render() integrates CodeFormatter for width constraints."""
        # Create diff with long line that needs wrapping
        long_line = "x" * 100  # 100 chars, exceeds MAX_WIDTH=50
        hunk = DiffHunk(
            old_start=1,
            old_count=1,
            new_start=1,
            new_count=1,
            lines=[f"+{long_line}"]
        )
        file_diff = FileDiff(
            old_path="test.py",
            new_path="test.py",
            hunks=[hunk]
        )

        result = renderer.render([file_diff])

        # Verify line wrapping occurred (continuation marker should appear)
        assert "↪" in result

    def test_render_integrates_syntax_highlighter(self, renderer):
        """Test that render() integrates SyntaxHighlighter for colored code."""
        # Create diff with Python code that should be highlighted
        hunk = DiffHunk(
            old_start=1,
            old_count=1,
            new_start=1,
            new_count=1,
            lines=["+def hello():"]
        )
        file_diff = FileDiff(
            old_path="test.py",
            new_path="test.py",
            hunks=[hunk]
        )

        result = renderer.render([file_diff], language="python")

        # Verify ANSI color codes present (syntax highlighting)
        assert "\x1b[" in result  # ANSI escape sequence

    def test_render_shows_context_lines(self, renderer):
        """Test that render() shows context lines (unchanged code)."""
        hunk = DiffHunk(
            old_start=1,
            old_count=3,
            new_start=1,
            new_count=3,
            lines=[
                " context before",
                "+added line",
                " context after"
            ]
        )
        file_diff = FileDiff(
            old_path="test.py",
            new_path="test.py",
            hunks=[hunk]
        )

        result = renderer.render([file_diff])

        # Verify context lines shown with context marker
        assert "≈ context before" in result
        assert "≈ context after" in result
        assert "➕" in result  # Added line also present

    def test_render_handles_multi_hunk_diffs(self, renderer):
        """Test that render() handles multiple hunks in same file."""
        hunk1 = DiffHunk(
            old_start=1,
            old_count=1,
            new_start=1,
            new_count=1,
            lines=["+first change"]
        )
        hunk2 = DiffHunk(
            old_start=10,
            old_count=1,
            new_start=10,
            new_count=1,
            lines=["+second change"]
        )
        file_diff = FileDiff(
            old_path="test.py",
            new_path="test.py",
            hunks=[hunk1, hunk2]
        )

        result = renderer.render([file_diff])

        # Verify both hunks rendered
        assert result.count("➕") == 2
        assert "first change" in result
        assert "second change" in result

    def test_render_handles_multi_file_diffs(self, renderer):
        """Test that render() handles multiple files with separate sections."""
        file1 = FileDiff(
            old_path="file1.py",
            new_path="file1.py",
            hunks=[DiffHunk(1, 1, 1, 1, ["+change in file1"])]
        )
        file2 = FileDiff(
            old_path="file2.py",
            new_path="file2.py",
            hunks=[DiffHunk(1, 1, 1, 1, ["+change in file2"])]
        )

        result = renderer.render([file1, file2])

        # Verify both files rendered with file headers
        assert "📄 file1.py" in result
        assert "📄 file2.py" in result
        assert "change in file1" in result
        assert "change in file2" in result

    def test_render_collapses_large_context(self, renderer):
        """Test that render() collapses large unchanged sections."""
        # Create hunk with 20 context lines (should collapse middle)
        context_lines = [f" context line {i}" for i in range(20)]
        hunk = DiffHunk(
            old_start=1,
            old_count=21,
            new_start=1,
            new_count=21,
            lines=context_lines[:10] + ["+added line"] + context_lines[10:]
        )
        file_diff = FileDiff(
            old_path="test.py",
            new_path="test.py",
            hunks=[hunk]
        )

        result = renderer.render([file_diff])

        # Verify collapse marker present
        assert "..." in result
        assert "lines unchanged" in result

        # Verify first 3 context lines shown
        assert "≈ context line 0" in result
        assert "≈ context line 1" in result
        assert "≈ context line 2" in result

    def test_render_handles_edge_cases(self, renderer):
        """Test that render() handles edge cases gracefully."""
        # Empty diff list
        assert renderer.render([]) == "No changes to display"

        # Binary file
        binary_file = FileDiff(
            old_path="image.png",
            new_path="image.png",
            hunks=[],
            is_binary=True
        )
        result = renderer.render([binary_file])
        assert "binary file" in result.lower()
        assert "image.png" in result

        # No context (only added/removed lines)
        hunk = DiffHunk(
            old_start=1,
            old_count=1,
            new_start=1,
            new_count=1,
            lines=["-old", "+new"]
        )
        file_diff = FileDiff(
            old_path="test.py",
            new_path="test.py",
            hunks=[hunk]
        )
        result = renderer.render([file_diff])
        assert "➖" in result
        assert "➕" in result

    def test_render_real_diff(self, renderer, capsys):
        """Test render with realistic diff for manual visual verification.

        This test outputs formatted diff to console for human verification
        of visual appearance on mobile screens.
        """
        # Create realistic Python diff
        hunk = DiffHunk(
            old_start=10,
            old_count=8,
            new_start=10,
            new_count=10,
            lines=[
                " def calculate_total(items):",
                "     total = 0",
                "     for item in items:",
                "-        total += item.price",
                "+        # Apply discount before adding to total",
                "+        discount = item.price * 0.1",
                "+        total += item.price - discount",
                "     return total",
                " ",
                " def format_currency(amount):"
            ]
        )
        file_diff = FileDiff(
            old_path="src/pricing.py",
            new_path="src/pricing.py",
            hunks=[hunk]
        )

        result = renderer.render([file_diff], language="python")

        # Print for manual verification
        print("\n" + "="*50)
        print("SAMPLE DIFF OUTPUT FOR VISUAL VERIFICATION")
        print("="*50)
        print(result)
        print("="*50)

        # Automated checks
        assert "➕" in result
        assert "➖" in result
        assert "≈" in result
        assert "src/pricing.py" in result
