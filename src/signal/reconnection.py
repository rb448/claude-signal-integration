"""Reconnection state machine for Signal API with exponential backoff.

Handles automatic reconnection after network drops with exponential backoff
to prevent connection storms (1s, 2s, 4s, 8s, ..., up to 60s max).
"""

from enum import Enum, auto


class ConnectionState(Enum):
    """Connection states for Signal API WebSocket."""

    CONNECTED = auto()
    DISCONNECTED = auto()
    RECONNECTING = auto()
    SYNCING = auto()


class ReconnectionManager:
    """Manages reconnection state and exponential backoff calculations.

    State machine:
    - CONNECTED → DISCONNECTED (network drop)
    - DISCONNECTED → RECONNECTING (start reconnect attempt)
    - RECONNECTING → CONNECTED (successful reconnect)
    - RECONNECTING → DISCONNECTED (failed attempt, will retry)
    - CONNECTED → SYNCING (reconnected, syncing session state)
    - SYNCING → CONNECTED (sync complete)

    Backoff formula: min(2^(attempt - 1), 60)
    - Attempt 1: 1s
    - Attempt 2: 2s
    - Attempt 3: 4s
    - Attempt 4: 8s
    - Attempt 5: 16s
    - Attempt 6: 32s
    - Attempt 7+: 60s (max)
    """

    # Valid state transitions (set of tuples)
    VALID_TRANSITIONS = {
        (ConnectionState.CONNECTED, ConnectionState.DISCONNECTED),
        (ConnectionState.DISCONNECTED, ConnectionState.RECONNECTING),
        (ConnectionState.RECONNECTING, ConnectionState.CONNECTED),
        (ConnectionState.RECONNECTING, ConnectionState.DISCONNECTED),
        (ConnectionState.CONNECTED, ConnectionState.SYNCING),
        (ConnectionState.SYNCING, ConnectionState.CONNECTED),
    }

    def __init__(self):
        """Initialize reconnection manager in CONNECTED state."""
        self.state = ConnectionState.CONNECTED
        self.attempt_count = 0

    def transition(self, new_state: ConnectionState) -> bool:
        """Attempt to transition to a new connection state.

        Args:
            new_state: Target connection state

        Returns:
            True if transition is valid and completed, False if invalid
        """
        if (self.state, new_state) in self.VALID_TRANSITIONS:
            self.state = new_state
            if new_state == ConnectionState.RECONNECTING:
                self.attempt_count += 1
            elif new_state == ConnectionState.CONNECTED:
                self.attempt_count = 0  # Reset on successful connection
            return True
        return False

    def calculate_backoff(self) -> float:
        """Calculate exponential backoff delay in seconds.

        Formula: min(2^(attempt_count - 1), MAX_BACKOFF)
        - Attempt 1: 1s
        - Attempt 2: 2s
        - Attempt 3: 4s
        - Attempt 4: 8s
        - Attempt 5: 16s
        - Attempt 6: 32s
        - Attempt 7+: 60s (max)

        Returns:
            Backoff delay in seconds
        """
        MAX_BACKOFF = 60.0
        if self.attempt_count == 0:
            return 1.0  # First attempt (after reset)

        # 2^(attempt - 1) with cap at MAX_BACKOFF
        delay = 2 ** (self.attempt_count - 1)
        return min(delay, MAX_BACKOFF)
