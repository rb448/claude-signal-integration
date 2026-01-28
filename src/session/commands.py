"""
Session command handlers for Signal bot.

GREEN Phase: Implement SessionCommands to make tests pass.
"""

from pathlib import Path
from typing import Callable, Optional
from src.session import SessionManager, SessionLifecycle, SessionStatus
from src.claude import ClaudeProcess
from src.claude.orchestrator import ClaudeOrchestrator
from src.thread import ThreadCommands, ThreadMapper
from src.approval.commands import ApprovalCommands
from src.notification.commands import NotificationCommands
from src.custom_commands.commands import CustomCommands
from src.emergency.commands import EmergencyCommands


class SessionCommands:
    """
    Handles /session commands and Claude commands from Signal messages.

    Parses and routes:
    - Session management commands (start, list, resume, stop)
    - Claude commands (non-/session messages to active sessions)
    """

    def __init__(
        self,
        session_manager: SessionManager,
        session_lifecycle: SessionLifecycle,
        claude_process_factory: Callable[[str, str], ClaudeProcess],
        claude_orchestrator: Optional[ClaudeOrchestrator] = None,
        thread_commands: Optional[ThreadCommands] = None,
        thread_mapper: Optional[ThreadMapper] = None,
        approval_commands: Optional[ApprovalCommands] = None,
        notification_commands: Optional[NotificationCommands] = None,
        custom_commands: Optional[CustomCommands] = None,
        emergency_commands: Optional[EmergencyCommands] = None,
    ):
        """
        Initialize SessionCommands.

        Args:
            session_manager: SessionManager for CRUD operations
            session_lifecycle: SessionLifecycle for state transitions
            claude_process_factory: Factory function to create ClaudeProcess instances
            claude_orchestrator: ClaudeOrchestrator for routing Claude commands
            thread_commands: ThreadCommands for thread mapping operations
            thread_mapper: ThreadMapper for thread-to-project mapping lookups
            approval_commands: ApprovalCommands for approval/rejection operations
            notification_commands: NotificationCommands for notification preference operations
            custom_commands: CustomCommands for custom command operations
            emergency_commands: EmergencyCommands for emergency mode operations
        """
        self.manager = session_manager
        self.lifecycle = session_lifecycle
        self.process_factory = claude_process_factory
        self.orchestrator = claude_orchestrator
        self.thread_commands = thread_commands
        self.thread_mapper = thread_mapper
        self.approval_commands = approval_commands
        self.notification_commands = notification_commands
        self.custom_commands = custom_commands
        self.emergency_commands = emergency_commands
        self.processes: dict[str, ClaudeProcess] = {}  # session_id -> process
        self.thread_sessions: dict[str, str] = {}  # thread_id -> session_id (active sessions)

    async def handle(self, thread_id: str, message: str) -> str:
        """
        Handle /session command, /thread command, /code command, approval command, notification command, or Claude command.

        Args:
            thread_id: Signal thread ID for this command
            message: Full message text

        Returns:
            Response message to send back to user (None for Claude commands)
        """
        # Route to appropriate handler in priority order:
        # 1. Approval commands (most urgent - time-sensitive operations)
        if self.approval_commands:
            result = await self.approval_commands.handle(message)
            if result is not None:
                return result

        # 2. Emergency commands (urgent mode operations)
        if message.strip().startswith("/emergency"):
            if self.emergency_commands:
                return await self.emergency_commands.handle(thread_id, message)
            else:
                return "Emergency mode not available."

        # 3. Notification commands (user configuration)
        if self.notification_commands:
            result = await self.notification_commands.handle(message, thread_id)
            if result is not None:
                return result

        # 4. Custom commands (feature-specific operations)
        if message.strip().startswith("/custom"):
            if self.custom_commands:
                return await self.custom_commands.handle(thread_id, message)
            else:
                return "Custom commands not available."

        # 5. Thread commands (project management)
        if message.strip().startswith("/thread"):
            if self.thread_commands:
                return await self.thread_commands.handle(thread_id, message)
            else:
                return "Thread management not available."

        # 6. Code display commands
        if message.strip().startswith("/code"):
            return await self._handle_code_command(message, thread_id)

        # 7. Session commands (session lifecycle)
        if message.strip().startswith("/session"):
            return await self._handle_session_command(thread_id, message)

        # 8. Claude commands (everything else)
        return await self._handle_claude_command(thread_id, message)

    async def _handle_session_command(self, thread_id: str, message: str) -> str:
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
            return await self._resume(thread_id, session_id)
        elif subcommand == "stop":
            session_id = parts[2] if len(parts) > 2 else None
            return await self._stop(thread_id, session_id)
        else:
            return self._help()

    async def _handle_code_command(self, message: str, recipient: str) -> str:
        """
        Handle /code command for code display control.

        Args:
            message: Full message text starting with /code
            recipient: Signal thread ID (for future session context lookup)

        Returns:
            Response message to send back to user
        """
        parts = message.split(maxsplit=1)
        subcommand = parts[1] if len(parts) > 1 else ""

        if subcommand == "full":
            return await self._code_full(recipient)
        elif subcommand == "help" or subcommand == "":
            return self._code_help()
        else:
            return f"Unknown subcommand: /code {subcommand}\n\nUse /code help for usage."

    async def _code_full(self, recipient: str) -> str:
        """
        Display last code output without truncation.

        Args:
            recipient: Signal thread ID

        Returns:
            Full code view or placeholder message
        """
        # TODO: Store last code output in session context
        # Full implementation requires ClaudeOrchestrator changes
        # Deferred to Phase 7 (Connection Resilience) which includes session state sync
        return "Full code view not yet implemented - coming in next iteration"

    def _code_help(self) -> str:
        """
        Show /code command help.

        Returns:
            Help text for code display commands
        """
        return """**Code Display Commands**

/code full - Show full code view (no truncation)
  • Diffs: All context shown (no collapse)
  • Long files: Sent as attachment
  • Recent: Last code from Claude

/code help - Show this help

**Automatic Display:**
• Code <20 lines: Inline with formatting
• Code 20-100 lines: Inline (use /code full for details)
• Code >100 lines: Attachment
• Diffs: Summary + rendered changes
"""

    async def _handle_claude_command(self, thread_id: str, message: str) -> str:
        """
        Handle Claude command (non-/session message).

        Args:
            thread_id: Signal thread ID for this command
            message: Command message for Claude

        Returns:
            Response message (error if no active session, confirmation otherwise)
        """
        # Get active session for this thread
        session_id = self.thread_sessions.get(thread_id)
        if session_id is None:
            return "No active session. Start one with: /session start <project_path>"

        # Route to orchestrator
        if self.orchestrator is None:
            return "Error: Claude orchestrator not initialized"

        # Execute command via orchestrator (async, responses streamed back via orchestrator)
        await self.orchestrator.execute_command(message, session_id)

        # Return None to indicate orchestrator is handling responses
        return None

    async def _start(self, thread_id: str, project_path: str | None) -> str:
        """
        Start new session.

        Args:
            thread_id: Signal thread ID
            project_path: Path to project directory (optional if thread is mapped)

        Returns:
            Success or error message
        """
        # Try to get thread mapping first
        resolved_path: str | None = None

        if self.thread_mapper:
            mapping = await self.thread_mapper.get_by_thread(thread_id)
            if mapping:
                resolved_path = mapping.project_path
                # Ignore user-provided path if thread is mapped
            elif not project_path:
                # No mapping, no path provided
                return (
                    "Error: Thread not mapped to a project.\n"
                    "Use '/thread map <path>' or '/session start <path>'"
                )

        # Fall back to explicit path if no mapping
        if not resolved_path:
            resolved_path = project_path

        if not resolved_path:
            return "Error: Missing project path\n\nUsage: /session start <project_path>"

        # Validate project path exists
        path = Path(resolved_path)
        if not path.exists():
            return f"Error: Project path does not exist: {resolved_path}"

        # Create session
        session = await self.manager.create(resolved_path, thread_id)

        # Transition CREATED -> ACTIVE
        session = await self.lifecycle.transition(
            session.id, SessionStatus.CREATED, SessionStatus.ACTIVE
        )

        # Spawn Claude process
        process = self.process_factory(session.id, resolved_path)
        await process.start()
        self.processes[session.id] = process

        # Wire orchestrator bridge so commands can execute
        if self.orchestrator:
            self.orchestrator.bridge = process.get_bridge()

        # Map thread to session
        self.thread_sessions[thread_id] = session.id

        return f"Started session {session.id[:8]} for {resolved_path}"

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

    async def _resume(self, thread_id: str, session_id: str | None) -> str:
        """
        Resume paused session.

        Args:
            thread_id: Signal thread ID
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
        session = await self.lifecycle.transition(
            session_id, SessionStatus.PAUSED, SessionStatus.ACTIVE
        )

        # Spawn Claude process if not already running
        if session_id not in self.processes:
            # Extract conversation history from session context
            # conversation_history extracted from session.context (populated by SessionManager)
            # Phase 3 will implement actual restoration to Claude Code CLI
            conversation_history = session.context.get("conversation_history", {})

            process = self.process_factory(session_id, session.project_path)
            await process.start(conversation_history=conversation_history)
            self.processes[session_id] = process

            # Wire orchestrator bridge so commands can execute
            if self.orchestrator:
                self.orchestrator.bridge = process.get_bridge()

        # Map thread to session
        self.thread_sessions[thread_id] = session_id

        return f"Resumed session {session_id[:8]}"

    async def _stop(self, thread_id: str, session_id: str | None) -> str:
        """
        Stop active session.

        Args:
            thread_id: Signal thread ID
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

        # Remove thread mapping if exists
        if thread_id in self.thread_sessions and self.thread_sessions[thread_id] == session_id:
            del self.thread_sessions[thread_id]

        # Transition ACTIVE -> TERMINATED
        await self.lifecycle.transition(
            session_id, SessionStatus.ACTIVE, SessionStatus.TERMINATED
        )

        return f"Stopped session {session_id[:8]}"

    def _help(self) -> str:
        """
        Return help message.

        Returns:
            Help text with available commands
        """
        help_text = "Available commands:\n\n"

        # Add approval commands if available
        if self.approval_commands:
            help_text += self.approval_commands.help() + "\n\n"

        # Add emergency commands reference
        if self.emergency_commands:
            help_text += "Emergency Mode:\n"
            help_text += "  /emergency help - Show emergency mode commands\n\n"

        # Add notification commands if available
        if self.notification_commands:
            help_text += self.notification_commands.help() + "\n\n"

        # Add custom commands reference
        if self.custom_commands:
            help_text += "Custom Commands:\n"
            help_text += "  /custom help - Show custom command operations\n\n"

        # Add thread commands reference (they have /thread help)
        if self.thread_commands:
            help_text += "Thread Commands:\n"
            help_text += "  /thread help - Show thread mapping commands\n\n"

        # Add code display commands
        help_text += """Code Display Commands:
  /code help - Show code display commands
  /code full - Show full code view

"""

        # Add session commands
        help_text += """Session Commands:
  /session start <project_path> - Start new session
  /session list - List all sessions
  /session resume <session_id> - Resume paused session
  /session stop <session_id> - Stop active session
"""

        return help_text
