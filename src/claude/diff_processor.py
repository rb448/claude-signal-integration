"""Git diff parsing and summary generation for mobile code display."""

from dataclasses import dataclass
from typing import List


@dataclass
class DiffHunk:
    """A hunk within a file diff (@@...@@ section)."""

    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: List[str]  # Lines with +/- prefix preserved


@dataclass
class FileDiff:
    """Diff for a single file."""

    old_path: str
    new_path: str
    hunks: List[DiffHunk]
    is_binary: bool = False


class DiffParser:
    """Parse git diff output into structured representation."""

    def parse(self, diff_text: str) -> List[FileDiff]:
        """Parse git diff text into FileDiff objects.

        Args:
            diff_text: Output from git diff command

        Returns:
            List of FileDiff objects, one per file
        """
        if not diff_text:
            return []

        files = []
        current_file = None
        current_hunk = None

        for line in diff_text.split('\n'):
            # File headers: diff --git a/file b/file
            if line.startswith('diff --git'):
                if current_file:
                    # Save previous file before starting new one
                    if current_hunk:
                        current_file.hunks.append(current_hunk)
                        current_hunk = None
                    files.append(current_file)

                # Extract paths from diff --git a/old b/new
                parts = line.split()
                if len(parts) >= 4:
                    old_path = parts[2][2:] if parts[2].startswith('a/') else parts[2]
                    new_path = parts[3][2:] if parts[3].startswith('b/') else parts[3]
                    current_file = FileDiff(old_path, new_path, [])
                    current_hunk = None

            # Binary file marker
            elif line.startswith('Binary files'):
                if current_file:
                    current_file.is_binary = True

            # Hunk header: @@ -old_start,old_count +new_start,new_count @@
            elif line.startswith('@@'):
                if current_hunk and current_file:
                    current_file.hunks.append(current_hunk)

                # Parse @@ -10,5 +10,7 @@ optional context
                try:
                    parts = line.split('@@')
                    if len(parts) >= 2:
                        ranges = parts[1].strip().split()
                        if len(ranges) >= 2:
                            # Parse old range: -10,5 or -10
                            old = ranges[0][1:].split(',')  # Remove - prefix
                            old_start = int(old[0])
                            old_count = int(old[1]) if len(old) > 1 else 1

                            # Parse new range: +10,7 or +10
                            new = ranges[1][1:].split(',')  # Remove + prefix
                            new_start = int(new[0])
                            new_count = int(new[1]) if len(new) > 1 else 1

                            current_hunk = DiffHunk(
                                old_start=old_start,
                                old_count=old_count,
                                new_start=new_start,
                                new_count=new_count,
                                lines=[]
                            )
                except (ValueError, IndexError):
                    # Malformed hunk header, skip
                    current_hunk = None

            # Hunk content lines (added, removed, context)
            elif current_hunk and (
                line.startswith('+') or
                line.startswith('-') or
                line.startswith(' ')
            ):
                # Skip file metadata lines (---, +++)
                if not line.startswith('---') and not line.startswith('+++'):
                    current_hunk.lines.append(line)

        # Append final hunk/file
        if current_hunk and current_file:
            current_file.hunks.append(current_hunk)
        if current_file:
            files.append(current_file)

        return files


class SummaryGenerator:
    """Generate plain-English summaries of code changes."""

    def generate(self, file_diffs: List[FileDiff]) -> str:
        """Create readable summary from parsed diff.

        Args:
            file_diffs: List of FileDiff objects from DiffParser

        Returns:
            Plain-English description of changes
        """
        if not file_diffs:
            return "No changes detected"

        summaries = []

        for file_diff in file_diffs:
            if file_diff.is_binary:
                summaries.append(f"Updated {file_diff.new_path} (binary file)")
                continue

            # Detect new files (old_path is /dev/null)
            if file_diff.old_path == "/dev/null":
                lines = self._count_added_lines(file_diff)
                summaries.append(f"Created {file_diff.new_path}: {lines} lines")
                continue

            # Detect deleted files (new_path is /dev/null)
            if file_diff.new_path == "/dev/null":
                summaries.append(f"Deleted {file_diff.old_path}")
                continue

            # Modified file - count changes
            added, removed = self._count_changes(file_diff)
            changes = []
            if added:
                changes.append(f"added {added} lines")
            if removed:
                changes.append(f"removed {removed} lines")

            # Try to detect function/class changes
            modified_items = self._detect_modified_items(file_diff)
            if modified_items:
                summaries.append(
                    f"Modified {', '.join(modified_items)} in {file_diff.new_path}"
                )
            elif changes:
                summaries.append(
                    f"Modified {file_diff.new_path}: {', '.join(changes)}"
                )
            else:
                # No detectable changes (shouldn't happen, but handle gracefully)
                summaries.append(f"Modified {file_diff.new_path}")

        # Format final summary
        if len(summaries) == 1:
            return summaries[0]
        else:
            return f"Modified {len(summaries)} files:\n" + "\n".join(f"  • {s}" for s in summaries)

    def _count_changes(self, file_diff: FileDiff) -> tuple[int, int]:
        """Count added and removed lines.

        Returns:
            Tuple of (added_count, removed_count)
        """
        added = removed = 0
        for hunk in file_diff.hunks:
            for line in hunk.lines:
                if line.startswith('+') and not line.startswith('+++'):
                    added += 1
                elif line.startswith('-') and not line.startswith('---'):
                    removed += 1
        return added, removed

    def _count_added_lines(self, file_diff: FileDiff) -> int:
        """Count total lines in new file."""
        total = 0
        for hunk in file_diff.hunks:
            for line in hunk.lines:
                if line.startswith('+'):
                    total += 1
        return total

    def _detect_modified_items(self, file_diff: FileDiff) -> List[str]:
        """Detect modified functions/classes from diff context.

        Returns:
            List of function/class names found in diff
        """
        items = set()
        for hunk in file_diff.hunks:
            for line in hunk.lines:
                # Detect Python functions: def function_name(
                if 'def ' in line:
                    try:
                        parts = line.split('def ')[1].split('(')[0].strip()
                        if parts:
                            items.add(f"{parts}()")
                    except IndexError:
                        pass

                # Detect Python classes: class ClassName:
                elif 'class ' in line:
                    try:
                        parts = line.split('class ')[1].split(':')[0].split('(')[0].strip()
                        if parts:
                            items.add(parts)
                    except IndexError:
                        pass

                # Detect JS/TS functions: function name() or name = () =>
                elif 'function ' in line:
                    try:
                        parts = line.split('function ')[1].split('(')[0].strip()
                        if parts:
                            items.add(f"{parts}()")
                    except IndexError:
                        pass

        return list(items)
