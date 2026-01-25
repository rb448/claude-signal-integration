# Stack Research

**Domain:** Signal bot with Claude API integration (macOS desktop service)
**Researched:** 2026-01-25
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.11+ | Primary language | Superior ecosystem for Claude API (official SDK 0.76.0), excellent async support with asyncio, strong Signal bot libraries, simpler daemon management on macOS than Node.js |
| signal-cli | 0.13.23 | Signal protocol interface | Official Signal CLI tool maintained by AsamK, provides JSON-RPC and DBus interfaces, required by all Signal bot frameworks, actively maintained (Jan 24, 2026 release) |
| signal-cli-rest-api | 0.96 | Signal API wrapper | Production-ready Docker wrapper around signal-cli with REST + JSON-RPC modes, active maintenance (Dec 2, 2025), handles message receiving/sending, 91 releases with 53 contributors |
| anthropic | 0.76.0 | Claude API client | Official Anthropic Python SDK (Jan 13, 2026), supports streaming, async/await, tool calling, Python 3.9+ compatible |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| websockets | 16.0 | WebSocket client/server | Real-time bidirectional communication, built on asyncio, Python 3.10+ support (Jan 10, 2026 release) |
| aiohttp | 3.9+ | Async HTTP client | HTTP requests to signal-cli-rest-api, WebSocket fallback, better performance than httpx for high-concurrency |
| aiofiles | 25.1.0 | Async file I/O | Non-blocking file operations for code/log reading, Python 3.9+ (Oct 9, 2025 release) |
| pydantic | 2.12.5+ | Data validation | Type-safe message/session models, Rust-based core for performance, Python 3.9+ (Nov 26, 2025 release) |
| structlog | 25.5.0 | Structured logging | JSON logs for production debugging, key-value pairs, asyncio-aware (Oct 27, 2025 release) |
| python-dotenv | 1.0.1+ | Environment config | Secure API key management, .env file support, 12-factor app pattern (Oct 26, 2025 release) |
| redis | 5.2.0+ | Session persistence | Fast session state storage with TTL, pub/sub for multi-instance coordination (if needed later) |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| launchd | macOS service manager | Native macOS daemon manager, superior to Supervisor for single-user macOS services, use .plist in ~/Library/LaunchAgents |
| Docker Desktop | signal-cli-rest-api host | Required to run signal-cli-rest-api container, easier than managing Java dependencies directly |
| uv | Python package manager | Fast Rust-based package installer, lockfile support, replaces pip+venv |
| pytest + pytest-asyncio | Testing framework | Async test support, fixtures for mocking Signal/Claude APIs |
| ruff | Linter/formatter | Fast Rust-based linter, replaces black+flake8+isort, 10-100x faster |

## Installation

```bash
# System dependencies (macOS)
brew install signal-cli  # For CLI debugging, not runtime dependency
brew install --cask docker

# Python environment (using uv - recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv --python 3.11
source .venv/bin/activate

# Core dependencies
uv pip install anthropic==0.76.0 \
               aiohttp>=3.9 \
               websockets==16.0 \
               pydantic>=2.12.5 \
               structlog==25.5.0 \
               python-dotenv>=1.0.1 \
               aiofiles==25.1.0 \
               redis>=5.2.0

# Development dependencies
uv pip install pytest pytest-asyncio pytest-mock ruff

# Signal CLI REST API (Docker)
docker pull bbernhard/signal-cli-rest-api:latest
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Python 3.11+ | Node.js 20+ | If team has strong TypeScript preference or needs HTTP/2 client features; Node.js has native async but weaker Claude SDK ecosystem |
| signal-cli-rest-api (JSON-RPC mode) | Direct signal-cli DBus | If running on Linux server without Docker, DBus is more native; macOS DBus support is problematic |
| aiohttp | httpx | If you need sync/async hybrid API or HTTP/2 support; httpx is slower for high-concurrency scenarios but more flexible |
| Redis | SQLite with aiosqlite | If single-user with no scaling needs and want zero external dependencies; SQLite simpler but no TTL, slower for concurrent access |
| launchd | Supervisor | If cross-platform support needed or running on Linux; Supervisor adds Python dependency overhead on macOS |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| signal-cli-python-api (kbin76) | Unmaintained, no releases, requires custom signal-cli fork, lacks 2025 activity | signal-cli-rest-api with aiohttp client |
| signalbot PyPI package | Limited documentation, unclear maintenance status, less flexible than REST API approach | signal-cli-rest-api |
| Python 3.9 or earlier | Pydantic V2 incompatible with 3.14+, websockets requires 3.10+, missing modern async features | Python 3.11+ (tested through 3.14) |
| Direct Claude Code CLI subprocess | Fragile process management, difficult state tracking, no official Python API for CLI | Use Anthropic SDK with streaming for progress updates |
| PM2 for process management | Node.js tool, unnecessary on macOS with launchd, adds complexity | launchd native .plist configuration |
| signal-cli native mode | Requires GraalVM native-image compilation, macOS support issues, JSON-RPC mode faster anyway | signal-cli-rest-api Docker in JSON-RPC mode |

## Stack Patterns by Variant

**For single-user macOS desktop (your use case):**
- Use launchd for service management (no Supervisor overhead)
- Use SQLite with aiosqlite if you want zero-dependency persistence
- Use signal-cli-rest-api JSON-RPC mode in Docker
- Store session state in ~/.config/claude-signal-bot/

**For multi-user or Linux server deployment:**
- Use Supervisor or systemd for service management
- Use Redis for session persistence (better concurrency)
- Consider direct signal-cli DBus on Linux (no Docker dependency)
- Store logs in /var/log with logrotate

**For development/testing:**
- Use signal-cli-rest-api normal mode (easier debugging)
- Use in-memory session storage
- Mock Anthropic API responses
- Run without launchd (manual python script execution)

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| anthropic==0.76.0 | Python 3.9-3.14 | Requires httpx or aiohttp for async client |
| websockets==16.0 | Python 3.10-3.14 | Not compatible with 3.9; use 15.x for 3.9 |
| pydantic>=2.12.5 | Python 3.9-3.13 | V1 incompatible with Python 3.14+; use V2 |
| signal-cli==0.13.23 | openjdk@21 | Homebrew auto-installs; must update every 3 months per Signal protocol |
| signal-cli-rest-api==0.96 | signal-cli 0.13.x | Docker image bundles compatible signal-cli version |
| aiohttp>=3.9 | Python 3.8-3.14 | Anthropic SDK supports aiohttp for async operations |

## Architecture Decision: Python over Node.js

**Why Python wins for this project:**

1. **Claude API Integration (Critical):** Anthropic's official Python SDK (anthropic 0.76.0) is first-class with streaming, async, and tool calling support. Node.js SDK exists but Python is reference implementation.

2. **Signal Bot Ecosystem:** While both have signal-cli wrappers, Python has more mature async patterns (asyncio + aiohttp/websockets) that align with Signal's event-driven model.

3. **Async Performance (Sufficient):** Python with uvloop can match or exceed Node.js for I/O-bound tasks. For a single-user bot, concurrency is not a bottleneck. Python's asyncio is production-proven.

4. **macOS Service Integration:** Both work with launchd, but Python's simpler subprocess model and file I/O libraries (aiofiles) are better for desktop automation tasks.

5. **Development Velocity:** Python's REPL, dynamic typing for rapid prototyping, and simpler async syntax (async/await without callback hell) accelerate development.

**When Node.js would be better:**
- Team expertise is exclusively TypeScript/JavaScript
- Need to integrate with existing Node.js Claude Code extensions
- Require HTTP/2 client features (though not needed here)
- Plan to scale to thousands of concurrent users (unlikely for personal bot)

## Signal Interface Decision: REST API over Direct CLI

**Why signal-cli-rest-api (JSON-RPC mode):**

1. **Persistent Daemon:** JSON-RPC mode maintains long-running process, receives messages instantly via notifications (no polling), critical for real-time bot responsiveness.

2. **Dockerized Stability:** Bundles correct signal-cli + Java runtime versions, avoids Homebrew signal-cli update breakage, cryptographic state persists in volumes.

3. **REST + RPC Hybrid:** Sending messages via REST POST, receiving via JSON-RPC notifications over stdin/stdout or WebSocket, clean separation of concerns.

4. **Active Maintenance:** Version 0.96 (Dec 2025) shows ongoing updates, 53 contributors, comprehensive Swagger API documentation.

**Why not direct signal-cli:**
- **DBus on macOS:** macOS DBus support is problematic, requires dbus-daemon setup, launchd integration hacky
- **JSON-RPC stdin/out:** Requires managing signal-cli daemon process lifecycle, stdout parsing fragile
- **Java Dependencies:** Manual openjdk@21 + gradle setup, Homebrew updates can break compatibility

**Why not Python wrappers:**
- signal-cli-python-api: unmaintained, custom fork dependency
- signalbot PyPI: limited docs, unclear maintenance
- All wrappers add abstraction layer over signal-cli; REST API is official wrapper with best support

## Session Persistence Decision: Redis vs SQLite

**Default recommendation: SQLite with aiosqlite**

For single-user desktop bot:
- **Zero external dependencies** (no Redis server to manage)
- **File-based simplicity** (~/.config/claude-signal-bot/sessions.db)
- **aiosqlite** provides async API compatible with event loop
- **Sufficient performance** for <100 concurrent sessions
- **Backup-friendly** (single file to sync/restore)

**Upgrade to Redis when:**
- **Multi-instance deployment** (shared session state across processes)
- **TTL requirements** (auto-expire old sessions without cron job)
- **High write frequency** (>1000 updates/sec, unlikely for personal bot)
- **Pub/sub needed** (cross-process notifications)

**Implementation notes:**
- Use Pydantic models for session serialization (type-safe JSON)
- SQLite Write-Ahead Logging (WAL) mode for concurrent reads
- Index on session_id and last_accessed for fast queries
- Async context managers to ensure connection cleanup

## Sources

### Primary (HIGH confidence)
- [Anthropic Python SDK GitHub](https://github.com/anthropics/anthropic-sdk-python) — Current version, features, installation (Jan 13, 2026)
- [signal-cli Homebrew Formula](https://formulae.brew.sh/formula/signal-cli) — Version 0.13.23, dependencies
- [signal-cli Releases](https://github.com/AsamK/signal-cli/releases) — Latest releases with dates (Jan 24, 2026)
- [signal-cli-rest-api GitHub](https://github.com/bbernhard/signal-cli-rest-api) — Version 0.96, features, modes (Dec 2, 2025)
- [websockets PyPI](https://pypi.org/project/websockets/) — Version 16.0, Python 3.10+ requirement (Jan 10, 2026)
- [pydantic PyPI](https://pypi.org/project/pydantic/) — Version 2.12.5, Python 3.9+ (Nov 26, 2025)
- [structlog PyPI](https://pypi.org/project/structlog/) — Version 25.5.0 (Oct 27, 2025)
- [aiofiles PyPI](https://pypi.org/project/aiofiles/) — Version 25.1.0 (Oct 9, 2025)
- [python-dotenv PyPI](https://pypi.org/project/python-dotenv/) — Latest version (Oct 26, 2025)

### Secondary (MEDIUM confidence)
- [Bot Development Guide 2025](https://alexasteinbruck.medium.com/bot-development-for-messenger-platforms-whatsapp-telegram-and-signal-2025-guide-50635f49b8c6) — Signal bot landscape, community tools
- [Python vs Node.js 2025 comparisons](https://medium.com/israeli-tech-radar/so-you-think-python-is-slow-asyncio-vs-node-js-fe4c0083aee4) — Async performance with uvloop
- [HTTPX vs AIOHTTP comparison](https://oxylabs.io/blog/httpx-vs-requests-vs-aiohttp) — Performance benchmarks
- [Python Structured Logging Guide](https://betterstack.com/community/guides/logging/structlog/) — Best practices
- [macOS launchd documentation](https://support.apple.com/guide/terminal/script-management-with-launchd-apdc6c1077b-5d5d-4d35-9c19-60f2397b2369/mac) — Service management

### Tertiary (LOW confidence - context only)
- [Supervisor documentation](https://supervisord.org/) — Alternative process manager (cross-platform, not macOS-optimized)
- [Redis Session Management](https://redis.io/solutions/session-management/) — Alternative persistence approach

---
*Stack research for: Signal bot with Claude API integration (macOS desktop service)*
*Researched: 2026-01-25*
*Valid until: 2026-04-25 (signal-cli requires updates every ~3 months per Signal protocol)*
