"""ClaudeOrchestrator coordinates command flow from Signal to Claude CLI and back."""

import asyncio
from typing import Callable, Optional

from .bridge import CLIBridge
from .parser import OutputParser
from .responder import SignalResponder, MessageBatcher


class ClaudeOrchestrator:
    """
    Orchestrate command execution flow: Signal → Claude CLI → Signal.

    Coordinates:
    - Sending commands to Claude CLI via CLIBridge
    - Parsing output via OutputParser
    - Formatting for Signal via SignalResponder
    - Batching and sending messages back to Signal
    """

    # Batch interval for message sending (seconds)
    BATCH_INTERVAL = 0.5

    def __init__(
        self,
        bridge: Optional[CLIBridge],
        parser: OutputParser,
        responder: SignalResponder,
        send_signal: Callable[[str, str], asyncio.Future],
    ):
        """
        Initialize ClaudeOrchestrator.

        Args:
            bridge: CLIBridge for communicating with Claude CLI (None until session starts)
            parser: OutputParser for parsing CLI output
            responder: SignalResponder for formatting messages
            send_signal: Async callback to send Signal messages (recipient, message)
        """
        self.bridge = bridge
        self.parser = parser
        self.responder = responder
        self.send_signal = send_signal
        self.session_id: Optional[str] = None

    async def execute_command(self, command: str, session_id: str) -> None:
        """
        Execute a command and stream results back to Signal.

        Args:
            command: Command text to send to Claude CLI
            session_id: Session ID for routing responses

        Process:
        1. Send command via bridge
        2. Read streaming response
        3. Parse each line
        4. Format for Signal
        5. Batch and send messages
        """
        self.session_id = session_id

        # Initialize message batcher
        batcher = MessageBatcher(min_batch_interval=self.BATCH_INTERVAL)

        try:
            # Validate bridge is available
            if self.bridge is None:
                error_msg = self.responder.format(
                    self.parser.parse("Error: No active Claude CLI session")
                )
                await self._send_message(error_msg)
                return

            # Send command to Claude CLI
            await self.bridge.send_command(command)

            # Read and process response stream
            async for line in self.bridge.read_response():
                # Parse line into structured event
                parsed = self.parser.parse(line)

                # Format for Signal display
                formatted = self.responder.format(parsed)

                # Add to batch
                batcher.add(formatted)

                # Flush if batch interval elapsed
                if batcher.should_flush():
                    await self._flush_batch(batcher)

            # Flush any remaining messages
            await self._flush_batch(batcher)

        except Exception as e:
            # Handle bridge errors and convert to user-facing error
            error_msg = self.responder.format(
                self.parser.parse(f"Error: {str(e)}")
            )
            await self._send_message(error_msg)

    async def _flush_batch(self, batcher: MessageBatcher) -> None:
        """
        Flush batched messages to Signal.

        Args:
            batcher: MessageBatcher with messages to send
        """
        messages = batcher.flush()
        if messages:
            # Combine messages with newlines
            combined = "\n".join(messages)
            await self._send_message(combined)

    async def _send_message(self, message: str) -> None:
        """
        Send a message to Signal for current session.

        Args:
            message: Message text to send
        """
        if self.session_id:
            # send_signal expects (recipient, message)
            # For now, we'll use session_id as recipient (daemon will map to thread)
            await self.send_signal(self.session_id, message)
