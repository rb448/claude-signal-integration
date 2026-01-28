"""File system watcher for custom Claude Code commands."""
import asyncio
import frontmatter
import structlog
from pathlib import Path
from typing import Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from .registry import CustomCommandRegistry


logger = structlog.get_logger(__name__)


class CommandFileHandler(FileSystemEventHandler):
    """Handles file system events for command files."""

    def __init__(self, syncer: "CommandSyncer", loop: asyncio.AbstractEventLoop):
        """Initialize handler with reference to syncer and event loop.

        Args:
            syncer: CommandSyncer instance to notify of file changes
            loop: Event loop to schedule async tasks in
        """
        self.syncer = syncer
        self.loop = loop
        super().__init__()

    def on_created(self, event: FileSystemEvent):
        """Handle file creation events."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        if file_path.suffix == ".md":
            asyncio.run_coroutine_threadsafe(
                self.syncer._handle_file_created(file_path),
                self.loop
            )

    def on_modified(self, event: FileSystemEvent):
        """Handle file modification events."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        if file_path.suffix == ".md":
            asyncio.run_coroutine_threadsafe(
                self.syncer._handle_file_modified(file_path),
                self.loop
            )

    def on_deleted(self, event: FileSystemEvent):
        """Handle file deletion events."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        if file_path.suffix == ".md":
            asyncio.run_coroutine_threadsafe(
                self.syncer._handle_file_deleted(file_path),
                self.loop
            )


class CommandSyncer:
    """Monitors ~/.claude/agents/ and synchronizes commands to registry.

    Uses watchdog for file system monitoring and updates the CustomCommandRegistry
    when command files are created, modified, or deleted.
    """

    def __init__(
        self,
        agents_dir: Optional[Path] = None,
        registry: Optional[CustomCommandRegistry] = None
    ):
        """Initialize command syncer.

        Args:
            agents_dir: Directory to monitor. Defaults to ~/.claude/agents/
            registry: Command registry to update. Required for actual operation.
        """
        if agents_dir is None:
            agents_dir = Path.home() / ".claude" / "agents"

        self.agents_dir = agents_dir
        self.registry = registry
        self.observer: Optional[Observer] = None

    def _parse_command_file(self, file_path: Path) -> Optional[dict]:
        """Parse command file and extract frontmatter metadata.

        Args:
            file_path: Path to command .md file

        Returns:
            Metadata dict with name, description, etc., or None if invalid
        """
        # Only parse .md files
        if file_path.suffix != ".md":
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                post = frontmatter.load(f)

            # Require 'name' field
            if 'name' not in post.metadata:
                logger.warning(
                    "command_file_missing_name",
                    file_path=str(file_path)
                )
                return None

            return post.metadata

        except Exception as e:
            logger.warning(
                "command_parse_error",
                file_path=str(file_path),
                error=str(e)
            )
            return None

    async def initial_scan(self):
        """Scan agents directory and load all existing commands."""
        # Create directory if it doesn't exist
        self.agents_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "scanning_agents_directory",
            agents_dir=str(self.agents_dir)
        )

        count = 0
        for md_file in self.agents_dir.glob("*.md"):
            metadata = self._parse_command_file(md_file)
            if metadata and self.registry:
                command_name = metadata["name"]
                await self.registry.add_command(
                    name=command_name,
                    file_path=str(md_file),
                    metadata=metadata
                )
                count += 1
                logger.debug(
                    "command_loaded",
                    command_name=command_name,
                    file_path=str(md_file)
                )

        logger.info(
            "initial_scan_complete",
            commands_loaded=count
        )

    async def _handle_file_created(self, file_path: Path):
        """Handle new command file creation.

        Args:
            file_path: Path to newly created file
        """
        metadata = self._parse_command_file(file_path)
        if metadata and self.registry:
            command_name = metadata["name"]
            await self.registry.add_command(
                name=command_name,
                file_path=str(file_path),
                metadata=metadata
            )
            logger.info(
                "command_added",
                command_name=command_name,
                file_path=str(file_path)
            )

    async def _handle_file_modified(self, file_path: Path):
        """Handle command file modification.

        Args:
            file_path: Path to modified file
        """
        metadata = self._parse_command_file(file_path)
        if metadata and self.registry:
            command_name = metadata["name"]
            # Use add_command (idempotent) to update
            await self.registry.add_command(
                name=command_name,
                file_path=str(file_path),
                metadata=metadata
            )
            logger.info(
                "command_updated",
                command_name=command_name,
                file_path=str(file_path)
            )

    async def _handle_file_deleted(self, file_path: Path):
        """Handle command file deletion.

        Args:
            file_path: Path to deleted file
        """
        # Extract command name from filename (without .md extension)
        # This is a fallback since we can't parse the deleted file
        # Actual command name should match the filename by convention
        command_name = file_path.stem

        if self.registry:
            await self.registry.remove_command(command_name)
            logger.info(
                "command_removed",
                command_name=command_name,
                file_path=str(file_path)
            )

    def start(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        """Start monitoring the agents directory.

        Args:
            loop: Event loop to schedule async tasks in. If None, gets running loop.
        """
        if self.observer is not None:
            logger.warning("syncer_already_running")
            return

        if loop is None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()

        # Create directory if it doesn't exist
        self.agents_dir.mkdir(parents=True, exist_ok=True)

        # Create and start observer
        self.observer = Observer()
        event_handler = CommandFileHandler(self, loop)
        self.observer.schedule(event_handler, str(self.agents_dir), recursive=False)
        self.observer.start()

        logger.info(
            "syncer_started",
            agents_dir=str(self.agents_dir)
        )

    def stop(self):
        """Stop monitoring the agents directory."""
        if self.observer is not None:
            self.observer.stop()
            self.observer.join()
            self.observer = None

            logger.info("syncer_stopped")
