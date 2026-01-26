"""
Session Lifecycle Tests - TDD RED Phase

Tests for session state machine transition validation.
Written BEFORE implementation to define expected behavior.
"""

import pytest
from src.session.manager import SessionManager, SessionStatus
from src.session.lifecycle import SessionLifecycle, StateTransitionError


@pytest.fixture
async def session_manager():
    """Create temporary session manager for testing."""
    manager = SessionManager(db_path=":memory:")
    await manager.initialize()
    yield manager
    await manager.close()


@pytest.fixture
async def lifecycle(session_manager):
    """Create lifecycle manager with test session manager."""
    return SessionLifecycle(session_manager)


@pytest.fixture
async def test_session(session_manager):
    """Create a test session in CREATED state."""
    return await session_manager.create(
        project_path="/test/project",
        thread_id="test-thread"
    )


class TestValidTransitions:
    """Test all valid state transitions."""

    async def test_created_to_active(self, lifecycle, test_session):
        """CREATED → ACTIVE (session starts)."""
        result = await lifecycle.transition(
            test_session.id,
            SessionStatus.CREATED,
            SessionStatus.ACTIVE
        )
        assert result.status == SessionStatus.ACTIVE

    async def test_active_to_paused(self, lifecycle, session_manager):
        """ACTIVE → PAUSED (user pauses work)."""
        # Create session and transition to ACTIVE first
        session = await session_manager.create("/test/project", "test-thread")
        await session_manager.update(session.id, status=SessionStatus.ACTIVE)

        result = await lifecycle.transition(
            session.id,
            SessionStatus.ACTIVE,
            SessionStatus.PAUSED
        )
        assert result.status == SessionStatus.PAUSED

    async def test_paused_to_active(self, lifecycle, session_manager):
        """PAUSED → ACTIVE (user resumes)."""
        # Create session and transition to PAUSED
        session = await session_manager.create("/test/project", "test-thread")
        await session_manager.update(session.id, status=SessionStatus.PAUSED)

        result = await lifecycle.transition(
            session.id,
            SessionStatus.PAUSED,
            SessionStatus.ACTIVE
        )
        assert result.status == SessionStatus.ACTIVE

    async def test_active_to_terminated(self, lifecycle, session_manager):
        """ACTIVE → TERMINATED (session ends normally)."""
        # Create session and transition to ACTIVE
        session = await session_manager.create("/test/project", "test-thread")
        await session_manager.update(session.id, status=SessionStatus.ACTIVE)

        result = await lifecycle.transition(
            session.id,
            SessionStatus.ACTIVE,
            SessionStatus.TERMINATED
        )
        assert result.status == SessionStatus.TERMINATED

    async def test_paused_to_terminated(self, lifecycle, session_manager):
        """PAUSED → TERMINATED (session ends from pause)."""
        # Create session and transition to PAUSED
        session = await session_manager.create("/test/project", "test-thread")
        await session_manager.update(session.id, status=SessionStatus.PAUSED)

        result = await lifecycle.transition(
            session.id,
            SessionStatus.PAUSED,
            SessionStatus.TERMINATED
        )
        assert result.status == SessionStatus.TERMINATED

    async def test_created_to_terminated(self, lifecycle, test_session):
        """CREATED → TERMINATED (session cancelled before start)."""
        result = await lifecycle.transition(
            test_session.id,
            SessionStatus.CREATED,
            SessionStatus.TERMINATED
        )
        assert result.status == SessionStatus.TERMINATED


class TestInvalidTransitions:
    """Test all invalid state transitions that should raise errors."""

    async def test_terminated_to_active(self, lifecycle, session_manager):
        """TERMINATED → ACTIVE raises StateTransitionError (terminal state)."""
        # Create session and terminate it
        session = await session_manager.create("/test/project", "test-thread")
        await session_manager.update(session.id, status=SessionStatus.TERMINATED)

        with pytest.raises(StateTransitionError) as exc_info:
            await lifecycle.transition(
                session.id,
                SessionStatus.TERMINATED,
                SessionStatus.ACTIVE
            )
        assert "TERMINATED" in str(exc_info.value)

    async def test_created_to_paused(self, lifecycle, test_session):
        """CREATED → PAUSED raises StateTransitionError (can't pause before active)."""
        with pytest.raises(StateTransitionError) as exc_info:
            await lifecycle.transition(
                test_session.id,
                SessionStatus.CREATED,
                SessionStatus.PAUSED
            )
        assert "CREATED" in str(exc_info.value)
        assert "PAUSED" in str(exc_info.value)

    async def test_any_to_created(self, lifecycle, session_manager):
        """Any state → CREATED raises StateTransitionError (can't go back to initial)."""
        # Test from ACTIVE state
        session = await session_manager.create("/test/project", "test-thread")
        await session_manager.update(session.id, status=SessionStatus.ACTIVE)

        with pytest.raises(StateTransitionError) as exc_info:
            await lifecycle.transition(
                session.id,
                SessionStatus.ACTIVE,
                SessionStatus.CREATED
            )
        assert "CREATED" in str(exc_info.value)

    async def test_terminated_to_paused(self, lifecycle, session_manager):
        """TERMINATED → PAUSED raises StateTransitionError (terminal state)."""
        session = await session_manager.create("/test/project", "test-thread")
        await session_manager.update(session.id, status=SessionStatus.TERMINATED)

        with pytest.raises(StateTransitionError) as exc_info:
            await lifecycle.transition(
                session.id,
                SessionStatus.TERMINATED,
                SessionStatus.PAUSED
            )
        assert "TERMINATED" in str(exc_info.value)


class TestPersistence:
    """Test that transitions persist to database."""

    async def test_transition_persists_to_database(self, lifecycle, test_session, session_manager):
        """Transition should update database and be retrievable."""
        # Transition to ACTIVE
        await lifecycle.transition(
            test_session.id,
            SessionStatus.CREATED,
            SessionStatus.ACTIVE
        )

        # Retrieve fresh from database
        retrieved = await session_manager.get(test_session.id)
        assert retrieved.status == SessionStatus.ACTIVE

    async def test_failed_transition_does_not_persist(self, lifecycle, test_session, session_manager):
        """Invalid transition should not modify database."""
        # Attempt invalid transition
        with pytest.raises(StateTransitionError):
            await lifecycle.transition(
                test_session.id,
                SessionStatus.CREATED,
                SessionStatus.PAUSED
            )

        # Verify state unchanged in database
        retrieved = await session_manager.get(test_session.id)
        assert retrieved.status == SessionStatus.CREATED


class TestIdempotency:
    """Test idempotent transitions (same state)."""

    async def test_transition_to_same_state_is_allowed(self, lifecycle, session_manager):
        """Transitioning to same state (ACTIVE → ACTIVE) should be idempotent."""
        # Create and transition to ACTIVE
        session = await session_manager.create("/test/project", "test-thread")
        await session_manager.update(session.id, status=SessionStatus.ACTIVE)

        # Transition to same state should succeed
        result = await lifecycle.transition(
            session.id,
            SessionStatus.ACTIVE,
            SessionStatus.ACTIVE
        )
        assert result.status == SessionStatus.ACTIVE


class TestStatusMismatch:
    """Test handling of status mismatch between expected and actual."""

    async def test_from_status_mismatch_raises_error(self, lifecycle, session_manager):
        """If from_status doesn't match current DB status, raise StateTransitionError."""
        # Create session in CREATED state
        session = await session_manager.create("/test/project", "test-thread")

        # Try to transition from ACTIVE (but it's actually CREATED)
        with pytest.raises(StateTransitionError) as exc_info:
            await lifecycle.transition(
                session.id,
                SessionStatus.ACTIVE,  # Wrong current state
                SessionStatus.PAUSED
            )
        assert "mismatch" in str(exc_info.value).lower()
