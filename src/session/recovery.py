"""
Crash Recovery - AUTO-PAUSE ACTIVE sessions on daemon restart.

GREEN Phase: Implementation to make tests pass.

When daemon crashes, any sessions in ACTIVE state are orphaned
(their Claude Code processes are killed by the OS). On daemon restart,
this module detects those ACTIVE sessions and transitions them to PAUSED,
allowing users to resume work.
"""

from datetime import datetime, UTC
from typing import TYPE_CHECKING, List

from src.session.manager import Session, SessionStatus

if TYPE_CHECKING:
    from src.session.manager import SessionManager
    from src.session.lifecycle import SessionLifecycle


class CrashRecovery:
    """
    Detects and recovers from daemon crashes.

    On daemon startup, finds sessions that were ACTIVE when daemon crashed
    and transitions them to PAUSED state for user resumption.
    """

    def __init__(
        self,
        session_manager: "SessionManager",
        session_lifecycle: "SessionLifecycle"
    ):
        """
        Initialize CrashRecovery.

        Args:
            session_manager: SessionManager for database access
            session_lifecycle: SessionLifecycle for state transitions
        """
        self.session_manager = session_manager
        self.session_lifecycle = session_lifecycle

    async def detect_crashed_sessions(self) -> List[Session]:
        """
        Detect sessions that were ACTIVE when daemon crashed.

        Returns:
            List of Session objects with status=ACTIVE
        """
        all_sessions = await self.session_manager.list()
        crashed_sessions = [
            session for session in all_sessions
            if session.status == SessionStatus.ACTIVE
        ]
        return crashed_sessions

    async def recover(self) -> List[str]:
        """
        Recover crashed sessions by transitioning ACTIVE → PAUSED.

        Finds all ACTIVE sessions and transitions them to PAUSED,
        adding a recovered_at timestamp to their context.

        Returns:
            List of session IDs that were recovered
        """
        crashed_sessions = await self.detect_crashed_sessions()

        if not crashed_sessions:
            return []

        recovered_ids = []
        recovery_time = datetime.now(UTC).isoformat()

        for session in crashed_sessions:
            # Transition ACTIVE → PAUSED (validates state machine rules)
            await self.session_lifecycle.transition(
                session_id=session.id,
                from_status=SessionStatus.ACTIVE,
                to_status=SessionStatus.PAUSED
            )

            # Add recovered_at timestamp to context (preserves existing data)
            updated_context = {**session.context, "recovered_at": recovery_time}
            await self.session_manager.update(
                session_id=session.id,
                context=updated_context
            )

            recovered_ids.append(session.id)

        return recovered_ids
