"""
Session Lifecycle - State machine for session transitions.

Enforces valid state transitions and prevents invalid lifecycle changes.
"""

from typing import TYPE_CHECKING

from src.session.manager import SessionStatus, Session

if TYPE_CHECKING:
    from src.session.manager import SessionManager


class StateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass


# Valid state transition rules
# Set of (from_state, to_state) tuples representing allowed transitions
VALID_TRANSITIONS = {
    # From CREATED
    (SessionStatus.CREATED, SessionStatus.ACTIVE),
    (SessionStatus.CREATED, SessionStatus.TERMINATED),

    # From ACTIVE
    (SessionStatus.ACTIVE, SessionStatus.ACTIVE),  # Idempotent
    (SessionStatus.ACTIVE, SessionStatus.PAUSED),
    (SessionStatus.ACTIVE, SessionStatus.TERMINATED),

    # From PAUSED
    (SessionStatus.PAUSED, SessionStatus.PAUSED),  # Idempotent
    (SessionStatus.PAUSED, SessionStatus.ACTIVE),
    (SessionStatus.PAUSED, SessionStatus.TERMINATED),

    # From TERMINATED - no valid transitions (terminal state)
    (SessionStatus.TERMINATED, SessionStatus.TERMINATED),  # Idempotent
}


class SessionLifecycle:
    """
    Manages session state transitions with validation.

    Enforces valid lifecycle transitions and prevents invalid state changes.
    Persists all state changes to database via SessionManager.
    """

    def __init__(self, session_manager: "SessionManager"):
        """
        Initialize SessionLifecycle.

        Args:
            session_manager: SessionManager instance for database operations
        """
        self.session_manager = session_manager

    async def transition(
        self,
        session_id: str,
        from_status: SessionStatus,
        to_status: SessionStatus
    ) -> Session:
        """
        Transition session from one state to another.

        Args:
            session_id: UUID of session to transition
            from_status: Expected current status (verified against DB)
            to_status: Desired new status

        Returns:
            Updated Session object with new status

        Raises:
            StateTransitionError: If transition is invalid or status mismatch
        """
        # Verify current status matches expected
        current_session = await self.session_manager.get(session_id)
        if current_session is None:
            raise StateTransitionError(f"Session {session_id} not found")

        if current_session.status != from_status:
            raise StateTransitionError(
                f"Status mismatch: expected {from_status.value}, "
                f"but session is in {current_session.status.value}"
            )

        # Check if transition is valid
        transition_key = (from_status, to_status)
        if transition_key not in VALID_TRANSITIONS:
            raise StateTransitionError(
                f"Invalid transition: {from_status.value} → {to_status.value}"
            )

        # Persist transition to database
        updated_session = await self.session_manager.update(
            session_id=session_id,
            status=to_status
        )

        return updated_session
