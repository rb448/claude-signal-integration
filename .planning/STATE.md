# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-01-25)

**Core value:** Enable complete Claude Code functionality from mobile without requiring GitHub repos - users can continue development work with local directories while away from their desk.
**Current focus:** Phase 3 — Claude Code Integration

## Current Position

Phase: 3 of 10 (Claude Code Integration)
Plan: 2 of 3 in phase (completed)
Status: In progress
Last activity: 2026-01-26 — Completed 03-02-PLAN.md (Output Parser)

Progress: ████████░░ 67% (Phase 3: 2/3 plans complete)

## Performance Metrics

**Velocity:**
- Total plans completed: 13
- Average duration: 4.0 min
- Total execution time: 0.9 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 - Core Infrastructure | 4/4 | 38min | 9.5min |
| 2 - Session Management | 7/7 | 19min | 2.7min |
| 3 - Claude Integration | 2/3 | 5min | 2.5min |

**Recent Trend:**
- Last 5 plans: 6min (02-05), 1min (02-06), 2min (02-07), 2min (03-01), 3min (03-02)
- Trend: Excellent velocity maintained - Phase 3 averaging 2.5min/plan

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

| Decision | Plan | Rationale | Impact |
|----------|------|-----------|--------|
| Used signal-cli-rest-api:0.96 in JSON-RPC mode | 01-01 | Persistent daemon for instant message receipt vs polling | Real-time message delivery |
| Python 3.11+ as primary language | 01-01 | Superior asyncio and Claude SDK integration | Better async patterns, official SDK support |
| websockets library over aiohttp WebSocket | 01-01 | Dedicated WebSocket library with cleaner async API | Simpler implementation, better error handling |
| Virtual environment for dependency isolation | 01-01 | macOS system Python restrictions, safer isolation | No conflicts with system packages |
| Conservative 30 messages/minute rate limit | 01-02 | Signal API limits unknown, defensive approach from PITFALLS research | Prevents 413 rate limit errors |
| Token bucket with 5-message burst allowance | 01-02 | Natural conversation flow requires instant responses | Responsive bot while preventing sustained bursts |
| Exponential backoff with 60s cooldown | 01-02 | PITFALLS research shows backoff prevents thundering herd | Graceful degradation under load, auto-recovery |
| Queue overflow drops oldest messages | 01-02 | Alternative (blocking) could freeze bot | Prevents memory exhaustion, keeps recent commands |
| Run daemon as Python module (-m) | 01-03 | Direct script execution breaks relative imports | Enables proper package imports, daemon starts correctly |
| Use launchd for process management | 01-03 | Native macOS solution, no additional dependencies | Daemon auto-starts and auto-restarts, logs to ~/Library/Logs |
| E.164 phone exact matching for auth | 01-03 | Security requires precise authorization | Only exact authorized number processes commands |
| Health check on port 8081 | 01-03 | Separate from Signal API for independent monitoring | Can verify daemon status even if Signal offline |
| Concurrent tasks with asyncio.gather() | 01-04 | Both receive_task and queue_task need graceful cancellation | Clean shutdown of all daemon tasks |
| Inline receive_loop() in run() method | 01-04 | 11-line function tightly coupled to daemon state | Simpler code structure, all coordination in one place |
| SQLite with WAL mode for sessions | 02-01 | Concurrent access safety needed for async operations | Multiple reads possible during writes, crash-safe |
| Session context as JSON blob | 02-01 | Context structure will evolve with conversation features | No schema migrations needed, flexible storage |
| UUID4 for session IDs | 02-01 | Prevents collisions in concurrent session creation | Globally unique IDs, no coordination required |
| UTC-aware datetime.now(UTC) | 02-01 | datetime.utcnow() deprecated in Python 3.12+ | Future-proof timestamps, zero warnings |
| Set-based VALID_TRANSITIONS | 02-02 | O(1) lookup performance for transition validation | Fast state machine checks, explicit rules |
| Optimistic transition validation | 02-02 | Check validity before database update | Fail fast, no rollback needed, better performance |
| Status mismatch detection | 02-02 | Verify expected state matches actual before transition | Prevents race conditions and stale-state transitions |
| Idempotent transitions allowed | 02-02 | Same-state transitions (ACTIVE→ACTIVE) valid | Enables safe retry logic without special-casing |
| asyncio.create_subprocess_exec for subprocesses | 02-03 | Prevents shell injection by separating command and args | Safe subprocess spawning, no injection vulnerabilities |
| Graceful shutdown: SIGTERM → SIGKILL | 02-03 | Give processes time to clean up (5s) but force kill if hung | Reliable cleanup, no zombie processes |
| Working directory isolation via cwd parameter | 02-03 | Each session operates in own project without cross-contamination | Concurrent sessions fully isolated |
| Crash detection via ACTIVE sessions | 02-04 | ACTIVE status means daemon crashed before clean shutdown | Simple, reliable detection without OS process tracking |
| Use SessionLifecycle.transition() for recovery | 02-04 | Preserves state machine validation rules | Maintains state integrity, two DB updates acceptable |
| recovered_at timestamp in context | 02-04 | Provides audit trail for crash recovery events | Enables user notification and debugging |
| Idempotent recovery design | 02-04 | Safe to run on every daemon startup | No risk of double-recovery or corrupted state |
| Factory function for ClaudeProcess creation | 02-05 | Enables easy mocking in tests without complex DI | Clean test isolation, processes mocked per session |
| Truncate session IDs to 8 chars in list | 02-05 | Full UUIDs (36 chars) don't fit mobile screens | User-friendly display, 8 chars sufficient |
| Path validation before session creation | 02-05 | Fail fast if project directory doesn't exist | Clear error messages, prevents invalid sessions |
| Crash recovery runs before Signal connect | 02-05 | Sessions recovered before processing messages | Consistent state on startup |
| Process lifecycle tracked in dict | 02-05 | Need to track running processes for cleanup | Prevents zombie processes on stop |
| Best-effort messaging with exception handling | 02-06 | Send failures logged but don't crash daemon | Messaging important for UX but daemon availability critical |
| Truncate session IDs to 8 chars in notifications | 02-06 | Matches /session list format, mobile-friendly | Consistent user experience across all session displays |
| Conversation history parameter added but not used | 02-07 | Phase 2 focused on session persistence, not Claude CLI integration | Parameter wired through system, restoration deferred to Phase 3 |
| Conversation history stored in session.context | 02-07 | session.context JSON blob already exists, no schema changes needed | Phase 3 can call update_context() without refactoring session layer |
| Dataclasses with __post_init__ for type assignment | 03-02 | Each ParsedOutput subclass sets its type in __post_init__ | Clean API: ToolCall(tool="Read", target="file.py") without passing type |
| Regex patterns as class constants | 03-02 | TOOL_CALL_PATTERN, BASH_PATTERN, ERROR_PATTERN compiled once | Performance: patterns compiled once, reused for all parse() calls |
| Generator-based feed() for streaming | 03-02 | Yields ParsedOutput as complete lines arrive | Caller can process results incrementally without waiting for stream end |
| Buffer incomplete lines in StreamingParser | 03-02 | Handles chunks that break mid-line | Enables realistic streaming where network chunks don't align with line boundaries |

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

## Session Continuity

Last session: 2026-01-26
Stopped at: Completed 03-02-PLAN.md (Output Parser) - 2/3 plans in Phase 3 complete
Resume file: None
