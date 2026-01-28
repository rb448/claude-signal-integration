"""Integration tests for complete session lifecycles.

Tests session creation, state transitions, and concurrent sessions.
"""

import pytest

from src.session.manager import SessionStatus
from src.session.lifecycle import SessionLifecycle


@pytest.mark.asyncio
async def test_session_lifecycle_transitions(session_manager, temp_project_dir, authorized_number):
    """Test complete session lifecycle from creation through termination.

    Flow:
    1. Create session (CREATED)
    2. Start session (ACTIVE)
    3. Terminate session (TERMINATED)
    """
    # Create session
    session = await session_manager.create(
        project_path=str(temp_project_dir),
        thread_id=authorized_number,
    )

    assert session.status.name == "CREATED"

    # Transition to ACTIVE
    lifecycle = SessionLifecycle(session_manager)
    updated = await lifecycle.transition(
        session_id=session.id,
        from_status=SessionStatus.CREATED,
        to_status=SessionStatus.ACTIVE,
    )

    assert updated.status.name == "ACTIVE"

    # Transition to TERMINATED
    terminated = await lifecycle.transition(
        session_id=session.id,
        from_status=SessionStatus.ACTIVE,
        to_status=SessionStatus.TERMINATED,
    )

    assert terminated.status.name == "TERMINATED"


@pytest.mark.asyncio
async def test_concurrent_sessions(session_manager, temp_project_dir, authorized_number):
    """Test multiple concurrent sessions for different threads.

    Verifies:
    - Multiple sessions can exist simultaneously
    - Sessions are isolated by thread_id
    - Each session maintains independent state
    """
    # Create multiple sessions with different thread IDs
    thread1 = "+15551111111"
    thread2 = "+15552222222"
    thread3 = "+15553333333"

    session1 = await session_manager.create(
        project_path=str(temp_project_dir),
        thread_id=thread1,
    )

    session2 = await session_manager.create(
        project_path=str(temp_project_dir),
        thread_id=thread2,
    )

    session3 = await session_manager.create(
        project_path=str(temp_project_dir),
        thread_id=thread3,
    )

    # Verify all sessions exist
    all_sessions = await session_manager.list()
    assert len(all_sessions) >= 3

    session_ids = {s.id for s in all_sessions}
    assert session1.id in session_ids
    assert session2.id in session_ids
    assert session3.id in session_ids

    # Verify sessions have correct thread IDs
    assert session1.thread_id == thread1
    assert session2.thread_id == thread2
    assert session3.thread_id == thread3


@pytest.mark.asyncio
async def test_session_context_updates(session_manager, temp_project_dir, authorized_number):
    """Test session context storage and retrieval.

    Verifies:
    - Conversation history can be stored
    - Context persists across retrievals
    """
    # Create session
    session = await session_manager.create(
        project_path=str(temp_project_dir),
        thread_id=authorized_number,
    )

    # Update conversation history
    test_history = {
        "messages": ["Hello", "How are you?"],
        "metadata": {"version": "1.0"},
    }

    await session_manager.update_context(
        session_id=session.id,
        conversation_history=test_history,
    )

    # Retrieve and verify conversation history is stored under conversation_history key
    updated_session = await session_manager.get(session.id)
    assert "conversation_history" in updated_session.context
    assert updated_session.context["conversation_history"] == test_history


@pytest.mark.asyncio
async def test_activity_tracking(session_manager, temp_project_dir, authorized_number):
    """Test session activity tracking.

    Verifies:
    - Activities can be tracked in session context
    - Activity log maintains recent history
    """
    # Create session
    session = await session_manager.create(
        project_path=str(temp_project_dir),
        thread_id=authorized_number,
    )

    # Track some activities
    await session_manager.track_activity(
        session_id=session.id,
        activity_type="tool_call",
        details={"tool": "Read", "target": "README.md"},
    )

    await session_manager.track_activity(
        session_id=session.id,
        activity_type="command_executed",
        details={"command": "list files"},
    )

    # Verify activities stored in context
    updated_session = await session_manager.get(session.id)
    assert "activity_log" in updated_session.context
    assert len(updated_session.context["activity_log"]) >= 1
