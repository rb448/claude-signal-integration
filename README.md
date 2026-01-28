# Claude Code Signal Integration

![Tests](https://github.com/USER/REPO/workflows/Tests/badge.svg)
![Coverage](https://img.shields.io/codecov/c/github/USER/REPO)

This is the **Signal bot integration** project for mobile access to Claude Code sessions.

**Not** the CryptoTradingApp - that's in the parent directory.

## Project Documentation

- Planning files: `.planning-signal/`
- Project spec: `.planning-signal/PROJECT.md`
- Roadmap: `.planning-signal/ROADMAP.md`
- Requirements: `.planning-signal/REQUIREMENTS.md`
- Current state: `.planning-signal/STATE.md`

## Quick Start

See `.planning-signal/ROADMAP.md` for phased development plan.

## Development

### Running Tests

Run all tests:
```bash
pytest -v
```

Run tests with coverage:
```bash
pytest --cov=src --cov-report=term-missing
```

Run specific test suites:
```bash
pytest -m integration          # Integration tests only
pytest -m "not slow"           # Fast tests only (skip load/chaos tests)
pytest tests/test_signal_client.py  # Specific test file
```

Run tests in parallel:
```bash
pytest -n auto
```

### Coverage Requirements

- **Minimum coverage:** 80% (enforced by CI)
- **Target coverage:** >85% for critical modules (signal, session, claude)
- **Coverage reports:** Automatically generated on PRs

View local coverage report:
```bash
pytest --cov=src --cov-report=html
open htmlcov/index.html
```

### CI/CD

All pull requests must pass:
- ✅ **Test workflow:** All tests pass on Python 3.11 and 3.12
- ✅ **Coverage workflow:** Coverage remains at or above 80%

Test workflows run automatically on:
- Every pull request
- Every push to main branch

See [tests/README.md](tests/README.md) for detailed test documentation.

### Test Organization

Tests are organized by marker:
- **Unit tests** (default): Fast, isolated tests
- **Integration tests** (`@pytest.mark.integration`): Multi-component tests
- **Load tests** (`@pytest.mark.load`): Performance and stress tests
- **Chaos tests** (`@pytest.mark.chaos`): Resilience tests with failure injection

See [tests/README.md](tests/README.md) for complete testing guide.

---
*To avoid confusion: This subdirectory is for the Signal bot. The main Claude directory contains the CryptoTradingApp.*
