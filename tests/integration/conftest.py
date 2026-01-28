"""Integration test fixtures for Signal ↔ Claude Code flows.

Provides:
- Mocked Signal API WebSocket clients
- Temporary test databases
- Realistic Signal/Claude message payloads
- Initialized daemon components for testing
"""

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from src.approval.detector import OperationDetector
from src.approval.manager import ApprovalManager
from src.approval.workflow import ApprovalWorkflow
from src.claude.bridge import CLIBridge
from src.claude.orchestrator import ClaudeOrchestrator
from src.claude.parser import OutputParser, StreamingParser
from src.claude.responder import SignalResponder
from src.session.lifecycle import SessionLifecycle
from src.session.manager import SessionManager


@pytest_asyncio.fixture
async def signal_client_mock():
    """Mock signal-cli-rest-api WebSocket client.

    Provides async send_message() and receive_messages() methods
    that can be configured per test for realistic Signal API simulation.
    """
    mock = AsyncMock()
    mock.send_message = AsyncMock()
    mock.receive_messages = AsyncMock()
    mock.connect = AsyncMock()
    mock.disconnect = AsyncMock()

    # Default behavior: receive_messages returns empty list
    mock.receive_messages.return_value = []

    return mock


@pytest_asyncio.fixture
async def test_db(tmp_path: Path) -> AsyncGenerator[Path, None]:
    """Temporary SQLite database for testing.

    Creates isolated database file that's cleaned up after test.
    Returns path to database file.
    """
    db_path = tmp_path / "test_sessions.db"

    # Initialize SessionManager to create schema
    manager = SessionManager(db_path=str(db_path))
    await manager.initialize()

    yield db_path

    # Cleanup
    if db_path.exists():
        db_path.unlink()


@pytest_asyncio.fixture
async def temp_project_dir(tmp_path: Path) -> Path:
    """Temporary directory for test projects.

    Creates directory structure:
    /tmp/test_project_XXX/
        README.md
        src/
            main.py
    """
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()

    # Create some sample files
    (project_dir / "README.md").write_text("# Test Project\n")
    src_dir = project_dir / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text('def main():\n    print("Hello")\n')

    return project_dir


@pytest.fixture
def sample_signal_messages() -> Dict[str, Any]:
    """Realistic Signal message payloads.

    Returns dict with common message types:
    - session_start: User starting a session
    - session_stop: User stopping a session
    - claude_command: User sending command to Claude
    - approval_response: User approving a request
    """
    return {
        "session_start": {
            "envelope": {
                "source": "+15551234567",
                "timestamp": 1234567890000,
                "dataMessage": {
                    "timestamp": 1234567890000,
                    "message": "/session start /tmp/test_project",
                    "groupInfo": None,
                },
            },
            "account": "+15559876543",
        },
        "session_stop": {
            "envelope": {
                "source": "+15551234567",
                "timestamp": 1234567891000,
                "dataMessage": {
                    "timestamp": 1234567891000,
                    "message": "/session stop abc123de",
                    "groupInfo": None,
                },
            },
            "account": "+15559876543",
        },
        "claude_command": {
            "envelope": {
                "source": "+15551234567",
                "timestamp": 1234567892000,
                "dataMessage": {
                    "timestamp": 1234567892000,
                    "message": "read the README file",
                    "groupInfo": None,
                },
            },
            "account": "+15559876543",
        },
        "approval_response": {
            "envelope": {
                "source": "+15551234567",
                "timestamp": 1234567893000,
                "dataMessage": {
                    "timestamp": 1234567893000,
                    "message": "/approve abc123de",
                    "groupInfo": None,
                },
            },
            "account": "+15559876543",
        },
    }


@pytest.fixture
def sample_claude_output() -> List[str]:
    """Sample Claude CLI streaming output chunks.

    Returns list of output lines simulating Claude CLI stdout:
    - Tool calls
    - Thinking tokens
    - Final response
    """
    return [
        "Tool: Read",
        "Target: README.md",
        "Status: Reading file...",
        "",
        "# Test Project",
        "",
        "This is a test project for integration testing.",
        "",
        "Tool: Complete",
        "Result: Successfully read README.md (3 lines)",
        "",
        "The README file contains a basic project description.",
    ]


@pytest_asyncio.fixture
async def session_manager(test_db: Path) -> AsyncGenerator[SessionManager, None]:
    """Initialized SessionManager with test database.

    Provides clean session manager for each test with isolated database.
    """
    manager = SessionManager(db_path=str(test_db))
    await manager.initialize()

    yield manager

    # Cleanup handled by test_db fixture


@pytest_asyncio.fixture
async def approval_components() -> Dict[str, Any]:
    """Initialized approval system components.

    Returns dict with:
    - detector: OperationDetector
    - manager: ApprovalManager
    - workflow: ApprovalWorkflow

    All configured for testing with mocked Signal notifications.
    """
    detector = OperationDetector()
    manager = ApprovalManager()

    # Mock Signal notification function
    async def mock_notify(thread_id: str, message: str):
        """Mock notification that stores sent messages for verification."""
        if not hasattr(mock_notify, "sent_messages"):
            mock_notify.sent_messages = []
        mock_notify.sent_messages.append({"thread_id": thread_id, "message": message})

    workflow = ApprovalWorkflow(
        detector=detector,
        manager=manager,
        notify_func=mock_notify,
    )

    return {
        "detector": detector,
        "manager": manager,
        "workflow": workflow,
        "notify_func": mock_notify,
    }


@pytest_asyncio.fixture
async def orchestrator_components() -> Dict[str, Any]:
    """Initialized orchestrator components.

    Returns dict with:
    - parser: OutputParser
    - responder: SignalResponder
    - orchestrator: ClaudeOrchestrator

    Configured with mocked Signal send function.
    """
    parser = OutputParser()

    # Mock Signal send function
    async def mock_send(thread_id: str, message: str):
        """Mock send that stores sent messages for verification."""
        if not hasattr(mock_send, "sent_messages"):
            mock_send.sent_messages = []
        mock_send.sent_messages.append({"thread_id": thread_id, "message": message})

    responder = SignalResponder(send_func=mock_send)

    orchestrator = ClaudeOrchestrator(
        parser=parser,
        responder=responder,
    )

    return {
        "parser": parser,
        "responder": responder,
        "orchestrator": orchestrator,
        "send_func": mock_send,
    }


@pytest_asyncio.fixture
async def mock_claude_process():
    """Mock ClaudeProcess for testing without spawning real subprocess.

    Provides:
    - start() method that simulates successful process start
    - get_bridge() method that returns mock CLIBridge
    - stop() method that simulates clean shutdown
    """
    mock = AsyncMock()

    # Mock bridge
    mock_bridge = AsyncMock(spec=CLIBridge)
    mock_bridge.send_command = AsyncMock()
    mock_bridge.read_response = AsyncMock()

    mock.start = AsyncMock()
    mock.get_bridge = MagicMock(return_value=mock_bridge)
    mock.stop = AsyncMock()
    mock.is_running = MagicMock(return_value=True)

    return mock


@pytest.fixture
def authorized_number() -> str:
    """Authorized phone number for testing."""
    return "+15551234567"


@pytest.fixture
def bot_number() -> str:
    """Bot's phone number for testing."""
    return "+15559876543"
