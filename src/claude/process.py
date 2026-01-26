"""
Claude Code subprocess management for session isolation.

Each session spawns an isolated Claude Code subprocess with:
- Dedicated working directory
- Captured stdout/stderr
- Graceful shutdown (SIGTERM → SIGKILL)
"""

import asyncio
import structlog
from typing import Optional

logger = structlog.get_logger(__name__)


class ClaudeProcess:
    """
    Manages a Claude Code subprocess for a single session.

    Provides:
    - Process isolation per session
    - Working directory isolation
    - Graceful shutdown with timeout
    - Process status monitoring
    """

    def __init__(self, session_id: str, project_path: str):
        """
        Initialize Claude Code process manager.

        Args:
            session_id: Unique session identifier
            project_path: Absolute path to project directory (becomes cwd)
        """
        self.session_id = session_id
        self.project_path = project_path
        self._process: Optional[asyncio.subprocess.Process] = None
        self._log = logger.bind(session_id=session_id, project_path=project_path)

    async def start(self) -> None:
        """
        Spawn Claude Code subprocess.

        Uses asyncio.create_subprocess_exec for safe subprocess spawning:
        - Command and args are separate (no shell injection)
        - cwd parameter isolates working directory
        - stdout/stderr captured for debugging

        Raises:
            RuntimeError: If process already running
            FileNotFoundError: If claude-code not in PATH
        """
        if self._process is not None and self.is_running:
            raise RuntimeError(f"Process already running for session {self.session_id}")

        self._log.info("starting_claude_process")

        # Use create_subprocess_exec (NOT shell=True) to prevent injection
        # Command: "claude-code" (hardcoded)
        # Args: ["--no-browser"] (hardcoded flags)
        # cwd: project_path (user input, but as parameter not in command string)
        self._process = await asyncio.create_subprocess_exec(
            "claude-code",
            "--no-browser",
            cwd=self.project_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        self._log.info("claude_process_started", pid=self._process.pid)

    async def stop(self, timeout: float = 5.0) -> None:
        """
        Gracefully terminate Claude Code subprocess.

        Shutdown sequence:
        1. Send SIGTERM (graceful shutdown)
        2. Wait up to `timeout` seconds
        3. Send SIGKILL if still running (force kill)

        Args:
            timeout: Seconds to wait before forcing kill
        """
        if self._process is None:
            self._log.warning("stop_called_but_no_process")
            return

        if not self.is_running:
            self._log.info("process_already_stopped")
            return

        self._log.info("stopping_claude_process", pid=self._process.pid, timeout=timeout)

        # Step 1: Send SIGTERM (graceful)
        self._process.terminate()

        try:
            # Step 2: Wait for graceful shutdown
            await asyncio.wait_for(self._process.wait(), timeout=timeout)
            self._log.info("claude_process_terminated_gracefully", pid=self._process.pid)
        except asyncio.TimeoutError:
            # Step 3: Force kill if timeout
            self._log.warning("claude_process_timeout_killing", pid=self._process.pid)
            self._process.kill()
            await self._process.wait()
            self._log.info("claude_process_killed", pid=self._process.pid)

    @property
    def is_running(self) -> bool:
        """
        Check if subprocess is currently running.

        Returns:
            True if process exists and hasn't exited
        """
        if self._process is None:
            return False

        return self._process.returncode is None
