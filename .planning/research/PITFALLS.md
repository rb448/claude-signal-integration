# Pitfalls Research

**Domain:** Signal Bot + Remote Development Tool Integration
**Researched:** 2026-01-25
**Confidence:** MEDIUM

## Critical Pitfalls

### Pitfall 1: Signal Rate Limiting Without Queue Backoff

**What goes wrong:**
Signal returns HTTP 413 "Rate limit exceeded" errors even after initial successful sends to ~100 contacts. Bots continue attempting to send messages, getting rate-limited indefinitely, and failing to deliver even single messages after cooldown periods. Users report being unable to send messages even after resolving captcha challenges.

**Why it happens:**
Signal's rate limits are not well-documented for unofficial bot implementations (signal-cli/signalbot). Developers assume they can send at the same pace as the official client, but bot detection triggers stricter limits. Simple retry logic without exponential backoff causes rapid re-attempts that trigger cascading rate limits.

**How to avoid:**
- Implement exponential backoff with jitter: start with 500ms base delay, double after each failure, cap at 30 seconds, add random jitter up to 1000ms to prevent thundering herd
- Queue messages with priority levels (urgent vs. informational)
- Track per-recipient send rates — Signal appears to limit per-contact as well as per-account
- Monitor for 413 errors and implement circuit breaker pattern (stop sending after N consecutive failures)

**Warning signs:**
- 413 errors appearing in logs
- Messages successfully sent initially but failing after first batch
- Captcha challenges appearing (Signal's anti-spam measure)
- Error rate increasing over time even with constant traffic

**Phase to address:**
Phase 1 (Core Infrastructure) — Message queue with backoff must be foundational, not retrofitted later

---

### Pitfall 2: Signal Daemon Not Running in Continuous Receive Mode

**What goes wrong:**
Messages fail to decrypt, group updates don't sync, expiration timers malfunction, and the bot appears to receive messages but can't properly decrypt them. The Signal protocol breaks down because it expects regular message receipt for encryption ratcheting.

**Why it happens:**
Developers treat signal-cli like a stateless API tool, sending messages without maintaining a persistent daemon. The Signal protocol's Double Ratchet requires continuous message receipt to maintain encryption state. Without daemon mode, the bot's encryption keys fall out of sync with the server.

**How to avoid:**
- Run signal-cli in daemon mode with `--socket` or `--dbus` interface, not as one-off CLI commands
- Configure daemon to continuously receive messages: `daemon --socket /path/to/socket` with all local accounts loaded
- Set up systemd service or equivalent to ensure daemon restarts on crash
- Keep signal-cli updated — versions older than 3 months may break due to Signal server changes

**Warning signs:**
- "Failed to decrypt message" errors in logs
- Group metadata out of sync (members, name, avatar)
- Expiration timer not working correctly
- Messages arrive but content is garbled or empty

**Phase to address:**
Phase 1 (Core Infrastructure) — Daemon architecture is foundational, cannot be added later

---

### Pitfall 3: No Durable Execution for Long-Running Sessions

**What goes wrong:**
Bot process crashes during multi-step Claude interactions, losing all conversation context. When restarted, the bot cannot resume where it left off. Users receive partial responses or need to re-explain their request. File operations half-complete, leaving workspace in inconsistent state.

**Why it happens:**
Developers assume bot processes are reliable and don't crash. They store session state only in memory. When crashes occur (OOM, network issues, signal handling errors), all context evaporates. Traditional try-catch doesn't help because the process is gone.

**How to avoid:**
- Implement durable execution pattern: persist each step's result before proceeding
- Use battle-tested frameworks: Temporal, Restate, DBOS, or Microsoft's Durable Task Extension
- Design operations as incremental steps that can be replayed: when process crashes, recover from durable journal and resume from last completed step
- For Claude interactions: save conversation state after each turn, including tool calls and results
- Persist workspace state: track which files were read/modified in current session

**Warning signs:**
- Users report "losing their place" after bot stops responding
- Incomplete file operations (file created but not populated)
- No way to ask bot "what were we doing?" after reconnect
- Bot repeats questions already answered before crash

**Phase to address:**
Phase 2 (Session Management) — Build on Phase 1 infrastructure, critical before multi-turn conversations

---

### Pitfall 4: Treating E2E Encryption as Complete Security

**What goes wrong:**
Bot stores decrypted messages, API keys, or file contents in plain text on disk. Developer assumes "Signal is encrypted, so everything is secure" while sensitive data leaks through logs, temp files, or error messages. Desktop file system becomes attack surface.

**Why it happens:**
Misunderstanding E2E encryption scope — it protects data in transit and on Signal's servers, not on endpoints. Signal Desktop has had CVE-2023-24069 (file system vulnerability) where files were saved in predictable local directories. Developers focus on transport security but ignore at-rest data protection.

**How to avoid:**
- Never store decrypted message content in plain text files or logs
- Implement at-rest encryption for any persisted session state
- Store API keys/secrets in OS keychain (macOS Keychain, Linux Secret Service) or dedicated secrets manager (Doppler, HashiCorp Vault)
- Rotate API keys every 90 days minimum
- Use environment variables for configuration, not hardcoded values
- Implement proper access controls on bot's working directory — not world-readable
- Sanitize error messages before sending to users (don't leak file paths, API keys)

**Warning signs:**
- API keys visible in `ps aux` output
- Log files containing Claude responses with potentially sensitive code
- Temp files with `.signal` or `.claude` in predictable locations
- Error messages showing full file system paths to users

**Phase to address:**
Phase 1 (Core Infrastructure) — Security foundation cannot be retrofitted

---

### Pitfall 5: No Context Switching Isolation Between Projects

**What goes wrong:**
User asks bot about Project A while it still has files open from Project B. Bot suggests code changes that mix concerns across projects. File operations target wrong project directory. Claude context window polluted with irrelevant files, wasting tokens and degrading response quality.

**Why it happens:**
Developers assume users work on one project at a time. Bot maintains single global state without project boundaries. When user switches projects via Signal message, bot doesn't fully reset context. Research shows 20% cognitive capacity lost per context switch — bots suffer similarly from context pollution.

**How to avoid:**
- Implement project-scoped sessions: each project gets isolated context window and file system scope
- Require explicit project switching: user sends "/switch project-name" before changing context
- Clear previous project's file list from Claude context when switching
- Use separate working directories per project with strict path validation
- Track "last active project" per user — default to it, but verify before file operations
- Implement project isolation similar to IDE window management: one context per project

**Warning signs:**
- Bot references files from wrong project
- User confusion: "I didn't ask about that file"
- File operations failing with "path not found" after project switch
- Claude responses that mention irrelevant code/files

**Phase to address:**
Phase 2 (Session Management) — After basic bot works, before multi-project scenarios

---

### Pitfall 6: Mobile Code Display Without Formatting

**What goes wrong:**
Claude returns 500-line diffs that are unreadable on mobile. No syntax highlighting makes code blocks look like plain text. Long lines wrap awkwardly. Users can't distinguish between code, explanations, and file paths. Critical errors buried in walls of text.

**Why it happens:**
Developers test on desktop where terminals have 120+ column width and syntax highlighting. Signal messages default to plain text. Mobile screens are 320-428px wide — code formatted for desktop becomes horizontal scroll nightmare. Without markdown or syntax highlighting, code loses visual structure.

**How to avoid:**
- Limit code snippets to 20-30 lines max in Signal messages — link to full diffs
- Use markdown code blocks with language tags: ```python for syntax hints (if client supports)
- Break responses into multiple messages: summary first, then code sections
- For long responses: offer "send as file" option that user can download
- Test all formatting on actual mobile devices (iOS 320px, Android 360px widths)
- Preserve indentation but avoid horizontal scroll: wrap at 60-70 chars for mobile
- Use visual separators: "---" or "===" between sections

**Warning signs:**
- Users asking "can you resend that?" or "I can't read that"
- Long messages with code that scrolls horizontally
- Lack of visual distinction between code and explanation
- Users requesting email or other channels for code review

**Phase to address:**
Phase 3 (Mobile UX) — After core functionality works, critical for real usage

---

### Pitfall 7: Notification Spam vs. Information Gaps

**What goes wrong:**
Bot sends notification for every file read, every tool use, every intermediate step. User's phone buzzes 20+ times for single request. Or opposite: bot goes silent during 90-second Claude operation, user thinks it crashed. Both scenarios break trust and usability.

**Why it happens:**
Developers either log everything (treating Signal like terminal stdout) or nothing (assuming users know bot is working). 2026 research shows notification fatigue is the #1 reason users disable apps — once permission is lost, it's rarely regained. Without explicit design, bots default to wrong notification frequency.

**How to avoid:**
- Implement adaptive notification levels:
  - SILENT: only send final result
  - NORMAL: send start + finish + errors (default)
  - VERBOSE: include progress updates every 30s for long operations
- Allow user to configure per-project or per-session
- For multi-step operations: send "Working on [task]..." then only final result
- Use single message with edits if Signal API supports (avoid multiple messages)
- Implement progress indicators: "Step 2/5: Reading files..." rather than separate messages
- Set expectations: "This will take ~60 seconds" for long operations

**Warning signs:**
- Multiple notifications within 5 seconds
- Users responding "stop" or "too many messages"
- Silent periods >30 seconds where user asks "are you still there?"
- Users enabling Do Not Disturb when using bot

**Phase to address:**
Phase 3 (Mobile UX) — After core works but before heavy usage

---

### Pitfall 8: No WebSocket Reconnection with Exponential Backoff

**What goes wrong:**
Bot's WebSocket connection to Signal or Claude API drops due to network hiccup. Reconnection attempts every 100ms, overwhelming server. Or bot gives up after first failure, requiring manual restart. Users experience silent failures — messages sent but never delivered.

**Why it happens:**
Developers implement naive reconnection: immediate retry on disconnect. With 10,000 concurrent bots, server crash causes thundering herd — all reconnect simultaneously, causing cascading failure. Or they assume connections never drop, providing no reconnection logic.

**How to avoid:**
- Implement exponential backoff with jitter:
  - Base delay: 1 second
  - Max delay: 30 seconds
  - Jitter: random 0-1000ms
  - Formula: `delay = min(base * 2^attempt + random(0-1000), max_delay)`
- Limit reconnection attempts: 5-10 max before requiring manual intervention
- Implement heartbeat/ping-pong: send ping every 30s, assume disconnect if no pong in 10s
- Detect connection state: don't queue messages indefinitely if offline
- Surface connection status to user: "Connection lost, retrying..." vs. silent failure
- Log reconnection attempts for monitoring/debugging

**Warning signs:**
- Rapid reconnection attempts visible in server logs
- Users report "bot stopped responding" after network blip
- Server load spikes after brief outage
- No visibility into connection state — appears working but isn't

**Phase to address:**
Phase 1 (Core Infrastructure) — Foundational reliability concern

---

### Pitfall 9: Claude Tool Use Without Cost/Rate Limit Tracking

**What goes wrong:**
Single "show me the codebase" request triggers 200+ file reads, consuming thousands of tokens. Bill spikes unexpectedly. Rate limits hit mid-operation, causing partial failures. No visibility into which operations are expensive until invoice arrives.

**Why it happens:**
Claude's tool use adds 466-499 tokens to system prompt. Each tool_use block (parameters) and tool_result block (returned data) count as standard input/output tokens. Developers test with small files, then production uses large files. A single Cowork session with complex file operations can use quota equivalent to dozens of regular messages.

**How to avoid:**
- Implement token tracking per request: log input_tokens + output_tokens for every Claude call
- Set per-request token budgets: warn user if request will exceed threshold
- Track rate limit consumption: know your tier (Tier 1: 50 RPM, Tier 4: 4000 RPM)
- Use prompt caching aggressively: 90% discount on cached content, can reduce costs 80%
- Implement cost estimation: before reading 50 files, estimate token cost and ask user to confirm
- Monitor tier limits: upgrade from Tier 1 ($5 deposit) to Tier 4 ($400 deposit) when scaling
- File size limits: warn if file >10KB before reading (tool_result tokens)

**Warning signs:**
- Rate limit 429 errors appearing mid-session
- Unexpected API bill spikes
- No visibility into token consumption per request
- Users hitting limits during normal usage

**Phase to address:**
Phase 2 (Session Management) — Before heavy usage, enables informed scaling

---

### Pitfall 10: Hardcoded Timeouts for Variable-Duration Operations

**What goes wrong:**
Bot times out after 30 seconds, but Claude is still processing 500-line diff. User sees "Request failed" while Claude completes successfully 20 seconds later, wasting tokens. Or timeout is set to 5 minutes, causing 4-minute hangs on actually-failed requests.

**Why it happens:**
Developers set single global timeout for all operations. Reading small file: 2 seconds. Generating complex refactor: 90 seconds. Processing streaming response: variable. One-size-fits-all timeout either cuts off valid long operations or waits too long for failures.

**How to avoid:**
- Operation-specific timeouts:
  - File read: 5 seconds
  - Simple query: 15 seconds
  - Code generation: 60 seconds
  - Multi-step refactor: 120 seconds
- Implement streaming progress detection: timeout if no new data in 15 seconds, not absolute time
- For Claude streaming: reset timeout on each content block received
- Surface progress to user: "Still working... 45s elapsed" rather than silent timeout
- Allow user override: "This might take 2-3 minutes, continue? Y/N"
- Distinguish network timeout (10s) from operation timeout (60s+)

**Warning signs:**
- Operations timing out that actually complete successfully
- Wasted API calls due to premature timeout
- Users reporting "it failed but worked" confusion
- Long hangs on actually-failed operations

**Phase to address:**
Phase 2 (Session Management) — After basic operations work, before complex interactions

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Store session state in memory only | Faster development, no DB needed | All context lost on crash/restart; cannot scale horizontally | Never — use at least file-based persistence |
| Skip message queuing, send directly | Simpler architecture, fewer dependencies | Rate limits impossible to manage; thundering herd on restart | Only for single-user proof-of-concept |
| Use same timeout for all operations | One config value, less complexity | Either premature timeouts or excessive waits | Never — operation types need different limits |
| Hardcode API keys in env vars | Easy to deploy, no secrets manager needed | Keys visible in process list; cannot rotate without redeploy | Local dev only — production needs secrets manager |
| Poll for messages instead of daemon mode | Easier to understand/debug | Signal protocol breaks; encryption fails; high latency | Never — daemon mode is required for Signal bot reliability |
| Single global Claude context for all projects | No context management needed | Context pollution; wrong responses; wasted tokens | Only if bot explicitly designed for single-project use |

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| signal-cli | Running as one-off CLI commands instead of daemon | Run daemon with `--socket` or `--dbus`, maintain persistent process, keep updated (3-month max age) |
| Signal API | Assuming same rate limits as official client | Implement exponential backoff, per-contact rate tracking, circuit breaker after N 413 errors |
| Claude API | Not tracking tool_use token consumption | Log tokens per request, set budgets, use prompt caching, estimate costs before multi-file operations |
| Claude Streaming | Assuming responses arrive in <5 seconds | Use streaming mode, reset timeout on each content block, surface progress to user |
| WebSocket connections | Immediate reconnect on disconnect | Exponential backoff with jitter (1s → 30s), heartbeat every 30s, limit retry attempts |
| Desktop file system | Trusting file paths from user messages | Validate all paths against project root, prevent directory traversal, use absolute paths internally |

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| No message queue | Works fine initially, then 413 errors appear | Implement queue with backoff from day 1 | After ~100 messages sent or first burst of activity |
| In-memory only session state | Fast initially, then crashes lose everything | Use durable execution or persistent storage | First crash (unpredictable timing) |
| Loading entire file into Claude context | Works for small files, then rate limits/costs spike | Set file size limits (10KB warning, 50KB hard limit) | Files >50KB or >10 files per request |
| Synchronous file operations | Fast on SSD, slow on network mounts | Use async file I/O, timeout if >5s | Network-mounted home directories or NFS |
| Single WebSocket for all users | Works for 1-10 users, then connection instability | Connection pooling or per-user connections with limits | >50 concurrent users (depends on server) |
| No token budget per request | Cheap initially, then unexpected bills | Track and limit tokens, warn at thresholds | First large codebase exploration or batch operation |

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Storing decrypted Signal messages in plain text logs | Message content leaks via log aggregation or disk access | Never log message content; use structured logging with sanitization |
| Hardcoding Anthropic API keys in code or env vars | Keys visible in `ps aux`, process dumps, or version control | Use OS keychain or secrets manager; rotate every 90 days |
| Trusting file paths from Signal messages | Directory traversal allows reading arbitrary files | Validate against project root; reject `../`; use absolute paths |
| Assuming E2E encryption protects at-rest data | Unencrypted state on disk vulnerable to local access | Encrypt persisted session state; secure temp file permissions |
| Exposing full file system paths in error messages | Leaks directory structure and usernames to Signal chat | Sanitize errors: show relative paths from project root only |
| Slack/Signal bot tokens in version control | #1 most leaked secret type (40%+ of SaaS leaks) | Use .gitignore, pre-commit hooks, secrets scanning |
| Running bot process as root/admin | Compromise grants full system access | Run as dedicated user with minimal permissions |

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Sending 500-line code blocks to mobile | Unreadable horizontal scroll; user can't parse | Limit to 20-30 lines; offer "send as file" option; use summaries |
| No notification preference controls | Either notification fatigue or information gaps | Offer SILENT/NORMAL/VERBOSE modes; let user configure per-project |
| Silent failures (no feedback when things go wrong) | User doesn't know if bot is working or broken | Always acknowledge receipt; surface errors; show progress for >10s operations |
| Assuming >1000ms response time is acceptable | Modern expectation: <1 second for messaging | Show "typing..." indicator immediately; stream responses; use caching |
| No "what were we doing?" recovery after crash | User loses context, must re-explain everything | Persist conversation; offer "/resume" command; summarize last N interactions |
| Treating Signal like a terminal | Verbose output, raw paths, no context | Mobile-first formatting; summarize instead of dump; use conversational tone |
| No offline queue handling | Messages lost when network drops | Queue with deterministic ordering; sync within 90s of reconnection |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Message sending:** Often missing exponential backoff for rate limits — verify 413 handling and backoff logic exists
- [ ] **Session persistence:** Often missing crash recovery — verify state persists across process restart
- [ ] **File operations:** Often missing path validation — verify directory traversal prevention with `../` tests
- [ ] **Claude integration:** Often missing token tracking — verify per-request token logging and budget enforcement
- [ ] **WebSocket connections:** Often missing reconnection logic — verify exponential backoff and heartbeat implementation
- [ ] **Error handling:** Often missing user-facing error messages — verify errors are sanitized and actionable
- [ ] **signal-cli setup:** Often missing daemon mode — verify continuous receive mode, not one-off commands
- [ ] **Security:** Often missing secrets management — verify no hardcoded keys, using OS keychain or secrets manager
- [ ] **Mobile formatting:** Often missing mobile testing — verify on actual 320px width device, not just desktop
- [ ] **Notification strategy:** Often missing user control — verify SILENT/NORMAL/VERBOSE modes exist and work
- [ ] **Context isolation:** Often missing project switching — verify Claude context clears between projects
- [ ] **Offline handling:** Often missing queue persistence — verify messages queue when offline and sync on reconnect

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Hit Signal rate limits | LOW | Implement circuit breaker; stop sending for 15 minutes; exponential backoff on retry |
| Crashed without session persistence | HIGH | Cannot recover context; user must re-explain; implement durable execution before next session |
| Leaked API key in logs | MEDIUM | Rotate key immediately in Anthropic console; scan logs for usage; implement secrets manager |
| Wrong file modified due to context pollution | MEDIUM | Git revert if version controlled; restore from backup; implement project isolation |
| WebSocket stuck in reconnection loop | LOW | Implement connection state detection; reset after 10 failed attempts; notify user |
| Token budget exceeded | LOW | Pause operations; notify user of cost; implement per-request budgets |
| signal-cli encryption out of sync | MEDIUM | Restart daemon in continuous receive mode; may need to re-link device; document daemon requirement |
| Notification spam caused user to disable | HIGH | Cannot recover notification permission; implement granular controls before re-requesting |
| Timeout cut off valid operation | LOW | Retry with longer timeout; implement streaming progress detection |
| Directory traversal exploit attempt | MEDIUM | Log attempt; validate all file paths; implement allowlist of accessible directories |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Signal rate limiting | Phase 1: Core Infrastructure | Send 150 messages in burst — verify backoff prevents 413 cascade |
| Missing daemon mode | Phase 1: Core Infrastructure | Restart bot — verify encryption still works and messages decrypt |
| No durable execution | Phase 2: Session Management | Kill bot mid-operation — verify resume from last step on restart |
| E2E encryption misunderstanding | Phase 1: Core Infrastructure | Scan disk for plain-text API keys or message content — none found |
| No context isolation | Phase 2: Session Management | Switch projects — verify Claude doesn't reference previous project files |
| Mobile code formatting | Phase 3: Mobile UX | View 100-line diff on 320px screen — verify readable without horizontal scroll |
| Notification spam/gaps | Phase 3: Mobile UX | Run 5-minute operation — verify exactly 3 notifications (start, progress, finish) |
| WebSocket reconnection | Phase 1: Core Infrastructure | Simulate network drop — verify reconnection with exponential backoff |
| Claude cost tracking | Phase 2: Session Management | Request codebase scan — verify token estimate shown before execution |
| Hardcoded timeouts | Phase 2: Session Management | Run 90-second operation — verify doesn't timeout; run failed operation — verify timeout in <15s |

## Sources

### HIGH Confidence
- [Signal rate limiting issues — GitHub signal-cli Issue #161](https://github.com/AsamK/signal-cli/issues/161)
- [Signal rate limiting issues — GitHub signal-cli Issue #1603](https://github.com/AsamK/signal-cli/issues/1603)
- [signal-cli daemon mode documentation — GitHub](https://github.com/AsamK/signal-cli)
- [signal-cli best practices for deployment — Issue #402](https://github.com/AsamK/signal-cli/issues/402)
- [Claude API rate limits — Official docs](https://platform.claude.com/docs/en/api/rate-limits)
- [Claude API pricing 2026 — Official docs](https://platform.claude.com/docs/en/about-claude/pricing)
- [Claude API streaming — Official docs](https://platform.claude.com/docs/en/build-with-claude/streaming)

### MEDIUM Confidence
- [WebSocket reconnection strategies — DEV Community](https://dev.to/hexshift/robust-websocket-reconnection-strategies-in-javascript-with-exponential-backoff-40n1)
- [Durable execution for AI agents — Microsoft Community](https://techcommunity.microsoft.com/blog/appsonazureblog/bulletproof-agents-with-the-durable-task-extension-for-microsoft-agent-framework/4467122)
- [Durable execution for crashproof agents — DBOS](https://www.dbos.dev/blog/durable-execution-crashproof-ai-agents)
- [Notification fatigue best practices 2026 — Appbot](https://appbot.co/blog/app-push-notifications-2026-best-practices/)
- [Chatbot best practices 2026 — Botpress](https://botpress.com/blog/chatbot-best-practices)
- [Context switching developer productivity — Reclaim](https://reclaim.ai/blog/context-switching)
- [Mobile messaging latency expectations — Pusher](https://pusher.com/blog/how-latency-affects-user-engagement/)
- [Secrets management environment variables 2026 — Security Boulevard](https://securityboulevard.com/2025/12/are-environment-variables-still-safe-for-secrets-in-2026/)

### LOW Confidence
- [Signal Desktop file vulnerabilities — Kaspersky](https://usa.kaspersky.com/blog/signal-desktop-file-vulnerabilities/27728/)
- [Signal Desktop memory issues — GitHub Issue #4054](https://github.com/signalapp/Signal-Desktop/issues/4054)
- [Chatbot security risks 2026 — Botpress](https://botpress.com/blog/chatbot-security)
- [Offline messaging capabilities — Best Mobile IM 2026](https://www.alibaba.com/product-insights/best-mobile-instant-messaging-application-efficiency-benchmarked-2026.html)

---
*Pitfalls research for: Signal Bot + Remote Development Tool Integration*
*Researched: 2026-01-25*
