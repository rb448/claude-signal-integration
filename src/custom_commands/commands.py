"""Custom command handlers for Signal bot.

GREEN Phase: Implement CustomCommands to make tests pass.
"""

from typing import Optional, TYPE_CHECKING
from src.custom_commands.registry import CustomCommandRegistry

if TYPE_CHECKING:
    from src.claude.orchestrator import ClaudeOrchestrator


class CustomCommands:
    """
    Handles /custom commands for managing and invoking custom Claude Code commands.

    Parses and routes:
    - /custom list - List available custom commands
    - /custom show <name> - Show command details
    - /custom invoke <name> <args> - Execute custom command
    - /custom help - Show command documentation
    """

    def __init__(self, registry: CustomCommandRegistry, orchestrator: Optional["ClaudeOrchestrator"] = None):
        """
        Initialize CustomCommands.

        Args:
            registry: CustomCommandRegistry instance for command storage
            orchestrator: ClaudeOrchestrator for command execution (optional for testing)
        """
        self.registry = registry
        self.orchestrator = orchestrator
        self._active_sessions: dict[str, str] = {}  # thread_id -> session_id

    def set_active_session(self, thread_id: str, session_id: str):
        """
        Set active session for a thread.

        Args:
            thread_id: Signal thread ID
            session_id: Active Claude session ID
        """
        self._active_sessions[thread_id] = session_id

    def clear_active_session(self, thread_id: str):
        """
        Clear active session for a thread.

        Args:
            thread_id: Signal thread ID
        """
        self._active_sessions.pop(thread_id, None)

    async def handle(self, thread_id: str, message: str) -> str:
        """
        Handle /custom command.

        Args:
            thread_id: Signal thread ID for this command
            message: Full message text starting with /custom

        Returns:
            Response message to send back to user
        """
        # Parse: /custom <subcommand> [args]
        parts = message.strip().split(maxsplit=2)
        if len(parts) < 2:
            return self._help()

        subcommand = parts[1]

        if subcommand == "list":
            return await self._list()
        elif subcommand == "show":
            command_name = parts[2] if len(parts) > 2 else None
            return await self._show(command_name)
        elif subcommand == "invoke":
            if len(parts) < 3:
                return "Error: Missing command name\n\nUsage: /custom invoke <command_name> [args]"
            # Split command name and args
            invoke_parts = parts[2].split(maxsplit=1)
            command_name = invoke_parts[0]
            args = invoke_parts[1] if len(invoke_parts) > 1 else ""
            return await self._invoke(thread_id, command_name, args)
        elif subcommand == "help":
            return self._help()
        else:
            return self._help()

    async def _list(self) -> str:
        """
        List all available custom commands.

        Returns:
            Formatted list of commands or "No commands" message
        """
        commands = await self.registry.list_commands()

        if not commands:
            return "No custom commands available."

        # Format as list with emoji and descriptions
        lines = ["📋 Custom Commands:", ""]

        for cmd in commands:
            metadata = cmd["metadata"]
            name = cmd["name"]
            description = metadata.get("description", "No description")

            # Truncate long command names for mobile (30 char limit)
            display_name = name
            if len(name) > 30:
                display_name = name[:27] + "..."

            lines.append(f"📋 {display_name}")
            lines.append(f"   {description}")
            lines.append("")

        return "\n".join(lines)

    async def _show(self, command_name: Optional[str]) -> str:
        """
        Show details for a specific command.

        Args:
            command_name: Name of command to show

        Returns:
            Formatted command details or error message
        """
        if command_name is None:
            return "Error: Missing command name\n\nUsage: /custom show <command_name>"

        # Get command from registry
        command = await self.registry.get_command(command_name)

        if command is None:
            return f"Command '{command_name}' not found.\n\nUse '/custom list' to see available commands."

        # Format command details
        metadata = command["metadata"]
        lines = [f"📄 Command: {command_name}", ""]

        # Description
        description = metadata.get("description", "No description")
        lines.append(f"Description: {description}")
        lines.append("")

        # Parameters
        parameters = metadata.get("parameters", [])
        if parameters:
            lines.append("Parameters:")
            for param in parameters:
                lines.append(f"  - {param}")
            lines.append("")

        # Usage
        usage = metadata.get("usage", f"/{command_name}")
        lines.append(f"Usage: {usage}")

        return "\n".join(lines)

    async def _invoke(self, thread_id: str, command_name: str, args: str) -> str:
        """
        Invoke a custom command.

        Args:
            thread_id: Signal thread ID
            command_name: Name of command to invoke
            args: Command arguments

        Returns:
            Success message or error
        """
        # Check if command exists
        command = await self.registry.get_command(command_name)
        if command is None:
            return f"Command '{command_name}' not found.\n\nUse '/custom list' to see available commands."

        # Check for active session
        session_id = self._active_sessions.get(thread_id)
        if session_id is None:
            return "Error: No active session.\n\nStart a session first with '/session start <path>'"

        # Execute command via orchestrator
        if self.orchestrator:
            await self.orchestrator.execute_custom_command(
                command_name=command_name,
                args=args,
                thread_id=thread_id
            )

        return f"▶️ Executing custom command: {command_name}"

    def _help(self) -> str:
        """
        Return help message.

        Returns:
            Help text with available commands
        """
        return """Available commands:

/custom list - List all available custom commands
/custom show <name> - Show details for a specific command
/custom invoke <name> [args] - Execute a custom command
/custom help - Show this help message

Custom commands are stored in your .claude/commands/ directory and synced automatically."""
