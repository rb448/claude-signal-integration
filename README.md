# Claude Code Signal Integration

![Version](https://img.shields.io/badge/version-v1.0-blue)
![Coverage](https://img.shields.io/badge/coverage-93--94%25-brightgreen)
![Tests](https://img.shields.io/badge/tests-647%2B%20passing-brightgreen)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)

**Complete mobile access to Claude Code via Signal.** Control development sessions, review code changes, manage approvals, and work across multiple projects—all from your phone using Signal's encrypted messaging.

## ✨ v1.0 Features

- 🤖 **Signal Bot** - Real-time messaging with WebSocket, rate limiting, phone auth
- 💾 **Session Management** - SQLite-persisted sessions with crash recovery
- 🔄 **Claude Integration** - Bidirectional CLI streaming with mobile-optimized display
- 📁 **Multi-Project** - Concurrent work across projects via thread mapping
- ✅ **Approval System** - Gate destructive operations, emergency fix mode
- 🔌 **Connection Resilience** - Auto-reconnect, message buffering, catch-up summaries
- 🔔 **Notifications** - Configurable urgency tiers per thread
- ⚙️ **Advanced** - Custom commands, emergency mode auto-approval
- 🧪 **Quality** - 93-94% test coverage, 647+ tests, comprehensive CI/CD

## 🚀 Quick Start

### 1. Verify Deployment Readiness
```bash
./verify-deployment.sh
```

### 2. Install Dependencies
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e ".[dev]"
```

### 3. Start Signal API
```bash
docker-compose up -d
```

### 4. Configure & Run
```bash
# Set your phone number in .env
echo "AUTHORIZED_NUMBER=+1234567890" > .env

# Run tests
pytest --cov=src

# Start daemon
python -m src.daemon.service
```

### 5. Link Signal Account
Send a QR code link request from Signal on your phone, then test:
```
/session help
```

**Full deployment guide:** See [DEPLOYMENT.md](DEPLOYMENT.md)

## 📖 Documentation

- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Complete deployment guide with troubleshooting
- **[.planning/MILESTONES.md](.planning/MILESTONES.md)** - v1.0 release notes and stats
- **[.planning/PROJECT.md](.planning/PROJECT.md)** - Project vision and requirements
- **[.planning/milestones/](.planning/milestones/)** - Archived roadmaps and requirements

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
