"""
Thread command handlers for Signal bot.

GREEN Phase: Implement ThreadCommands to make tests pass.
"""

from pathlib import Path
from src.thread import ThreadMapper, ThreadMappingError


class ThreadCommands:
    """
    Handles /thread commands for managing thread-to-project mappings.

    Parses and routes:
    - /thread map <path> - Create thread-to-project mapping
    - /thread list - List all mappings
    - /thread unmap - Remove current thread's mapping
    - /thread help - Show command documentation
    """

    def __init__(self, mapper: ThreadMapper):
        """
        Initialize ThreadCommands.

        Args:
            mapper: ThreadMapper instance for persistence
        """
        self.mapper = mapper

    async def handle(self, thread_id: str, message: str) -> str:
        """
        Handle /thread command.

        Args:
            thread_id: Signal thread ID for this command
            message: Full message text starting with /thread

        Returns:
            Response message to send back to user
        """
        # Parse: /thread <subcommand> [args]
        parts = message.strip().split()
        if len(parts) < 2:
            return self._help()

        subcommand = parts[1]

        if subcommand == "map":
            project_path = parts[2] if len(parts) > 2 else None
            return await self._map(thread_id, project_path)
        elif subcommand == "list":
            return await self._list()
        elif subcommand == "unmap":
            return await self._unmap(thread_id)
        elif subcommand == "help":
            return self._help()
        else:
            return self._help()

    async def _map(self, thread_id: str, project_path: str | None) -> str:
        """
        Create thread-to-project mapping.

        Args:
            thread_id: Signal thread ID
            project_path: Path to project directory

        Returns:
            Success or error message
        """
        if project_path is None:
            return "Error: Missing project path\n\nUsage: /thread map <project_path>"

        # Validate path exists (ThreadMapper.map also validates, but provide clear message)
        path = Path(project_path)
        if not path.exists():
            return f"Error: Path does not exist: {project_path}"

        try:
            # Create mapping
            mapping = await self.mapper.map(thread_id, project_path)

            # Return success message with truncated thread ID
            short_id = thread_id[:8]
            return f"✓ Thread {short_id} mapped to {project_path}"

        except ThreadMappingError as e:
            # Convert ThreadMappingError to user-friendly message
            error_msg = str(e)

            # Make error messages more user-friendly
            if "already mapped to" in error_msg and "Thread" in error_msg:
                # Thread already mapped
                return f"Error: This thread is already mapped. Use '/thread unmap' first.\n\n{error_msg}"
            elif "already mapped to thread" in error_msg:
                # Path already mapped to another thread
                existing_thread_id = error_msg.split("thread ")[-1]
                short_existing = existing_thread_id[:8] if len(existing_thread_id) > 8 else existing_thread_id
                return f"Error: Path {project_path} is already mapped to thread {short_existing}"
            else:
                # Generic error
                return f"Error: {error_msg}"

    async def _list(self) -> str:
        """
        List all thread-to-project mappings.

        Returns:
            Formatted table of mappings or "No mappings" message
        """
        mappings = await self.mapper.list_all()

        if not mappings:
            return "No thread mappings."

        # Format as table
        lines = ["Thread Mappings:", ""]
        lines.append("Thread   | Project Path                   | Created")
        lines.append("-" * 70)

        for mapping in mappings:
            # Truncate thread ID for display
            short_id = mapping.thread_id[:8]

            # Truncate project path for display if too long
            project = mapping.project_path
            if len(project) > 30:
                project = "..." + project[-27:]

            # Format timestamp as date + time
            created = mapping.created_at.strftime("%Y-%m-%d %H:%M")

            lines.append(f"{short_id} | {project:30} | {created}")

        return "\n".join(lines)

    async def _unmap(self, thread_id: str) -> str:
        """
        Remove thread-to-project mapping.

        Args:
            thread_id: Signal thread ID

        Returns:
            Success message
        """
        # Remove mapping (idempotent operation)
        await self.mapper.unmap(thread_id)

        # Return success message with truncated thread ID
        short_id = thread_id[:8]
        return f"✓ Thread {short_id} unmapped"

    def _help(self) -> str:
        """
        Return help message.

        Returns:
            Help text with available commands
        """
        return """Available commands:

/thread map <project_path> - Map this thread to a project directory
/thread list - List all thread mappings
/thread unmap - Remove this thread's mapping
/thread help - Show this help message

Thread mappings persist across daemon restarts and allow you to work on multiple projects from different Signal threads."""
