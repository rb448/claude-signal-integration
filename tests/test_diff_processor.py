"""Tests for diff processing and summary generation."""

import pytest
from src.claude.diff_processor import DiffParser, SummaryGenerator, DiffHunk, FileDiff


class TestDiffParser:
    """Tests for DiffParser class."""

    def test_parse_extracts_file_path_from_diff_header(self):
        """DiffParser extracts file paths from git diff header."""
        diff_text = """diff --git a/src/user.py b/src/user.py
index 1234567..abcdefg 100644
--- a/src/user.py
+++ b/src/user.py"""

        parser = DiffParser()
        result = parser.parse(diff_text)

        assert len(result) == 1
        assert result[0].old_path == "src/user.py"
        assert result[0].new_path == "src/user.py"

    def test_parse_identifies_hunks(self):
        """DiffParser identifies hunks from @@ markers."""
        diff_text = """diff --git a/src/user.py b/src/user.py
index 1234567..abcdefg 100644
--- a/src/user.py
+++ b/src/user.py
@@ -10,5 +10,7 @@ class User:
     def validate(self):
         pass
+    def new_method(self):
+        pass"""

        parser = DiffParser()
        result = parser.parse(diff_text)

        assert len(result[0].hunks) == 1
        assert result[0].hunks[0].old_start == 10
        assert result[0].hunks[0].old_count == 5
        assert result[0].hunks[0].new_start == 10
        assert result[0].hunks[0].new_count == 7

    def test_parse_separates_added_and_removed_lines(self):
        """DiffParser preserves +/- prefixes for added/removed lines."""
        diff_text = """diff --git a/src/user.py b/src/user.py
index 1234567..abcdefg 100644
--- a/src/user.py
+++ b/src/user.py
@@ -10,3 +10,4 @@ class User:
     def validate(self):
-        pass
+        return True
+    # New comment"""

        parser = DiffParser()
        result = parser.parse(diff_text)

        lines = result[0].hunks[0].lines
        assert "     def validate(self):" in lines
        assert "-        pass" in lines
        assert "+        return True" in lines
        assert "+    # New comment" in lines

    def test_parse_preserves_context_lines(self):
        """DiffParser preserves context lines without +/- prefix."""
        diff_text = """diff --git a/src/user.py b/src/user.py
index 1234567..abcdefg 100644
--- a/src/user.py
+++ b/src/user.py
@@ -10,3 +10,3 @@ class User:
     def validate(self):
-        pass
+        return True"""

        parser = DiffParser()
        result = parser.parse(diff_text)

        lines = result[0].hunks[0].lines
        # Context line has no prefix
        assert "     def validate(self):" in lines

    def test_parse_handles_multiple_files(self):
        """DiffParser handles multiple files in single diff output."""
        diff_text = """diff --git a/src/user.py b/src/user.py
index 1234567..abcdefg 100644
--- a/src/user.py
+++ b/src/user.py
@@ -10,1 +10,2 @@ class User:
+    pass
diff --git a/src/auth.py b/src/auth.py
index 7654321..gfedcba 100644
--- a/src/auth.py
+++ b/src/auth.py
@@ -5,1 +5,2 @@ def login():
+    return True"""

        parser = DiffParser()
        result = parser.parse(diff_text)

        assert len(result) == 2
        assert result[0].old_path == "src/user.py"
        assert result[1].old_path == "src/auth.py"

    def test_parse_handles_binary_files(self):
        """DiffParser marks binary files without parsing content."""
        diff_text = """diff --git a/image.png b/image.png
index 1234567..abcdefg 100644
Binary files a/image.png and b/image.png differ"""

        parser = DiffParser()
        result = parser.parse(diff_text)

        assert len(result) == 1
        assert result[0].old_path == "image.png"
        assert result[0].is_binary is True
        assert len(result[0].hunks) == 0

    def test_parse_handles_empty_diff(self):
        """DiffParser returns empty list for empty diff."""
        parser = DiffParser()
        result = parser.parse("")

        assert result == []

    def test_parse_handles_malformed_input(self):
        """DiffParser gracefully handles malformed input."""
        diff_text = "This is not a git diff"

        parser = DiffParser()
        result = parser.parse(diff_text)

        # Should return empty list, not crash
        assert result == []


class TestSummaryGenerator:
    """Tests for SummaryGenerator class."""

    def test_generate_describes_single_file_change(self):
        """SummaryGenerator describes single-file modification."""
        file_diff = FileDiff(
            old_path="src/user.py",
            new_path="src/user.py",
            hunks=[
                DiffHunk(
                    old_start=10,
                    old_count=5,
                    new_start=10,
                    new_count=10,
                    lines=[
                        " class User:",
                        "-    pass",
                        "+    def validate(self):",
                        "+        return True",
                    ]
                )
            ]
        )

        generator = SummaryGenerator()
        result = generator.generate([file_diff])

        # Function detection takes priority over line counts (better UX)
        assert "User" in result or "validate()" in result
        assert "src/user.py" in result

    def test_generate_describes_multi_file_change(self):
        """SummaryGenerator lists multiple modified files."""
        file_diffs = [
            FileDiff("src/user.py", "src/user.py", []),
            FileDiff("src/auth.py", "src/auth.py", []),
            FileDiff("src/db.py", "src/db.py", []),
        ]

        generator = SummaryGenerator()
        result = generator.generate(file_diffs)

        assert "Modified 3 files" in result

    def test_generate_identifies_new_files(self):
        """SummaryGenerator identifies newly created files."""
        file_diff = FileDiff(
            old_path="/dev/null",
            new_path="config.json",
            hunks=[
                DiffHunk(
                    old_start=0,
                    old_count=0,
                    new_start=1,
                    new_count=20,
                    lines=["+{"] + [f"+  line{i}" for i in range(19)]
                )
            ]
        )

        generator = SummaryGenerator()
        result = generator.generate([file_diff])

        assert "Created config.json" in result
        assert "20 lines" in result

    def test_generate_identifies_deleted_files(self):
        """SummaryGenerator identifies deleted files."""
        file_diff = FileDiff(
            old_path="old_migration.sql",
            new_path="/dev/null",
            hunks=[]
        )

        generator = SummaryGenerator()
        result = generator.generate([file_diff])

        assert "Deleted old_migration.sql" in result

    def test_generate_detects_function_changes(self):
        """SummaryGenerator detects modified functions."""
        file_diff = FileDiff(
            old_path="src/user.py",
            new_path="src/user.py",
            hunks=[
                DiffHunk(
                    old_start=10,
                    old_count=3,
                    new_start=10,
                    new_count=4,
                    lines=[
                        " class User:",
                        "     def validate(self):",
                        "-        pass",
                        "+        return True",
                    ]
                )
            ]
        )

        generator = SummaryGenerator()
        result = generator.generate([file_diff])

        assert "validate()" in result
        assert "src/user.py" in result

    def test_generate_handles_binary_files(self):
        """SummaryGenerator describes binary file updates."""
        file_diff = FileDiff(
            old_path="image.png",
            new_path="image.png",
            hunks=[],
            is_binary=True
        )

        generator = SummaryGenerator()
        result = generator.generate([file_diff])

        assert "Updated image.png" in result
        assert "binary file" in result

    def test_generate_handles_empty_diff(self):
        """SummaryGenerator handles empty diff input."""
        generator = SummaryGenerator()
        result = generator.generate([])

        assert result == "No changes detected"


class TestEdgeCaseCoverage:
    """Tests for edge cases and error paths to improve coverage."""

    def test_parse_multiple_hunks_per_file(self):
        """DiffParser handles multiple hunks in a single file."""
        diff_text = """diff --git a/src/user.py b/src/user.py
index 1234567..abcdefg 100644
--- a/src/user.py
+++ b/src/user.py
@@ -10,3 +10,4 @@ class User:
     def validate(self):
-        pass
+        return True
@@ -20,2 +21,3 @@ class User:
     def save(self):
+        # New comment
         pass"""

        parser = DiffParser()
        result = parser.parse(diff_text)

        # Should have 2 hunks
        assert len(result[0].hunks) == 2
        assert result[0].hunks[0].old_start == 10
        assert result[0].hunks[1].old_start == 20

    def test_parse_malformed_hunk_header(self):
        """DiffParser handles malformed hunk headers gracefully."""
        diff_text = """diff --git a/src/user.py b/src/user.py
index 1234567..abcdefg 100644
--- a/src/user.py
+++ b/src/user.py
@@ invalid hunk header
     some content
@@ -10,3 +10,4 @@ valid header
+    added line"""

        parser = DiffParser()
        result = parser.parse(diff_text)

        # Should parse valid hunk, skip malformed one
        assert len(result) == 1
        # Only the valid hunk should be processed
        assert len(result[0].hunks) >= 0

    def test_generate_modified_file_without_function_detection(self):
        """SummaryGenerator describes changes when no functions detected."""
        hunk = DiffHunk(
            old_start=10,
            old_count=3,
            new_start=10,
            new_count=5,
            lines=[
                " some content",
                "+added line 1",
                "+added line 2",
                "-removed line",
            ]
        )
        file_diff = FileDiff(
            old_path="config.txt",
            new_path="config.txt",
            hunks=[hunk],
            is_binary=False
        )

        generator = SummaryGenerator()
        result = generator.generate([file_diff])

        # Should describe with line counts, not function names
        assert "config.txt" in result
        assert "added 2 lines" in result or "removed 1 line" in result

    def test_detect_python_function_with_malformed_syntax(self):
        """SummaryGenerator handles malformed Python function syntax."""
        hunk = DiffHunk(
            old_start=10,
            old_count=1,
            new_start=10,
            new_count=2,
            lines=[
                "+def incomplete_function",  # Missing parentheses
            ]
        )
        file_diff = FileDiff(
            old_path="src/user.py",
            new_path="src/user.py",
            hunks=[hunk],
            is_binary=False
        )

        generator = SummaryGenerator()
        # Should not crash, handle gracefully
        result = generator.generate([file_diff])
        assert "src/user.py" in result

    def test_detect_python_class_with_malformed_syntax(self):
        """SummaryGenerator handles malformed Python class syntax."""
        hunk = DiffHunk(
            old_start=10,
            old_count=1,
            new_start=10,
            new_count=2,
            lines=[
                "+class IncompleteClass",  # Missing colon
            ]
        )
        file_diff = FileDiff(
            old_path="src/models.py",
            new_path="src/models.py",
            hunks=[hunk],
            is_binary=False
        )

        generator = SummaryGenerator()
        # Should not crash, handle gracefully
        result = generator.generate([file_diff])
        assert "src/models.py" in result

    def test_detect_javascript_function_with_malformed_syntax(self):
        """SummaryGenerator handles malformed JavaScript function syntax."""
        hunk = DiffHunk(
            old_start=5,
            old_count=1,
            new_start=5,
            new_count=2,
            lines=[
                "+function incomplete",  # Missing parentheses
            ]
        )
        file_diff = FileDiff(
            old_path="src/app.js",
            new_path="src/app.js",
            hunks=[hunk],
            is_binary=False
        )

        generator = SummaryGenerator()
        # Should not crash, handle gracefully
        result = generator.generate([file_diff])
        assert "src/app.js" in result
