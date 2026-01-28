# Test Suite Documentation

## Test Organization

This project uses pytest with multiple test markers for organizing and running different types of tests.

## Test Markers

### Unit Tests (default)
Fast, isolated tests that don't require external dependencies.

```bash
pytest                    # Run all tests (including unit tests)
pytest tests/             # Explicitly run from tests directory
```

### Integration Tests
Tests that verify interactions between multiple components.

```bash
pytest -m integration     # Run only integration tests
pytest -m "not integration"  # Skip integration tests
```

Mark integration tests with:
```python
@pytest.mark.integration
def test_signal_client_integration():
    ...
```

### Load Tests
Performance and stress tests that verify system behavior under high load.

```bash
pytest -m load           # Run only load tests
pytest -m "not slow"     # Skip slow tests (load + chaos)
```

Mark load tests with:
```python
@pytest.mark.load
@pytest.mark.slow
def test_high_message_volume():
    ...
```

### Chaos Tests
Tests that verify resilience by injecting failures and network issues.

```bash
pytest -m chaos          # Run only chaos tests
```

Mark chaos tests with:
```python
@pytest.mark.chaos
@pytest.mark.slow
def test_network_partition_recovery():
    ...
```

### Slow Tests
Any test that takes >5 seconds to run should be marked as slow.

```bash
pytest -m "not slow"     # Skip all slow tests (fast feedback)
```

## Running Tests Locally

### Quick feedback (unit tests only)
```bash
pytest -m "not slow" -n auto
```

### With coverage
```bash
pytest --cov=src --cov-report=term-missing
```

### Specific test file
```bash
pytest tests/test_signal_client.py -v
```

### Run until first failure
```bash
pytest -x
```

## CI/CD Test Execution

### GitHub Actions - Test Workflow
Runs on every PR and push to main:
- Executes all unit and integration tests
- Tests on Python 3.11 and 3.12
- Parallel execution with pytest-xdist
- Must pass for PR to merge

### GitHub Actions - Coverage Workflow
Runs on every PR:
- Generates coverage report
- Enforces 80% minimum coverage
- Comments coverage report on PR
- Uploads HTML coverage report as artifact

## Writing Tests

### Test Structure
```python
import pytest
from src.signal.client import SignalClient

@pytest.mark.asyncio
async def test_signal_message_send():
    """Test that messages are sent correctly."""
    client = SignalClient(recipient="+1234567890")
    await client.send_message("test message")
    # assertions...
```

### Using Fixtures
Common fixtures are defined in `conftest.py`:
- `signal_client`: Mocked SignalClient instance
- `session_manager`: SessionManager with temporary database
- `claude_process`: Mocked ClaudeProcess instance

### Async Tests
All async tests automatically use `asyncio_mode = auto` from pytest.ini:
```python
@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
    assert result == expected
```

## Coverage Guidelines

- Aim for >80% overall coverage (enforced by CI)
- Critical modules (signal, session, claude) should have >90% coverage
- Focus on behavior coverage, not just line coverage
- Test edge cases and error conditions

## Test Best Practices

1. **Isolation**: Tests should not depend on each other
2. **Speed**: Keep unit tests fast (<100ms each)
3. **Clarity**: Use descriptive test names and clear assertions
4. **Mocking**: Mock external dependencies (Signal API, Claude CLI)
5. **Cleanup**: Use fixtures and context managers for resource cleanup
6. **Markers**: Apply appropriate markers for test categorization
