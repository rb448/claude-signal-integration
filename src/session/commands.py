"""
Session command handlers for Signal bot.

GREEN Phase: Implement SessionCommands to make tests pass.
"""

from pathlib import Path
from typing import Callable
from src.session import SessionManager, SessionLifecycle, SessionStatus
from src.claude import ClaudeProcess


class SessionCommands:
    """
    Handles /session commands from Signal messages.

    Parses and routes session management commands (start, list, resume, stop).
    """

    def __init__(
        self,
        session_manager: SessionManager,
        session_lifecycle: SessionLifecycle,
        claude_process_factory: Callable[[str, str], ClaudeProcess],
    ):
        """
        Initialize SessionCommands.

        Args:
            session_manager: SessionManager for CRUD operations
            session_lifecycle: SessionLifecycle for state transitions
            claude_process_factory: Factory function to create ClaudeProcess instances
        """
        self.manager = session_manager
        self.lifecycle = session_lifecycle
        self.process_factory = claude_process_factory
        self.processes: dict[str, ClaudeProcess] = {}  # session_id -> process

    async def handle(self, thread_id: str, message: str) -> str:
        """
        Handle /session command.

        Args:
            thread_id: Signal thread ID for this command
            message: Full message text starting with /session

        Returns:
            Response message to send back to user
        """
        # Parse: /session <subcommand> [args]
        parts = message.strip().split()
        if len(parts) < 2:
            return self._help()

        subcommand = parts[1]

        if subcommand == "start":
            project_path = parts[2] if len(parts) > 2 else None
            return await self._start(thread_id, project_path)
        elif subcommand == "list":
            return await self._list()
        elif subcommand == "resume":
            session_id = parts[2] if len(parts) > 2 else None
            return await self._resume(session_id)
        elif subcommand == "stop":
            session_id = parts[2] if len(parts) > 2 else None
            return await self._stop(session_id)
        else:
            return self._help()

    async def _start(self, thread_id: str, project_path: str | None) -> str:
        """
        Start new session.

        Args:
            thread_id: Signal thread ID
            project_path: Path to project directory

        Returns:
            Success or error message
        """
        if project_path is None:
            return "Error: Missing project path\n\nUsage: /session start <project_path>"

        # Validate project path exists
        path = Path(project_path)
        if not path.exists():
            return f"Error: Project path does not exist: {project_path}"

        # Create session
        session = await self.manager.create(project_path, thread_id)

        # Transition CREATED -> ACTIVE
        session = await self.lifecycle.transition(session.id, SessionStatus.ACTIVE)

        # Spawn Claude process
        process = self.process_factory(session.id, project_path)
        await process.start()
        self.processes[session.id] = process

        return f"Started session {session.id} for {project_path}"

    async def _list(self) -> str:
        """
        List all sessions.

        Returns:
            Formatted table of sessions
        """
        sessions = await self.manager.list()

        if not sessions:
            return "No sessions found."

        # Format as table
        lines = ["Sessions:", ""]
        lines.append("ID | Status | Project")
        lines.append("-" * 60)

        for session in sessions:
            # Truncate session ID for display
            short_id = session.id[:8]
            # Truncate project path for display
            project = session.project_path
            if len(project) > 30:
                project = "..." + project[-27:]

            lines.append(f"{short_id} | {session.status.value:10} | {project}")

        return "\n".join(lines)

    async def _resume(self, session_id: str | None) -> str:
        """
        Resume paused session.

        Args:
            session_id: Session UUID to resume

        Returns:
            Success or error message
        """
        if session_id is None:
            return "Error: Missing session ID\n\nUsage: /session resume <session_id>"

        # Get session
        session = await self.manager.get(session_id)
        if session is None:
            return f"Error: Session not found: {session_id}"

        # Transition PAUSED -> ACTIVE
        session = await self.lifecycle.transition(session_id, SessionStatus.ACTIVE)

        # Spawn Claude process if not already running
        if session_id not in self.processes:
            process = self.process_factory(session_id, session.project_path)
            await process.start()
            self.processes[session_id] = process

        return f"Resumed session {session_id}"

    async def _stop(self, session_id: str | None) -> str:
        """
        Stop active session.

        Args:
            session_id: Session UUID to stop

        Returns:
            Success or error message
        """
        if session_id is None:
            return "Error: Missing session ID\n\nUsage: /session stop <session_id>"

        # Get session
        session = await self.manager.get(session_id)
        if session is None:
            return f"Error: Session not found: {session_id}"

        # Stop Claude process if running
        if session_id in self.processes:
            process = self.processes[session_id]
            await process.stop()
            del self.processes[session_id]

        # Transition ACTIVE -> TERMINATED
        await self.lifecycle.transition(session_id, SessionStatus.TERMINATED)

        return f"Stopped session {session_id}"

    def _help(self) -> str:
        """
        Return help message.

        Returns:
            Help text with available commands
        """
        return """Available commands:

/session start <project_path> - Start new session
/session list - List all sessions
/session resume <session_id> - Resume paused session
/session stop <session_id> - Stop active session
"""
