"""
CLIBridge for bidirectional communication with Claude Code CLI subprocess.

Provides stdin/stdout interface for:
- Sending commands to Claude Code CLI
- Reading responses from Claude Code CLI
- Monitoring connection status
"""

import asyncio
from typing import AsyncGenerator


class CLIBridge:
    """
    Bridge for communicating with Claude Code CLI via stdin/stdout.

    Manages:
    - Command input via stdin
    - Response output via stdout
    - Connection status monitoring
    """

    def __init__(self, process: asyncio.subprocess.Process):
        """
        Initialize CLIBridge with subprocess.

        Args:
            process: Running Claude Code CLI subprocess with stdin/stdout pipes
        """
        self._process = process

    async def send_command(self, command: str) -> None:
        """
        Send command to Claude Code CLI via stdin.

        Commands are sent as UTF-8 encoded text with newline terminator.
        The write is immediately flushed to ensure delivery.

        Args:
            command: Command text to send (newline will be added)

        Raises:
            ValueError: If stdin is not available
        """
        if self._process.stdin is None:
            raise ValueError("Process stdin is not available")

        # Encode command with newline as UTF-8 bytes
        data = f"{command}\n".encode('utf-8')

        # Write to stdin
        self._process.stdin.write(data)

        # Flush to ensure immediate delivery
        await self._process.stdin.drain()

    async def read_response(self) -> AsyncGenerator[str, None]:
        """
        Read response lines from Claude Code CLI stdout.

        Yields lines until empty line or EOF is encountered.
        Each line is UTF-8 decoded with newline stripped.

        Yields:
            Response lines as strings

        Raises:
            ValueError: If stdout is not available
        """
        if self._process.stdout is None:
            raise ValueError("Process stdout is not available")

        while True:
            # Read one line from stdout
            line_bytes = await self._process.stdout.readline()

            # Empty bytes means EOF or end of output
            if not line_bytes:
                break

            # Decode UTF-8 and strip newline
            line = line_bytes.decode('utf-8').rstrip('\n')

            # Yield the line
            yield line

    @property
    def is_connected(self) -> bool:
        """
        Check if bridge is connected to running process.

        Returns:
            True if process is still running (returncode is None)
        """
        return self._process.returncode is None
