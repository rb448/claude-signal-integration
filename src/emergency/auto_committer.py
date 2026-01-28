"""Auto-commit formatter for emergency mode changes."""
import asyncio
import structlog
from pathlib import Path

from src.emergency.mode import EmergencyMode

logger = structlog.get_logger()


class EmergencyAutoCommitter:
    """
    Auto-commit formatter for emergency mode.

    Generates commit messages with [EMERGENCY] prefix and auto-commits
    successful changes in emergency mode.
    """

    def format_commit_message(
        self, session_id: str, operation: str, files: list[str]
    ) -> str:
        """
        Format commit message for emergency mode change.

        Args:
            session_id: Session that made the change
            operation: Operation type (Edit, Write, etc.)
            files: List of modified files

        Returns:
            Formatted commit message with [EMERGENCY] prefix
        """
        # Truncate session ID to 8 chars (Phase 2 pattern)
        session_short = session_id[:8]

        # Format file list
        if len(files) == 1:
            file_str = files[0]
        elif len(files) <= 3:
            file_str = ", ".join(files)
        else:
            file_str = f"{', '.join(files[:3])} and {len(files) - 3} more"

        return f"[EMERGENCY] {operation}: {file_str} (session: {session_short})"

    async def auto_commit(
        self,
        emergency_mode: EmergencyMode,
        session_id: str,
        project_path: str,
        operation: str,
        files: list[str],
    ) -> None:
        """
        Auto-commit changes if in emergency mode.

        Args:
            emergency_mode: Emergency mode instance to check status
            session_id: Session that made the change
            project_path: Project directory path
            operation: Operation type (Edit, Write, etc.)
            files: List of modified files
        """
        # Only commit in emergency mode
        if not await emergency_mode.is_active():
            logger.debug(
                "auto_commit_skipped",
                reason="not in emergency mode",
                session_id=session_id[:8],
            )
            return

        # Generate commit message
        message = self.format_commit_message(session_id, operation, files)

        try:
            # Stage files
            git_add_cmd = ["git", "add"] + files
            add_process = await asyncio.create_subprocess_exec(
                *git_add_cmd,
                cwd=project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await add_process.communicate()

            if add_process.returncode != 0:
                logger.warning(
                    "git_add_failed",
                    session_id=session_id[:8],
                    returncode=add_process.returncode,
                )
                return

            # Commit changes
            git_commit_cmd = ["git", "commit", "-m", message]
            commit_process = await asyncio.create_subprocess_exec(
                *git_commit_cmd,
                cwd=project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await commit_process.communicate()

            if commit_process.returncode == 0:
                logger.info(
                    "auto_commit_success",
                    session_id=session_id[:8],
                    operation=operation,
                    files_count=len(files),
                )
            else:
                logger.warning(
                    "git_commit_failed",
                    session_id=session_id[:8],
                    returncode=commit_process.returncode,
                    stderr=stderr.decode() if stderr else "",
                )

        except Exception as e:
            logger.error(
                "auto_commit_error",
                session_id=session_id[:8],
                error=str(e),
            )
