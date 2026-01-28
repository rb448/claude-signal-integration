# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-01-25)

**Core value:** Enable complete Claude Code functionality from mobile without requiring GitHub repos - users can continue development work with local directories while away from their desk.
**Current focus:** Phase 9 — Advanced Features

## Current Position

Phase: 9 of 10 (Advanced Features & Emergency Mode)
Plan: Not started
Status: Planning needed
Last activity: 2026-01-28 — Completed Phase 8 (Notification System)

Progress: ████████████████ 80% (8 phases complete, 2 remaining)

## Performance Metrics

**Velocity:**
- Total plans completed: 42
- Average duration: 7.4 min
- Total execution time: 5.42 hours (325 min)

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 - Core Infrastructure | 4/4 | 38min | 9.5min |
| 2 - Session Management | 7/7 | 19min | 2.7min |
| 3 - Claude Integration | 5/5 | 15.5min | 3.1min |
| 4 - Multi-Project Support | 5/5 | 21.6min | 4.3min |
| 5 - Permission & Approval | 5/5 | 32.8min | 6.6min |
| 6 - Code Display & Mobile UX | 6/6 | 73min | 12.2min |
| 7 - Connection Resilience | 5/5 | 108min | 21.6min |
| 8 - Notification System | 5/5 | 17min | 3.4min |

**Recent Trend:**
- Last 5 plans: 3min (08-01), 3min (08-02), 4min (08-03), 4min (08-04), 3min (08-05)
- Trend: Phase 8 complete - efficient execution (all plans <5min, strong TDD foundation)
- Trend: Phase 8 complete - all 5 plans executed in 3-4min (consistent integration/wiring work)

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
| Remote wins by default in session state sync | 07-04 | API is source of truth when no timestamps present | Ensures remote state takes precedence, prevents stale local state |
| Local wins in session state sync when timestamp newer | 07-04 | Preserves user's most recent work during disconnection | Prevents overwriting recent local changes with older remote state |
| SYNCING state used during reconnection | 07-04 | Explicit state for session synchronization phase | State transitions: DISCONNECTED → RECONNECTING → SYNCING → CONNECTED |
| Placeholder _sync_session_state() implementation | 07-04 | Full session context sync requires SessionManager API refactor | Integration point established, deferred to Phase 8 or future work |
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
| Emoji constants for tool visualization | 03-03 | 📖 Read, ✏️ Edit, 💾 Write, 🔧 Bash, 🔍 Grep, 📁 Glob | Mobile-friendly visual scanning on small screens |
| 1600 char message limit for Signal | 03-03 | Signal supports more but mobile screens don't | Prevents unreadable wall-of-text on mobile |
| 0.5s minimum batch interval | 03-03 | Prevents Signal flooding while maintaining responsiveness | Balances UX smoothness with API courtesy |
| Sentence boundary splitting | 03-03 | Split on . ! ? or \n\n in last 30% of chunk | Readability over hard character cuts |
| Code block preservation | 03-03 | Small blocks stay intact, split before large blocks | Prevents breaking syntax-highlighted code |
| ClaudeOrchestrator as central coordinator | 03-04 | Single component coordinates bridge, parser, responder, Signal callback | Clean separation of concerns, easy to test, single point for error handling |
| 0.5s batch interval for message sending | 03-04 | Balances responsive user experience with Signal API courtesy | User sees updates quickly but Signal not flooded with individual messages |
| SessionCommands routes all messages | 03-04 | Single entry point determines /session vs Claude command routing | Daemon simplified, routing logic centralized |
| Thread-to-session mapping | 03-04 | Track which Signal thread has which active session | Enables stateful conversations - user doesn't need to specify session ID with every command |
| None response signals orchestrator streaming | 03-04 | Distinguish immediate responses (/session commands) from async streaming (Claude commands) | Daemon knows when to send response vs when orchestrator handles it |
| Conditional orchestrator.bridge assignment | 03-05 | Check if self.orchestrator exists before setting bridge | Prevents AttributeError if orchestrator not provided (backwards compatibility) |
| Bridge wired after process lifecycle events | 03-05 | Set bridge after process.start() completes in _start() and _resume() | Bridge available via process.get_bridge() only after process starts, enables immediate command execution |
| thread_id as PRIMARY KEY, project_path as UNIQUE | 04-01 | Enforces bijection at database level | One thread maps to one project, one project maps to one thread - database rejects violations automatically |
| Path validation before thread mapping | 04-01 | Check Path.exists() before creating mapping | Fail fast with clear error, prevents invalid mappings to non-existent directories |
| Idempotent unmap operation | 04-01 | unmap() doesn't raise error if thread not mapped | Enables safe retry logic, simpler error handling in higher layers |
| Reverse lookup index on project_path | 04-01 | CREATE INDEX for bidirectional queries | Efficient "which thread is working on this project?" lookups |
| ThreadMappingError for all validation failures | 04-01 | Single exception type for path missing, duplicate thread, duplicate path | Simpler exception handling, descriptive error messages |
| Follow SessionCommands pattern for ThreadCommands | 04-02 | Consistent user experience across /session and /thread commands | Same handle() routing structure, same help format |
| Truncate thread_ids to 8 chars in thread messages | 04-02 | Mobile screens can't display full UUIDs, 8 chars sufficient | Matches /session list display format from Phase 2-5 |
| Validate paths before mapper.map() | 04-02 | Provide clear "Path does not exist" error before database operations | Better error messages, fail fast on user input errors |
| Include persistence note in /thread help | 04-02 | Users need to know mappings survive daemon restarts | Help text clarifies mapping lifetime expectations |
| ThreadMapper initialized in __init__, async initialize() called in start() | 04-03 | Follow Phase 2 SessionManager pattern for async component initialization | Consistent lifecycle management, async DB operations in async context |
| ThreadCommands created after mapper initialization | 04-03 | ThreadCommands requires initialized mapper with DB schema | Ensures database ready before command handler created |
| SessionCommands.thread_commands as optional parameter | 04-03 | Follow orchestrator pattern - backwards compatible, testable | Works without thread_commands (graceful degradation) |
| Thread commands wired via property assignment | 04-03 | SessionCommands created before ThreadCommands exists | Flexible wiring after both components initialized |
| thread_mappings.db in Application Support | 04-03 | Follow sessions.db pattern for consistent data directory | macOS standard location, user-friendly path |
| Use mapped project_path when available, fall back to explicit path for backward compatibility | 04-04 | Provides best UX for mapped threads while maintaining compatibility | Users can start sessions without specifying path when thread is mapped |
| Mapped threads ignore explicit path arguments (mapping has priority) | 04-04 | Prevents confusion where user provides path but system uses different mapped path | Mapping always wins, explicit path argument ignored if mapping exists |
| Unmapped threads without explicit path return helpful error with both options | 04-04 | Guide users to either map the thread or provide explicit path | Clear path forward for users, reduces support questions |
| ThreadMapper passed as optional parameter to SessionCommands for graceful degradation | 04-04 | System should work without thread mapper for testing and backward compatibility | SessionCommands works with or without thread mapping feature |
| Log thread mapping count on daemon startup | 04-05 | Provides visibility into mapping state | Users can verify mappings loaded, debugging startup issues easier |
| Use capsys fixture for structlog output verification | 04-05 | structlog writes to stdout, not Python logging system | Tests correctly capture and verify log messages |
| Mock health server in daemon tests | 04-05 | Prevents port 8081 conflicts in concurrent/consecutive test runs | Tests run reliably without port binding errors |
| Safe operations: Read, Grep, Glob | 05-01 | Read-only operations don't modify files or state | Auto-execute without approval, improves UX |
| Destructive operations: Edit, Write, Bash | 05-01 | Operations that can modify files or system state | Require user approval, prevents unwanted changes |
| Unknown tools default to DESTRUCTIVE | 05-01 | Fail-safe approach when encountering new tool types | Better to require approval unnecessarily than skip needed approval |
| Case-insensitive tool name matching | 05-01 | Claude CLI might vary capitalization of tool names | "Read", "read", "READ" all work consistently |
| Conservative bash classification | 05-01 | Even read-only bash commands marked destructive | Shell commands unpredictable, fail-safe approach safer |
| UUID4 for approval IDs | 05-02 | Prevents collisions in concurrent request creation | Globally unique without coordination, follows session ID pattern |
| UTC-aware datetime.now(UTC) for approval timestamps | 05-02 | datetime.utcnow() deprecated in Python 3.12+ | Consistent with Phase 2, future-proof timestamps |
| 10-minute timeout for pending approvals | 05-02 | Balances user convenience with system responsiveness | Configurable via TIMEOUT_MINUTES class variable |
| Dict-based approval request tracking | 05-02 | Phase 5 in-memory state, no persistence needed yet | Approvals lost on daemon restart, acceptable for this phase |
| Idempotent approve/reject operations | 05-02 | Safe retry logic, follows SessionLifecycle pattern | Approving already-approved request doesn't error |
| Terminal state preservation in approval transitions | 05-02 | Once timed out, approval cannot be approved | Prevents race conditions where timeout and approval overlap |
| Approval commands take priority over session commands | 05-04 | User approvals are urgent (time-sensitive operations blocked) | Prevents conflicts where approval IDs might match session command patterns |
| ApprovalCommands optional parameter | 05-04 | Follow Phase 4-3 ThreadCommands pattern for backwards compatibility | SessionCommands works without approval system (testing, gradual rollout) |
| approve_all() iterates over list_pending() | 05-04 | Reuse existing method for consistency | Simple implementation, avoids duplicate logic |
| Truncate approval IDs to 8 chars in responses | 05-04 | Mobile screens (primary use case) cannot display full 36-char UUIDs | Consistent with Phase 2-5 session ID display, mobile-friendly UX |
| Approval system initialized in daemon __init__ | 05-05 | Approval components stateless, no async initialization needed | Components available immediately, simpler lifecycle |
| ApprovalCommands wired in run() method | 05-05 | Follow Phase 4-3 ThreadCommands pattern for component wiring | Consistent component lifecycle, supports graceful degradation |
| Single orchestrator instance receives approval_workflow | 05-05 | Daemon uses one orchestrator for all sessions (bridge updated per session) | Simpler than per-session orchestrators, same functionality |
| Startup logging with tool classification metrics | 05-05 | Follow Phase 4-5 pattern for component initialization logging | Visibility into approval system state on startup |
| MAX_WIDTH = 50 chars for mobile code display | 06-01 | 320px ÷ 6px per monospace char ≈ 53 chars; 50 provides margin | Code readable on smallest mobile screens without horizontal scroll |
| Continuation marker (↪) for wrapped lines | 06-01 | Visual indicator that line continues below | Prevents confusion with natural line breaks in code |
| Word boundary breaking in code wrapping | 06-01 | Breaking mid-identifier creates confusing partial tokens | Hard break at MAX_WIDTH if no space found (fallback) |
| INLINE_MAX = 20 lines, ATTACH_MIN = 100 lines | 06-01 | Balance inline context with attachment for large code | Mid-range (20-100) defaults to inline for better UX |
| Mid-range code (20-100 lines) defaults to inline | 06-01 | Better to show context inline than force download | Future /code full command will override for complete view |
| Terminal256Formatter with monokai style | 06-02 | Signal supports ANSI codes, monokai has high contrast for mobile | Good syntax distinction without overwhelming small screens |
| Rely on Pygments guess_lexer for language detection | 06-02 | Built-in detection handles Python/JS/TS/Rust/Go correctly | Simpler than custom regex patterns, leverages library robustness |
| Auto-detect language by default, allow explicit override | 06-02 | Reduces friction for users (no language specification needed) | Graceful fallback to plain text for unknown languages |
| Function/class detection prioritized over line counts | 06-03 | "Modified User.validate()" more informative than "added 2 lines" | Better mobile UX - user knows what behavior changed |
| Plain-English diff summaries without git syntax | 06-03 | Mobile users shouldn't parse +/- symbols and @@ markers | Format: "Created config.json: 20 lines" not "+20 -0" |
| Binary file detection skips content parsing | 06-03 | Binary files have no text representation in git diff | Output: "Updated image.png (binary file)" |
| Malformed diff input returns empty list | 06-03 | Graceful degradation - invalid diff doesn't crash system | Better UX with no error message for edge cases |
| Temp files with delete=False for controlled cleanup | 06-05 | Signal API expects file path, need control over cleanup timing | Create temp file, upload, cleanup in finally block |
| Cleanup in finally block ensures no leaked files | 06-05 | Upload errors shouldn't leave temp files in /tmp | Verified: zero temp file leaks after test runs |
| 100MB hard limit for attachments | 06-05 | Signal API constraint, requests fail above this | Size validation before temp file creation (fail fast) |
| 10MB warning threshold for attachments | 06-05 | Mobile data consideration for large downloads | Log warning but still upload (user decides to download) |
| Filename sanitization via os.path.basename + regex | 06-05 | Security (path traversal) + compatibility (cross-platform) | Pattern: [<>:"/\\|?*] replaced with underscore |
| E.164 validation pattern for phone numbers | 06-05 | Fail fast on invalid recipient before upload attempt | Pattern: ^\+[1-9]\d{1,14}$ validates country code + number |
| Return None on validation failures (non-blocking) | 06-05 | Attachment failures shouldn't crash daemon | Caller can retry or fall back to inline display |
| Overlay diff layout (not side-by-side) | 06-04 | 320px screens can't fit two columns of code without horizontal scroll | Show removed (➖) then added (➕) in sequence, more readable on mobile |
| Context collapse with 3-line threshold | 06-04 | Diffs can have 100+ unchanged lines between changes | Show 3 lines before/after, collapse middle with "... (N lines unchanged)" |
| Emoji markers for diff visual distinction | 06-04 | Mobile screens may have limited color contrast, accessibility | ➕ added, ➖ removed, ≈ context - works without relying solely on color |
| Format-then-highlight integration order | 06-04 | CodeFormatter operates on plain text, SyntaxHighlighter adds ANSI codes | format_code() first preserves width constraints, highlight() after adds color |
| Code/diff detection order: diff → code blocks → plain text | 06-06 | Diffs are most structured and need special handling | Ensures correct routing for mixed content |
| send_with_attachments() as separate method | 06-06 | Keeps format() pure (string transformation) separate from I/O operations | Cleaner architecture, easier testing, explicit post-processing step |
| /code full implementation deferred to Phase 7 | 06-06 | Requires session context tracking to store "last code output" | Natural fit for Phase 7 (Connection Resilience) which includes session state sync |
| Attachment marker line count calculation | 06-06 | Must match exact calculation in send_with_attachments() (code.count('\n') + 1) | Ensures marker replacement works correctly |
| deque with maxlen for automatic oldest-drop | 07-02 | Python's deque maxlen automatically drops oldest when full | Zero-overhead overflow management in MessageBuffer |
| Default max_size=100 messages | 07-02 | Balances reliability (substantial disconnect) with memory (25KB max) | Prevents both message loss and memory exhaustion |
| drain() returns list and clears atomically | 07-02 | Reconnection needs all messages at once, not iterative dequeue | Simpler integration, prevents partial drains |
| Set-based state transitions (VALID_TRANSITIONS) | 07-01 | O(1) lookup performance for transition validation | Fast validation, explicit state machine definition, easy to extend |
| 60-second maximum backoff cap | 07-01 | Balance between API courtesy and user responsiveness | Max 60s wait even after many failures, prevents excessive delays |
| attempt_count resets on CONNECTED transition | 07-01 | Successful connection indicates network stable, restart backoff sequence | Quick recovery after brief network instability, prevents overly conservative reconnection |
| auto_reconnect() as async loop | 07-03 | Loops while DISCONNECTED, transitions to RECONNECTING, sleeps for backoff, attempts connect | Clean separation from receive_messages(), can be spawned as background task |
| send_message() buffers before checking connection | 07-03 | Check reconnection_manager.state != CONNECTED first, buffer and return early | Graceful degradation - user messages queued instead of failing |
| receive_messages() catches ClientError to trigger reconnection | 07-03 | On aiohttp.ClientError: transition to DISCONNECTED, spawn auto_reconnect() task, return | Single source of truth for reconnection state, cleaner error handling |
| Daemon polls connection state every 1 second | 07-03 | monitor_connection_state() compares state to last_state in 1s loop | Simple polling adequate for human-observable connection changes, no complex event system needed |
| Activity log stored in session.context JSON blob | 07-05 | No schema changes needed, flexible structure, already persisted to SQLite | Activity tracking works immediately without database migrations |
| 10-activity limit for activity_log | 07-05 | Prevents unbounded context growth while preserving recent history | Context stays bounded, oldest activities dropped automatically |
| Catch-up summary generation deferred to Phase 8 | 07-05 | Requires notification system for "back online" message before draining buffer | Infrastructure ready (activity_log), implementation when notification system exists |
| activity_log structure: {timestamp, type, details} | 07-05 | Generic structure supports any activity type (commands, responses, file operations) | Flexible tracking without schema constraints |
| UrgencyLevel as IntEnum with lower values = higher urgency | 08-01 | Natural ordering for priority-based filtering | URGENT=0, IMPORTANT=1, INFORMATIONAL=2, SILENT=3 enables comparison operations |
| 300-char message limit for notifications | 08-01 | Mobile screen readability, consistent with Phase 3 decisions | Long messages truncated with "..." suffix |
| Case-insensitive event type matching | 08-01 | Defensive design, handles "ERROR" vs "error" vs "Error" | event["type"].lower() used for all lookups |
| Unknown event types default to INFORMATIONAL | 08-01 | Fail-safe default, better than dropping notifications | New event types automatically handled until categorization rule added |
| SILENT urgency returns empty string | 08-01 | Explicit "no notification" support for future filtering | Formatter returns "" for SILENT events (no Signal message sent) |
| Session IDs truncated to 8 chars in notifications | 08-01 | Follows Phase 2-6 convention, mobile-friendly display | "abc123de-f456-..." → "abc123de" in notifications |
| UrgencyLevel enum with 4 levels (URGENT, IMPORTANT, INFORMATIONAL, SILENT) | 08-02 | Clear hierarchy for notification prioritization | Enables preference matching with urgency overrides |
| URGENT overrides user preferences (always notify) | 08-02 | Critical events (errors, approvals) must not be silenced | Prevents user misconfiguration from degrading experience |
| SILENT overrides user preferences (never notify) | 08-02 | Internal events should never create user-facing notifications | Prevents debug/internal noise in Signal messages |
| Default preferences by urgency: IMPORTANT=True, INFORMATIONAL=False | 08-02 | Completion/reconnection events useful by default, progress events chatty | Balances discoverability with noise reduction |
| Application Support directory for notification_prefs.db | 08-02 | Follows macOS standards, consistent with thread/session databases | User-friendly location, persistent across updates |
| Composite primary key (thread_id, event_type) | 08-02 | Enables per-thread, per-event-type granular preference control | Fine-grained control without complex preference hierarchies |
| Idempotent upsert with ON CONFLICT for preferences | 08-02 | Follows Phase 2-5 patterns, safe retry logic | set_preference() can be called repeatedly without errors |
| NotificationCommands follows ApprovalCommands pattern | 08-03 | Consistent command handler design across approval/thread/notification | async handle(message, thread_id) signature matches ThreadCommands |
| Priority routing: approval → notify → thread → code → session → claude | 08-03 | Urgent operations first, then config, then operational, then content | Clear mental model prevents command conflicts |
| URGENT events cannot be disabled via /notify disable | 08-03 | Critical notifications (error, approval_needed) must not be silenced | Prevents user misconfiguration that breaks core functionality |
| Mobile-friendly emoji status indicators (✅/❌) in /notify list | 08-03 | Visual status scanning on small screens without reading text | Follows Phase 6 mobile-first UX patterns |
| UrgencyLevel as IntEnum consolidated in types.py | 08-03 | Single source of truth, supports comparison operations | URGENT=0, IMPORTANT=1, INFORMATIONAL=2, SILENT=3 with lower=higher urgency |
| NotificationManager orchestration pattern | 08-04 | Single notify() method coordinates categorization, preferences, formatting, and delivery | Simpler API for event sources (one call instead of multiple) |
| Optional notification_manager parameters for backwards compatibility | 08-04 | Follow Phase 5 ApprovalWorkflow pattern | Components work without notification system for testing and gradual rollout |
| Error notifications on exception, completion notifications on success | 08-04 | Error notifications: after user-facing error sent; Completion: before method returns | Ensures user sees error message before notification arrives |
| Notification system initialized in daemon run() after signal_client ready | 08-04 | async components need connection, follows Phase 4-5 pattern | notification_manager created when signal_client available for message sending |
| thread_id from recipient as fallback in orchestrator | 08-04 | execute_command() uses thread_id parameter or falls back to recipient | Ensures notifications work even without explicit thread_id |
| Catch-up summary generated atomically with activity_log clearing | 08-05 | generate_catchup_summary() clears activity_log after formatting to prevent duplicate summaries | Ensures one summary per reconnection, no repeated notifications |
| Skip catch-up notification if no meaningful activity | 08-05 | Check for "No activity" in summary before calling notify() | Avoids noise when nothing happened during disconnect |
| session_manager and notification_manager wired into SignalClient dynamically | 08-05 | Daemon sets attributes after component initialization using hasattr checks | Maintains decoupled architecture, SignalClient doesn't have direct dependencies |
| Plain-English activity summary format with operation counts | 08-05 | Activity type-specific formatting (tool_call, command_executed) with "Ready to continue" message | Mobile-friendly readability consistent with notification patterns |

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

## Session Continuity

Last session: 2026-01-28 15:28 UTC
Stopped at: Completed 08-05-PLAN.md (Catch-Up Summary) - Phase 8 complete
Resume file: None
