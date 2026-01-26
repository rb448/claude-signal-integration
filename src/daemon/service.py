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

logger = structlog.get_logger(__name__)


class ServiceDaemon:
    """Main daemon service managing Signal bot lifecycle.

    Coordinates SignalClient, MessageQueue, and health check endpoint.
    Handles graceful shutdown on SIGTERM/SIGINT.
    """

    def __init__(self, signal_api_url: str = "ws://localhost:8080") -> None:
        """Initialize service daemon.

        Args:
            signal_api_url: WebSocket URL for signal-cli-rest-api
        """
        self.signal_client = SignalClient(api_url=signal_api_url)
        self.message_queue = MessageQueue()
        self.phone_verifier = PhoneVerifier()
        self._shutdown_event = asyncio.Event()
        self._health_app: Optional[web.Application] = None
        self._health_runner: Optional[web.AppRunner] = None

        # Session management components
        self.session_manager = SessionManager()
        self.session_lifecycle = SessionLifecycle(self.session_manager)
        self.crash_recovery = CrashRecovery(self.session_manager, self.session_lifecycle)
        self.session_commands = SessionCommands(
            self.session_manager,
            self.session_lifecycle,
            lambda sid, path: ClaudeProcess(sid, path)
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
        # Message format depends on signal-cli-rest-api protocol
        sender = message.get("sender", message.get("source", ""))
        text = message.get("message", message.get("text", ""))
        thread_id = message.get("thread_id", sender)  # Use sender as thread_id if not provided

        # Verify sender is authorized
        if not self.phone_verifier.verify(sender):
            logger.warning(
                "message_ignored_unauthorized",
                sender=sender,
                message_preview=str(message)[:100]
            )
            return

        # Route /session commands
        if text.startswith("/session"):
            logger.info("routing_session_command", sender=sender, command=text)
            response = await self.session_commands.handle(thread_id, text)
            # Send response back to user
            try:
                await self.signal_client.send_message(sender, response)
                logger.info("session_command_response", response=response)
            except Exception as e:
                logger.error("send_response_failed", error=str(e), recipient=sender)
            return

        # Process authorized message
        logger.info(
            "message_processing_authorized",
            sender=sender,
            message=message
        )

        # Placeholder for other command handling logic
        # Will be expanded in future phases with Claude API integration
        logger.debug("message_received", message=message)

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
                logger.info("signal_connected", api_url=self.signal_client.api_url)
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
                        logger.info(
                            "message_received_enqueued",
                            sender=message.get("source"),
                            timestamp=message.get("timestamp")
                        )
                except Exception as e:
                    logger.error("receive_loop_error", error=str(e))
                    raise

            receive_task = asyncio.create_task(receive_loop())

            logger.info("daemon_running")

            # Wait for shutdown signal
            await self._shutdown_event.wait()

            logger.info("daemon_shutting_down")

            # Stop message queue processing and receiving
            self.message_queue.stop_processing()
            queue_task.cancel()
            receive_task.cancel()
            try:
                await asyncio.gather(queue_task, receive_task, return_exceptions=True)
            except asyncio.CancelledError:
                pass

            # Disconnect from Signal API
            await self.signal_client.disconnect()

            # Stop health check endpoint
            await self._stop_health_server()

            # Close session manager database connection
            await self.session_manager.close()
            logger.info("session_manager_closed")

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

    daemon = ServiceDaemon()

    try:
        asyncio.run(daemon.run())
    except KeyboardInterrupt:
        logger.info("daemon_interrupted")
    except Exception as e:
        logger.error("daemon_fatal_error", error=str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
