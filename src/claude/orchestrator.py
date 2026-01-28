"""ClaudeOrchestrator coordinates command flow from Signal to Claude CLI and back."""

import asyncio
import re
from typing import Callable, Optional, TYPE_CHECKING

from .bridge import CLIBridge
from .parser import OutputParser, OutputType
from .responder import SignalResponder, MessageBatcher

if TYPE_CHECKING:
    from src.approval.workflow import ApprovalWorkflow
    from src.notification.manager import NotificationManager


class ClaudeOrchestrator:
    """
    Orchestrate command execution flow: Signal → Claude CLI → Signal.

    Coordinates:
    - Sending commands to Claude CLI via CLIBridge
    - Parsing output via OutputParser
    - Formatting for Signal via SignalResponder
    - Batching and sending messages back to Signal
    """

    # TODO (Phase 8): Catch-up summary generation after reconnection
    #
    # After mobile reconnects, generate summary of Claude activity during disconnect:
    # 1. Fetch session.context["activity_log"] from SessionManager
    # 2. Generate plain-English summary: "While you were offline, I completed..."
    # 3. Send summary message before draining buffered responses
    #
    # Example summary:
    #   "📱 Back online! While you were disconnected, I:
    #    - Analyzed the authentication module (3 issues found)
    #    - Ran 24 tests (all passed)
    #    - Created 2 new files
    #
    #    Sending full results now..."
    #
    # This satisfies CONN-05's "user catches up on reconnect" requirement.

    # Batch interval for message sending (seconds)
    BATCH_INTERVAL = 0.5

    def __init__(
        self,
        bridge: Optional[CLIBridge],
        parser: OutputParser,
        responder: SignalResponder,
        send_signal: Callable[[str, str], asyncio.Future],
        approval_workflow: Optional["ApprovalWorkflow"] = None,
        notification_manager: Optional["NotificationManager"] = None,
    ):
        """
        Initialize ClaudeOrchestrator.

        Args:
            bridge: CLIBridge for communicating with Claude CLI (None until session starts)
            parser: OutputParser for parsing CLI output
            responder: SignalResponder for formatting messages
            send_signal: Async callback to send Signal messages (recipient, message)
            approval_workflow: Optional ApprovalWorkflow for operation approval
            notification_manager: Optional NotificationManager for event notifications
        """
        self.bridge = bridge
        self.parser = parser
        self.responder = responder
        self.send_signal = send_signal
        self.approval_workflow = approval_workflow
        self.notification_manager = notification_manager
        self.session_id: Optional[str] = None
        self.current_thread_id: Optional[str] = None

    async def execute_command(self, command: str, session_id: str, recipient: str, thread_id: str | None = None) -> None:
        """
        Execute a command and stream results back to Signal.

        Args:
            command: Command text to send to Claude CLI
            session_id: Session ID for routing responses
            recipient: Signal recipient (phone number) for attachment uploads
            thread_id: Optional Signal thread ID for notifications

        Process:
        1. Send command via bridge
        2. Read streaming response
        3. Parse each line
        4. Format for Signal
        5. Batch and send messages
        """
        self.session_id = session_id
        self.current_thread_id = thread_id or recipient

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

                # Check if this is a tool call requiring approval
                if parsed.type == OutputType.TOOL_CALL and self.approval_workflow:
                    approved, request_id = self.approval_workflow.intercept(parsed)

                    if not approved:
                        # Operation requires approval - notify user
                        _, reason = self.approval_workflow.detector.classify(parsed)
                        approval_msg = self.approval_workflow.format_approval_message(
                            parsed, reason, request_id
                        )
                        await self._send_message(approval_msg)

                        # Wait for user approval
                        is_approved = await self.approval_workflow.wait_for_approval(
                            request_id
                        )

                        if not is_approved:
                            # Rejected or timed out - skip operation
                            rejection_msg = f"❌ Operation rejected or timed out - skipping {parsed.tool}"
                            await self._send_message(rejection_msg)
                            continue

                        # Approved - notify and proceed
                        approval_msg = f"✅ Operation approved - executing {parsed.tool}"
                        await self._send_message(approval_msg)

                # Format for Signal display
                formatted = self.responder.format(parsed)

                # Check if formatted message has attachment markers
                attachment_marker_pattern = r'\[Code too long \(\d+ lines\) - attachment coming\.\.\.\]'
                if re.search(attachment_marker_pattern, formatted):
                    # Extract code blocks for attachment
                    code_blocks = []

                    # Response type contains the actual text content
                    if parsed.type == OutputType.RESPONSE and hasattr(parsed, 'text'):
                        # Generate timestamped filename
                        import time
                        timestamp = int(time.time())
                        filename = f"output_{timestamp}.txt"

                        code_blocks.append((parsed.text, filename))

                    # Upload attachments and get updated message
                    if code_blocks:
                        formatted = await self.responder.send_with_attachments(
                            formatted, code_blocks, recipient
                        )

                # Add to batch
                batcher.add(formatted)

                # Flush if batch interval elapsed
                if batcher.should_flush():
                    await self._flush_batch(batcher)

            # Flush any remaining messages
            await self._flush_batch(batcher)

            # Send completion notification
            if self.notification_manager and self.current_thread_id:
                await self.notification_manager.notify(
                    event_type="completion",
                    details={"message": "Task finished", "status": "complete"},
                    thread_id=self.current_thread_id,
                    session_id=session_id
                )

        except Exception as e:
            # Handle bridge errors and convert to user-facing error
            error_msg = self.responder.format(
                self.parser.parse(f"Error: {str(e)}")
            )
            await self._send_message(error_msg)

            # Send error notification
            if self.notification_manager and self.current_thread_id:
                await self.notification_manager.notify(
                    event_type="error",
                    details={"error": str(e), "context": "claude_stream"},
                    thread_id=self.current_thread_id,
                    session_id=self.session_id
                )

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

    def approve_operation(self, request_id: str) -> None:
        """
        Approve an operation approval request.

        Args:
            request_id: ID of approval request to approve

        Raises:
            KeyError: If request_id does not exist
        """
        if self.approval_workflow:
            self.approval_workflow.manager.approve(request_id)

    def reject_operation(self, request_id: str) -> None:
        """
        Reject an operation approval request.

        Args:
            request_id: ID of approval request to reject

        Raises:
            KeyError: If request_id does not exist
        """
        if self.approval_workflow:
            self.approval_workflow.manager.reject(request_id)
