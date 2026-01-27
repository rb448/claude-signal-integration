"""Main daemon service for Signal-Claude integration bot."""

import asyncio
import logging
import signal as signal_module
import sys
from typing import Optional

import structlog
from aiohttp import web

from ..auth.phone_verifier import PhoneVerifier
from ..signal.client import SignalClient
from ..signal.queue import MessageQueue
from ..session import SessionManager, SessionLifecycle, CrashRecovery, SessionCommands
from ..claude import ClaudeProcess
from ..claude.orchestrator import ClaudeOrchestrator
from ..claude.parser import OutputParser
from ..claude.responder import SignalResponder
from ..thread import ThreadMapper, ThreadCommands
from ..approval.detector import OperationDetector
from ..approval.manager import ApprovalManager
from ..approval.workflow import ApprovalWorkflow
from ..approval.commands import ApprovalCommands

logger = structlog.get_logger(__name__)


class ServiceDaemon:
    """Main daemon service managing Signal bot lifecycle.

    Coordinates SignalClient, MessageQueue, and health check endpoint.
    Handles graceful shutdown on SIGTERM/SIGINT.
    """

    def __init__(
        self,
        signal_api_url: str = "http://localhost:8080",
        signal_phone_number: str = "+19735258994"
    ) -> None:
        """Initialize service daemon.

        Args:
            signal_api_url: HTTP URL for signal-cli-rest-api
            signal_phone_number: Bot's registered Signal phone number
        """
        self.signal_client = SignalClient(
            api_url=signal_api_url,
            phone_number=signal_phone_number
        )
        self.message_queue = MessageQueue()
        self.phone_verifier = PhoneVerifier()
        self._shutdown_event = asyncio.Event()
        self._health_app: Optional[web.Application] = None
        self._health_runner: Optional[web.AppRunner] = None

        # Session management components
        self.session_manager = SessionManager()
        self.session_lifecycle = SessionLifecycle(self.session_manager)
        self.crash_recovery = CrashRecovery(self.session_manager, self.session_lifecycle)

        # Thread mapping component (initialized in async start())
        # Get data directory from session manager pattern
        from pathlib import Path
        data_dir = Path.home() / "Library" / "Application Support" / "claude-signal-bot"
        thread_db_path = data_dir / "thread_mappings.db"
        self.thread_mapper = ThreadMapper(str(thread_db_path))

        # Approval system
        self.approval_detector = OperationDetector()
        self.approval_manager = ApprovalManager()
        self.approval_workflow = ApprovalWorkflow(
            detector=self.approval_detector,
            manager=self.approval_manager
        )

        # Claude integration components
        self.output_parser = OutputParser()
        self.signal_responder = SignalResponder()
        self.claude_orchestrator = ClaudeOrchestrator(
            bridge=None,  # Bridge set when session starts
            parser=self.output_parser,
            responder=self.signal_responder,
            send_signal=self.signal_client.send_message,
            approval_workflow=self.approval_workflow
        )

        # Session commands (thread_commands will be set in async start())
        self.session_commands = SessionCommands(
            self.session_manager,
            self.session_lifecycle,
            lambda sid, path: ClaudeProcess(sid, path),
            claude_orchestrator=self.claude_orchestrator,
            thread_mapper=self.thread_mapper
        )

    async def _health_check_handler(self, request: web.Request) -> web.Response:
        """Health check endpoint handler.

        Args:
            request: HTTP request from health check client

        Returns:
            JSON response with status
        """
        return web.json_response({"status": "ok"})

    async def _start_health_server(self) -> None:
        """Start HTTP health check endpoint on port 8081."""
        self._health_app = web.Application()
        self._health_app.router.add_get("/health", self._health_check_handler)

        self._health_runner = web.AppRunner(self._health_app)
        await self._health_runner.setup()

        site = web.TCPSite(self._health_runner, "localhost", 8081)
        await site.start()

        logger.info("health_check_started", port=8081)

    async def _stop_health_server(self) -> None:
        """Stop HTTP health check endpoint."""
        if self._health_runner:
            await self._health_runner.cleanup()
            logger.info("health_check_stopped")

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        loop = asyncio.get_running_loop()

        for sig in (signal_module.SIGTERM, signal_module.SIGINT):
            loop.add_signal_handler(
                sig,
                lambda s=sig: asyncio.create_task(self._handle_shutdown(s))
            )

    async def _handle_shutdown(self, sig: signal_module.Signals) -> None:
        """Handle shutdown signal.

        Args:
            sig: Signal that triggered shutdown
        """
        logger.info("shutdown_signal_received", signal=sig.name)
        self._shutdown_event.set()

    async def _process_message(self, message: dict) -> None:
        """Process a single message from the queue.

        Args:
            message: Message data to process
        """
        # Extract sender phone number and message text from message
        # Message format from signal-cli-rest-api: {"envelope": {"sourceNumber": "...", "dataMessage": {"message": "..."}}}
        envelope = message.get("envelope", {})
        sender = envelope.get("sourceNumber", envelope.get("source", ""))
        data_message = envelope.get("dataMessage", {})
        text = data_message.get("message", "")
        thread_id = message.get("thread_id", sender)  # Use sender as thread_id if not provided

        # Verify sender is authorized
        if not self.phone_verifier.verify(sender):
            logger.warning(
                "message_ignored_unauthorized",
                sender=sender,
                message_preview=str(message)[:100]
            )
            return

        # Route all commands through session_commands
        # SessionCommands will route /session commands vs Claude commands
        logger.info("routing_command", sender=sender, command=text[:50])
        response = await self.session_commands.handle(thread_id, text)

        # Send response back to user if there is one
        # (Claude commands return None as orchestrator handles streaming responses)
        if response is not None:
            try:
                await self.signal_client.send_message(sender, response)
                logger.info("command_response_sent", response_preview=response[:100])
            except Exception as e:
                logger.error("send_response_failed", error=str(e), recipient=sender)

    async def run(self) -> None:
        """Run the daemon service.

        Main event loop that:
        1. Starts health check endpoint
        2. Connects to Signal API
        3. Processes messages from queue
        4. Handles graceful shutdown
        """
        logger.info("daemon_starting")

        try:
            # Setup signal handlers for graceful shutdown
            self._setup_signal_handlers()

            # Initialize session manager
            await self.session_manager.initialize()
            logger.info("session_manager_initialized")

            # Initialize thread mapper
            await self.thread_mapper.initialize()
            logger.info("thread_mapper_initialized")

            # Load and log thread mappings
            mappings = await self.thread_mapper.list_all()
            if mappings:
                logger.info(
                    "thread_mappings_loaded",
                    thread_count=len(mappings)
                )
            else:
                logger.info("no_thread_mappings_configured")

            # Create thread commands (requires initialized mapper)
            self.thread_commands = ThreadCommands(self.thread_mapper)

            # Wire thread commands into session commands
            self.session_commands.thread_commands = self.thread_commands

            # Approval commands (no async init needed)
            approval_commands = ApprovalCommands(manager=self.approval_manager)

            # Wire approval commands into session commands
            self.session_commands.approval_commands = approval_commands

            # Log approval system initialization
            logger.info(
                "approval_system_initialized",
                safe_tools=len(self.approval_detector.SAFE_TOOLS),
                destructive_tools=len(self.approval_detector.DESTRUCTIVE_TOOLS),
                pending_approvals=len(self.approval_manager.list_pending())
            )

            # Run crash recovery
            recovered = await self.crash_recovery.recover()
            if recovered:
                logger.warning(
                    "sessions_recovered",
                    count=len(recovered),
                    session_ids=recovered
                )
                # Send Signal notification to authorized user about recovered sessions
                try:
                    session_ids_str = ', '.join(r[:8] for r in recovered)
                    await self.signal_client.send_message(
                        self.phone_verifier.authorized_number,
                        f"⚠️ Recovered {len(recovered)} sessions after restart: {session_ids_str}"
                    )
                except Exception as e:
                    logger.error("send_recovery_notification_failed", error=str(e))

            # Start health check endpoint
            await self._start_health_server()

            # Connect to Signal API
            try:
                await self.signal_client.connect()
                logger.info(
                    "daemon_started",
                    phone_number=self.phone_verifier.authorized_number,
                    health_port=8081,
                    connection_resilience="enabled",
                    reconnection_backoff="exponential_1s_to_60s",
                    message_buffer_size=100
                )
            except ConnectionError as e:
                logger.error("signal_connection_failed", error=str(e))
                return

            # Start message queue processing
            queue_task = asyncio.create_task(
                self.message_queue.process_queue(self._process_message)
            )

            # Start message receiving loop
            async def receive_loop():
                """Continuously receive messages from Signal and put them in queue."""
                try:
                    async for message in self.signal_client.receive_messages():
                        await self.message_queue.put(message)
                        envelope = message.get("envelope", {})
                        sender = envelope.get("sourceNumber", envelope.get("source"))
                        timestamp = envelope.get("timestamp")
                        logger.info(
                            "message_received_enqueued",
                            sender=sender,
                            timestamp=timestamp
                        )
                except Exception as e:
                    logger.error("receive_loop_error", error=str(e))
                    raise

            receive_task = asyncio.create_task(receive_loop())

            # Monitor connection state changes
            async def monitor_connection_state():
                """Monitor and log connection state changes."""
                last_state = self.signal_client.reconnection_manager.state
                while not self._shutdown_event.is_set():
                    await asyncio.sleep(1)  # Check state every second
                    current_state = self.signal_client.reconnection_manager.state
                    if current_state != last_state:
                        logger.info(
                            "connection_status_changed",
                            old_state=last_state.name,
                            new_state=current_state.name
                        )
                        if current_state.name == "RECONNECTING":
                            logger.info(
                                "reconnection_attempt",
                                attempt_count=self.signal_client.reconnection_manager.attempt_count,
                                backoff_delay=self.signal_client.reconnection_manager.calculate_backoff()
                            )
                        last_state = current_state

            monitor_task = asyncio.create_task(monitor_connection_state())

            logger.info("daemon_running")

            # Wait for shutdown signal
            await self._shutdown_event.wait()

            logger.info("daemon_shutting_down")

            # Stop message queue processing and receiving
            self.message_queue.stop_processing()
            queue_task.cancel()
            receive_task.cancel()
            monitor_task.cancel()
            try:
                await asyncio.gather(queue_task, receive_task, monitor_task, return_exceptions=True)
            except asyncio.CancelledError:
                pass

            # Disconnect from Signal API
            await self.signal_client.disconnect()

            # Stop health check endpoint
            await self._stop_health_server()

            # Close session manager database connection
            await self.session_manager.close()
            logger.info("session_manager_closed")

            # Close thread mapper database connection
            await self.thread_mapper.close()
            logger.info("thread_mapper_closed")

            logger.info("daemon_stopped")

        except Exception as e:
            logger.error("daemon_error", error=str(e), exc_info=True)
            raise


def main() -> None:
    """Entry point for daemon service."""
    # Configure structlog for production logging
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Load configuration from config/daemon.json
    import json
    from pathlib import Path
    config_path = Path(__file__).parent.parent.parent / "config" / "daemon.json"

    try:
        with open(config_path) as f:
            config = json.load(f)
        signal_api_url = config.get("signal_api_url", "ws://localhost:8080")
    except Exception as e:
        logger.warning("config_load_failed", error=str(e), using_default=True)
        signal_api_url = "ws://localhost:8080"

    daemon = ServiceDaemon(signal_api_url=signal_api_url)

    try:
        asyncio.run(daemon.run())
    except KeyboardInterrupt:
        logger.info("daemon_interrupted")
    except Exception as e:
        logger.error("daemon_fatal_error", error=str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
