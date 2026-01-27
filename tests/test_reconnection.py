"""Tests for Signal API reconnection logic with exponential backoff.

RED phase: These tests will fail until ConnectionState and ReconnectionManager are implemented.
"""

import pytest
from src.signal.reconnection import ConnectionState, ReconnectionManager


class TestConnectionStateEnum:
    """Test ConnectionState enum values and distinctness."""

    def test_connection_state_enum(self):
        """Verify ConnectionState has all required values and they are distinct."""
        # Assert all states exist
        assert hasattr(ConnectionState, 'CONNECTED')
        assert hasattr(ConnectionState, 'DISCONNECTED')
        assert hasattr(ConnectionState, 'RECONNECTING')
        assert hasattr(ConnectionState, 'SYNCING')

        # Verify all values are distinct
        states = [
            ConnectionState.CONNECTED,
            ConnectionState.DISCONNECTED,
            ConnectionState.RECONNECTING,
            ConnectionState.SYNCING,
        ]
        assert len(states) == len(set(states)), "ConnectionState values must be unique"


class TestStateTransitions:
    """Test state machine transition validation."""

    def test_valid_state_transitions(self):
        """Verify all valid state transitions are allowed."""
        manager = ReconnectionManager()

        # Start in CONNECTED state
        assert manager.state == ConnectionState.CONNECTED

        # CONNECTED → DISCONNECTED (network drop)
        assert manager.transition(ConnectionState.DISCONNECTED) is True
        assert manager.state == ConnectionState.DISCONNECTED

        # DISCONNECTED → RECONNECTING (start reconnect attempt)
        assert manager.transition(ConnectionState.RECONNECTING) is True
        assert manager.state == ConnectionState.RECONNECTING

        # RECONNECTING → CONNECTED (successful reconnect)
        assert manager.transition(ConnectionState.CONNECTED) is True
        assert manager.state == ConnectionState.CONNECTED

        # CONNECTED → DISCONNECTED → RECONNECTING → DISCONNECTED (failed attempt)
        manager.transition(ConnectionState.DISCONNECTED)
        manager.transition(ConnectionState.RECONNECTING)
        assert manager.transition(ConnectionState.DISCONNECTED) is True
        assert manager.state == ConnectionState.DISCONNECTED

        # CONNECTED → SYNCING (reconnected, syncing state)
        manager.state = ConnectionState.CONNECTED  # Reset to CONNECTED
        assert manager.transition(ConnectionState.SYNCING) is True
        assert manager.state == ConnectionState.SYNCING

        # SYNCING → CONNECTED (sync complete)
        assert manager.transition(ConnectionState.CONNECTED) is True
        assert manager.state == ConnectionState.CONNECTED

    def test_invalid_state_transitions(self):
        """Verify invalid state transitions are rejected."""
        manager = ReconnectionManager()

        # DISCONNECTED → SYNCING (can't sync while disconnected)
        manager.state = ConnectionState.DISCONNECTED
        assert manager.transition(ConnectionState.SYNCING) is False
        assert manager.state == ConnectionState.DISCONNECTED  # State unchanged

        # RECONNECTING → SYNCING (must connect first)
        manager.state = ConnectionState.RECONNECTING
        assert manager.transition(ConnectionState.SYNCING) is False
        assert manager.state == ConnectionState.RECONNECTING  # State unchanged


class TestExponentialBackoff:
    """Test exponential backoff calculation."""

    def test_exponential_backoff_calculation(self):
        """Verify backoff delays follow exponential pattern with 60s cap."""
        manager = ReconnectionManager()

        # Simulate multiple reconnection attempts
        manager.state = ConnectionState.DISCONNECTED

        # Attempt 1: 1 second
        manager.transition(ConnectionState.RECONNECTING)
        assert manager.calculate_backoff() == 1.0

        # Attempt 2: 2 seconds
        manager.transition(ConnectionState.DISCONNECTED)
        manager.transition(ConnectionState.RECONNECTING)
        assert manager.calculate_backoff() == 2.0

        # Attempt 3: 4 seconds
        manager.transition(ConnectionState.DISCONNECTED)
        manager.transition(ConnectionState.RECONNECTING)
        assert manager.calculate_backoff() == 4.0

        # Attempt 4: 8 seconds
        manager.transition(ConnectionState.DISCONNECTED)
        manager.transition(ConnectionState.RECONNECTING)
        assert manager.calculate_backoff() == 8.0

        # Attempt 5: 16 seconds
        manager.transition(ConnectionState.DISCONNECTED)
        manager.transition(ConnectionState.RECONNECTING)
        assert manager.calculate_backoff() == 16.0

        # Attempt 6: 32 seconds
        manager.transition(ConnectionState.DISCONNECTED)
        manager.transition(ConnectionState.RECONNECTING)
        assert manager.calculate_backoff() == 32.0

        # Attempt 7: 60 seconds (capped at max)
        manager.transition(ConnectionState.DISCONNECTED)
        manager.transition(ConnectionState.RECONNECTING)
        assert manager.calculate_backoff() == 60.0

        # Attempt 8: 60 seconds (still capped)
        manager.transition(ConnectionState.DISCONNECTED)
        manager.transition(ConnectionState.RECONNECTING)
        assert manager.calculate_backoff() == 60.0

    def test_backoff_resets_on_successful_connection(self):
        """Verify backoff resets to 1s after successful reconnection."""
        manager = ReconnectionManager()

        # Simulate 5 failed attempts
        manager.state = ConnectionState.DISCONNECTED
        for _ in range(5):
            manager.transition(ConnectionState.RECONNECTING)
            manager.transition(ConnectionState.DISCONNECTED)

        # Verify we're at attempt 5 (16 second backoff)
        assert manager.attempt_count == 5

        # Successful connection resets attempt count
        manager.transition(ConnectionState.RECONNECTING)
        manager.transition(ConnectionState.CONNECTED)
        assert manager.attempt_count == 0

        # Next reconnection attempt should be 1 second
        manager.transition(ConnectionState.DISCONNECTED)
        manager.transition(ConnectionState.RECONNECTING)
        assert manager.calculate_backoff() == 1.0
