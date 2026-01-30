# v1.0 Deployment Checklist

## Pre-Deployment Setup

### 1. Virtual Environment Setup
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# OR
.\venv\Scripts\activate   # Windows

# Verify Python version (should be 3.11+)
python --version
```

### 2. Install Dependencies
```bash
# Install production dependencies
pip install -e .

# Install development dependencies (for testing)
pip install -e ".[dev]"

# Verify installation
pip list | grep -E "websockets|aiohttp|pydantic|structlog|pytest"
```

### 3. Signal CLI Setup
```bash
# Start signal-cli-rest-api container
docker-compose up -d

# Verify container running
docker ps | grep signal-api

# Check logs
docker logs signal-api
```

### 4. Configuration
```bash
# Copy environment template
cp .env.example .env

# Edit .env with your configuration:
# - AUTHORIZED_NUMBER: Your phone number in E.164 format (+1234567890)
# - SIGNAL_API_URL: http://localhost:8080 (default)

# Verify configuration
cat .env
```

## Deployment Verification

### 5. Run Tests
```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=src --cov-report=term-missing

# Expected: 647+ tests passing, 93-94% coverage
```

### 6. Start Daemon
```bash
# Run daemon in foreground (for testing)
python -m src.daemon.service

# Verify daemon started:
# - Health check: curl http://localhost:8081/health
# - Should show "Signal bot daemon running"
```

### 7. Link Signal Account (First Time Only)

**Option A: Link via QR code (recommended)**
```bash
# 1. Generate QR code
curl -X POST "http://localhost:8080/v1/qrcodelink?device_name=claude-bot"

# 2. Open Signal on your phone
# 3. Go to Settings > Linked Devices > Link New Device
# 4. Scan the QR code from the API response
```

**Option B: Link via phone number**
```bash
# 1. Request verification code
curl -X POST "http://localhost:8080/v1/register/+YOUR_PHONE_NUMBER"

# 2. Enter code received via SMS
curl -X POST "http://localhost:8080/v1/register/+YOUR_PHONE_NUMBER/verify/VERIFICATION_CODE"
```

### 8. Test Basic Functionality

**Send a test message from your phone to the bot:**
```
/session help
```

**Expected response:**
```
Session Management Commands:

/session start [path] - Start new Claude session
/session list - Show all sessions
/session resume [id] - Resume existing session
/session stop [id] - Stop running session
/session help - Show this help

Current sessions: 0
```

**Test session creation:**
```
/session start /Users/yourusername/projects/test-project
```

**Expected:** Session created, you can now send Claude commands.

**Test Claude integration:**
```
Create a hello.py file that prints "Hello from mobile!"
```

**Expected:** Claude responds, creates file, requests approval for Write operation.

**Test approval workflow:**
```
/approve [approval-id]
```

**Expected:** File created, success notification.

## Production Deployment (macOS)

### 9. Install as System Service (launchd)
```bash
# Copy daemon plist to LaunchAgents
cp config/daemon.plist ~/Library/LaunchAgents/com.signal-claude-bot.daemon.plist

# Edit plist to set correct paths:
# - WorkingDirectory: /path/to/claude-signal-integration
# - ProgramArguments: /path/to/venv/bin/python -m src.daemon.service

# Load daemon
launchctl load ~/Library/LaunchAgents/com.signal-claude-bot.daemon.plist

# Verify running
launchctl list | grep signal-claude-bot

# Check logs
tail -f ~/Library/Logs/signal-claude-bot/daemon.log
```

### 10. Verify Auto-Restart
```bash
# Kill daemon process
pkill -f "src.daemon.service"

# Wait 5 seconds, verify it restarted
launchctl list | grep signal-claude-bot

# Should show running process with new PID
```

## Health Checks

### 11. Ongoing Monitoring
```bash
# Health endpoint
curl http://localhost:8081/health

# Daemon logs
tail -f ~/Library/Logs/signal-claude-bot/daemon.log

# Signal API logs
docker logs -f signal-api

# Session database
sqlite3 ~/Library/Application\ Support/signal-claude-bot/sessions.db "SELECT * FROM sessions;"

# Thread mappings
sqlite3 ~/Library/Application\ Support/signal-claude-bot/thread_mappings.db "SELECT * FROM mappings;"
```

## Troubleshooting

### Daemon won't start
- Check virtual environment activated
- Verify dependencies installed: `pip list`
- Check Python version: `python --version` (must be 3.11+)
- Review logs: `tail ~/Library/Logs/signal-claude-bot/daemon.log`

### Signal API connection fails
- Verify Docker container running: `docker ps`
- Check API endpoint: `curl http://localhost:8080/v1/health`
- Restart container: `docker-compose restart`

### WebSocket connection issues
- Check Signal account linked: Look for QR code or verification step
- Verify authorized number in `.env` matches linked account
- Check firewall/network settings

### Messages not received
- Verify phone number format: Must be E.164 (+1234567890)
- Check daemon logs for rate limiting warnings
- Ensure Signal app is connected to internet

### Approval workflow not working
- Verify ApprovalManager initialized in logs
- Check approval database: `ls ~/Library/Application\ Support/signal-claude-bot/`
- Review recent approvals: daemon logs show approval requests

### Session recovery fails
- Check session database integrity: `sqlite3 ~/Library/Application\ Support/signal-claude-bot/sessions.db ".schema"`
- Verify WAL mode enabled: Look for `sessions.db-wal` file
- Review crash recovery logs on daemon startup

## Rollback Procedure

If v1.0 has critical issues:
```bash
# Stop daemon
launchctl unload ~/Library/LaunchAgents/com.signal-claude-bot.daemon.plist

# Checkout previous stable version (if exists)
git log --oneline | grep -E "feat|chore" | head -10
git checkout [previous-stable-commit]

# Restart daemon
launchctl load ~/Library/LaunchAgents/com.signal-claude-bot.daemon.plist
```

## Success Criteria

v1.0 deployment is successful when:

- [ ] All 647+ tests pass
- [ ] Daemon starts without errors
- [ ] Health check responds (http://localhost:8081/health)
- [ ] Signal account linked (QR code or verification)
- [ ] Test message receives response
- [ ] Session creation works
- [ ] Claude command execution works
- [ ] Approval workflow works (destructive operations require approval)
- [ ] Session persistence works (daemon restart preserves sessions)
- [ ] Auto-restart works (daemon recovers after crash)
- [ ] Code display works (syntax highlighting, diffs)
- [ ] Notifications work (errors, approvals, completions)
- [ ] Multi-project support works (thread mappings persist)

## Post-Deployment

After successful deployment:

1. **Use it!** - Use the bot from your phone for real development work
2. **Gather feedback** - Note any UX issues, performance problems, or missing features
3. **Monitor logs** - Watch for errors, rate limiting, or unexpected behavior
4. **Document learnings** - Create issues for bugs or enhancement ideas
5. **Plan v1.1** - Use real-world experience to prioritize next milestone

---

**Version:** v1.0 MVP
**Coverage:** 93-94% (647+ tests)
**Quality:** Production-ready
**Support:** See GitHub issues for bug reports and feature requests
