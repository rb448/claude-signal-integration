# Roadmap: Claude Code Signal Integration

## Overview

Build a Signal bot that provides complete mobile access to Claude Code sessions running on a desktop Mac. Journey from basic Signal daemon infrastructure through session management, Claude integration, multi-project support, permission workflows, code display, connection resilience, notifications, advanced features, and comprehensive testing.

## TDD Discipline

**All phases follow strict Test-Driven Development (TDD) for business logic:**

- **RED-GREEN-REFACTOR cycle:** Write failing test → implement to pass → refactor if needed
- **Test-first commit pattern:** `test(phase-plan): ...` commits before `feat(phase-plan): ...` commits
- **TDD applies to:** Business logic, APIs, algorithms, state machines, data transformations, validators
- **Standard implementation:** Configuration, schema definitions, UI scaffolding, infrastructure setup

Each phase includes a **TDD Strategy** section specifying:
1. Which components warrant TDD (with specific examples)
2. Test-first execution order (numbered steps)
3. What to build-then-test (infrastructure/config)

**Verification:** Phase 10 audits all prior phases to ensure TDD discipline was maintained, retrofitting tests if gaps exist.

## Phases

**Phase Numbering:**
- Integer phases (1-10): Planned milestone work
- Decimal phases (X.1, X.2): Urgent insertions if needed (marked with INSERTED)

- [ ] **Phase 1: Core Infrastructure & Signal Integration** - Signal daemon foundation with rate limiting
- [ ] **Phase 2: Session Management & Durable Execution** - Process isolation and crash recovery
- [ ] **Phase 3: Claude Code Integration** - Bidirectional CLI communication
- [ ] **Phase 4: Multi-Project Support** - Signal thread-to-project mapping
- [ ] **Phase 5: Permission & Approval Workflows** - Destructive operation gates
- [ ] **Phase 6: Code Display & Mobile UX** - Mobile-optimized code formatting
- [ ] **Phase 7: Connection Resilience** - WebSocket reconnection and offline support
- [ ] **Phase 8: Notification System** - Configurable push notifications
- [ ] **Phase 9: Advanced Features** - Custom commands and emergency mode
- [x] **Phase 10: Testing & Quality** - Comprehensive test suite and CI/CD
- [x] **Phase 11: Claude Integration Wiring Fixes** - Restore primary user flow (gap closure)
- [ ] **Phase 12: Test Coverage Improvement** - Unit tests for critical modules (quality enhancement)

## Phase Details

### Phase 1: Core Infrastructure & Signal Integration
**Goal**: Establish Signal daemon foundation with rate limiting protection
**Depends on**: Nothing (first phase)
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05
**Success Criteria** (what must be TRUE):
  1. Signal bot daemon receives messages from authorized phone number
  2. Message queue prevents rate limit errors during bursts
  3. Daemon automatically restarts after crashes via launchd
  4. WebSocket connection maintains real-time message receipt
  5. Bot authenticates user via phone number verification
**Research**: Unlikely (signal-cli-rest-api well-documented, established daemon patterns)
**Plans**: TBD

Plans:
- [ ] 01-01: TBD during phase planning

### Phase 2: Session Management & Durable Execution
**Goal**: Enable session persistence with crash recovery
**Depends on**: Phase 1 (requires messaging infrastructure)
**Requirements**: SESS-01, SESS-02, SESS-03, SESS-04, SESS-05, SESS-06
**Success Criteria** (what must be TRUE):
  1. User can start new Claude Code session from Signal message
  2. User can resume existing session with full conversation history
  3. Session state persists across bot restarts
  4. Each project runs in isolated Claude Code process
  5. System recovers session state automatically after crash
**TDD Strategy**: Test-first for all business logic
  - **TDD (write tests FIRST):**
    - Session lifecycle state machine (create → active → paused → resumed → terminated)
    - Session persistence layer (save/load from SQLite with atomic writes)
    - Crash recovery logic (detect crash → restore state → resume from checkpoint)
    - Process isolation (spawn subprocess → verify isolation → clean shutdown)
  - **Standard (build then test):**
    - SQLite schema definition
    - Configuration file structure
    - Subprocess scaffolding
  - **Test-first execution order:**
    1. Write failing tests for SessionManager.create(), .resume(), .persist()
    2. Implement session state machine to pass tests
    3. Write failing tests for crash detection and recovery
    4. Implement recovery logic to pass tests
    5. Write failing tests for process isolation
    6. Implement subprocess management to pass tests
**Research**: Likely (durable execution framework evaluation needed)
**Research topics**: Temporal vs Restate vs DBOS comparison, SQLite atomic write patterns, subprocess management for process isolation
**Plans**: 7 plans (5 initial + 2 gap closure)
**Completed**: 2026-01-26

Plans:
- [x] 02-01: Session persistence (SQLite schema + SessionManager CRUD)
- [x] 02-02: Session lifecycle state machine
- [x] 02-03: Process isolation (ClaudeProcess subprocess management)
- [x] 02-04: Crash recovery (CrashRecovery.recover() on startup)
- [x] 02-05: Session commands integration (/session start/list/resume/stop/help)
- [x] 02-06: Wire session command responses to Signal (gap closure)
- [x] 02-07: Conversation history restoration infrastructure (gap closure)

### Phase 3: Claude Code Integration & Command Parity
**Goal**: Full Claude Code command set accessible via Signal
**Depends on**: Phase 2 (requires session management)
**Requirements**: CLDE-01, CLDE-02, CLDE-03, CLDE-04, CLDE-05, CLDE-06
**Success Criteria** (what must be TRUE):
  1. Commands sent from Signal execute in Claude Code CLI
  2. Claude responses stream back to Signal in real-time
  3. User sees Claude tool calls as they happen (Read, Edit, Write, Bash)
  4. Progress updates show Claude's current action
  5. Error messages display when operations fail
  6. All Claude Code commands work from Signal (command parity achieved)
**TDD Strategy**: Test-first for command parsing and communication protocol
  - **TDD (write tests FIRST):**
    - Command parser (Signal message → Claude command object)
    - Bidirectional communication protocol (command → CLI → response → Signal)
    - Response streaming handler (chunk messages for mobile, maintain order)
    - Tool call parser (extract Read/Edit/Write/Bash from Claude output)
    - Error handler (CLI errors → user-friendly Signal messages)
  - **Standard (build then test):**
    - Initial subprocess spawn for Claude CLI
    - Logging configuration
  - **Test-first execution order:**
    1. Write failing tests for CommandParser.parse(message) → command
    2. Implement parser to pass tests (handle /command syntax, arguments)
    3. Write failing tests for CLIBridge.execute(command) → response stream
    4. Implement bidirectional communication to pass tests
    5. Write failing tests for ToolCallParser.extract(output) → tool calls
    6. Implement tool call extraction to pass tests
    7. Write failing tests for error scenarios (timeout, crash, invalid command)
    8. Implement error handling to pass tests
**Research**: Unlikely (Anthropic SDK documentation comprehensive)
**Plans**: TBD

Plans:
- [ ] 03-01: TBD during phase planning

### Phase 4: Multi-Project Support & Thread Management
**Goal**: Independent sessions per Signal thread/project
**Depends on**: Phase 2 (requires process isolation architecture)
**Requirements**: PROJ-01, PROJ-02, PROJ-03, PROJ-04, PROJ-05
**Success Criteria** (what must be TRUE):
  1. Each Signal thread maps to unique project directory
  2. User can work on multiple projects simultaneously without context mixing
  3. User can create new project thread with directory selection
  4. User can switch between threads without losing session state
  5. Project-to-directory mappings persist across restarts
**TDD Strategy**: Test-first for mapping and isolation logic
  - **TDD (write tests FIRST):**
    - Thread-to-project mapper (thread_id → project_path, bijective mapping)
    - Context isolation verifier (thread A changes don't affect thread B)
    - Thread state manager (create → active → paused → switch → resume)
    - Mapping persistence (save/load mappings, survive restart)
    - Directory validator (path exists, writable, not already mapped)
  - **Standard (build then test):**
    - Directory selection UI messages
    - Initial mapping storage schema
  - **Test-first execution order:**
    1. Write failing tests for ThreadMapper.map(thread_id, path) → success/error
    2. Implement mapper with validation to pass tests
    3. Write failing tests for context isolation (parallel threads don't mix state)
    4. Implement isolation to pass tests (separate sessions, separate state)
    5. Write failing tests for thread switching (pause A → activate B → resume A)
    6. Implement state manager to pass tests
    7. Write failing tests for persistence (save → restart → load → verify)
    8. Implement persistence to pass tests
**Research**: Unlikely (standard process isolation patterns)
**Plans**: 5 plans
**Completed**: 2026-01-26

Plans:
- [x] 04-01: Thread-to-project mapping persistence (SQLite + ThreadMapper)
- [x] 04-02: Thread command interface (/thread map/list/unmap/help)
- [x] 04-03: Daemon integration & command routing
- [x] 04-04: Session creation with thread mapping validation
- [x] 04-05: Daemon startup with thread mapper initialization

### Phase 5: Permission & Approval Workflows
**Goal**: Safe delegation with approval gates for destructive operations
**Depends on**: Phase 3 (requires Claude integration to detect operations)
**Requirements**: PERM-01, PERM-02, PERM-03, PERM-04, PERM-05, PERM-06, PERM-07
**Success Criteria** (what must be TRUE):
  1. System detects destructive operations before execution (file edits, deletions, git push)
  2. User receives push notification when approval needed
  3. User can approve operation via Signal reply
  4. User can reject operation via Signal reply
  5. System pauses work and notifies user on approval timeout (10 min)
  6. User can approve batch of operations with single command
  7. Approved operations execute; rejected operations skip
**TDD Strategy**: Test-first for approval state machine and operation detection
  - **TDD (write tests FIRST):**
    - Operation detector (Claude tool call → destructive/safe classification)
    - Approval state machine (pending → approved/rejected/timeout → execute/skip)
    - Timeout handler (wait 10min → notify user → pause work)
    - Batch approver (multiple pending → approve all → execute in order)
    - Operation classifier rules (Edit = destructive, Read = safe, etc.)
  - **Standard (build then test):**
    - Push notification formatting
    - Approval request message templates
  - **Test-first execution order:**
    1. Write failing tests for OperationDetector.classify(tool_call) → destructive/safe
    2. Implement classifier with rules to pass tests
    3. Write failing tests for ApprovalManager.request() → pending state
    4. Implement state machine to pass tests
    5. Write failing tests for timeout (wait → timeout → pause → notify)
    6. Implement timeout handler to pass tests
    7. Write failing tests for batch approval (approve_all → all execute)
    8. Implement batch logic to pass tests
    9. Write failing tests for edge cases (duplicate approval, reject after timeout)
    10. Implement edge case handling to pass tests
**Research**: Unlikely (established mobile notification patterns)
**Plans**: TBD

Plans:
- [ ] 05-01: TBD during phase planning

### Phase 6: Code Display & Mobile UX
**Goal**: Code readable on mobile screens (320px)
**Depends on**: Phase 3 (requires code from Claude to display)
**Requirements**: CODE-01, CODE-02, CODE-03, CODE-04, CODE-05, CODE-06
**Success Criteria** (what must be TRUE):
  1. Short code snippets (<20 lines) display inline with monospace formatting
  2. Long code (>100 lines) sends as file attachments
  3. Syntax highlighting works on mobile screens
  4. Diffs render in readable side-by-side or overlay mode
  5. Plain-English summaries accompany code changes
  6. User can request full code view when summary insufficient
**TDD Strategy**: Test-first for formatting and rendering algorithms
  - **TDD (write tests FIRST):**
    - Code formatter (raw code → mobile-optimized text, max 320px width)
    - Length detector (code → inline/attachment decision, <20 lines vs >100 lines)
    - Syntax highlighter (code + language → ANSI-colored text)
    - Diff parser (git diff → structured before/after representation)
    - Diff renderer (diff object → readable mobile format, overlay or side-by-side)
    - Summary generator (code change → plain-English description)
  - **Standard (build then test):**
    - Signal attachment API integration
    - Mobile preview generation
  - **Test-first execution order:**
    1. Write failing tests for CodeFormatter.format(code, width=320) → formatted
    2. Implement formatter with line wrapping to pass tests
    3. Write failing tests for LengthDetector.should_attach(code) → bool
    4. Implement threshold logic to pass tests
    5. Write failing tests for SyntaxHighlighter.highlight(code, lang) → colored
    6. Implement highlighter to pass tests (Pygments integration)
    7. Write failing tests for DiffParser.parse(git_diff) → diff_object
    8. Implement parser to pass tests
    9. Write failing tests for DiffRenderer.render(diff_object, mode) → mobile_text
    10. Implement renderer to pass tests (handle 320px constraint)
    11. Write failing tests for SummaryGenerator.generate(diff) → description
    12. Implement summarizer to pass tests
**Research**: Likely (mobile diff rendering libraries sparse, may need prototyping)
**Research topics**: Signal attachment format limits, mobile syntax highlighting libraries (Pygments optimization), diff rendering at 320px
**Plans**: TBD

Plans:
- [ ] 06-01: TBD during phase planning

### Phase 7: Connection Resilience & Offline Support
**Goal**: Claude continues working during mobile disconnects
**Depends on**: Phase 3 (requires bidirectional sync to test resilience)
**Requirements**: CONN-01, CONN-02, CONN-03, CONN-04, CONN-05
**Success Criteria** (what must be TRUE):
  1. WebSocket reconnects automatically after network drop
  2. Outgoing messages buffer during disconnect and send on reconnect
  3. Session state synchronizes after reconnection
  4. User sees connection status (connected/reconnecting/offline/syncing)
  5. Claude keeps working during mobile disconnect; user catches up on reconnect
**TDD Strategy**: Test-first for reconnection logic and buffer management
  - **TDD (write tests FIRST):**
    - Reconnection state machine (connected → dropped → reconnecting → connected)
    - Exponential backoff calculator (attempt 1 = 1s, attempt 2 = 2s, attempt 3 = 4s, max 60s)
    - Message buffer (queue outgoing during disconnect, drain on reconnect)
    - State synchronizer (diff local vs remote state → merge → notify user)
    - Connection health monitor (ping/pong, detect stale connection)
  - **Standard (build then test):**
    - Connection status indicator messages
    - Reconnection logging
  - **Test-first execution order:**
    1. Write failing tests for ReconnectionManager.on_disconnect() → state transition
    2. Implement state machine to pass tests
    3. Write failing tests for backoff calculator (attempt → delay in seconds)
    4. Implement exponential backoff to pass tests
    5. Write failing tests for MessageBuffer.enqueue()/dequeue() during disconnect
    6. Implement buffer with drain-on-reconnect to pass tests
    7. Write failing tests for StateSynchronizer.sync() → merged state
    8. Implement sync algorithm to pass tests
    9. Write failing tests for HealthMonitor.is_stale() → bool
    10. Implement ping/pong to pass tests
**Research**: Unlikely (WebSocket reconnection well-documented)
**Plans**: TBD

Plans:
- [ ] 07-01: TBD during phase planning

### Phase 8: Notification System
**Goal**: Configurable notifications for different event types
**Depends on**: Phase 5 (requires approval system as notification use case)
**Requirements**: NOTF-01, NOTF-02, NOTF-03, NOTF-04
**Success Criteria** (what must be TRUE):
  1. Push notifications sent for critical events (errors, approvals needed)
  2. User can configure notification preferences per project thread
  3. Notifications categorized by urgency (urgent/important/informational/silent)
  4. User can enable/disable notifications per event type (errors vs progress vs completions)
**TDD Strategy**: Test-first for event classification and preference filtering
  - **TDD (write tests FIRST):**
    - Event categorizer (event → urgency level: urgent/important/informational/silent)
    - Preference matcher (event + user prefs → send/skip notification)
    - Per-thread preference manager (thread_id + event_type → enabled/disabled)
    - Notification formatter (event → user-friendly message text)
    - Priority rules (urgent always sends, silent never sends, etc.)
  - **Standard (build then test):**
    - Notification delivery mechanism
    - Preference storage schema
  - **Test-first execution order:**
    1. Write failing tests for EventCategorizer.categorize(event) → urgency
    2. Implement categorization rules to pass tests
    3. Write failing tests for PreferenceMatcher.should_notify(event, prefs) → bool
    4. Implement matcher to pass tests
    5. Write failing tests for PreferenceManager.get/set(thread, event_type, enabled)
    6. Implement per-thread preferences to pass tests
    7. Write failing tests for NotificationFormatter.format(event) → message
    8. Implement formatter to pass tests
    9. Write failing tests for priority rules (urgent overrides user prefs, etc.)
    10. Implement priority logic to pass tests
**Research**: Unlikely (mobile notification best practices established)
**Plans**: 5 plans
**Completed**: 2026-01-28

Plans:
- [x] 08-01: Event Categorization & Formatting
- [x] 08-02: Notification Preferences
- [x] 08-03: Notification Command Interface
- [x] 08-04: Orchestrator & Daemon Integration
- [x] 08-05: Catch-Up Summary Generation

### Phase 9: Advanced Features & Emergency Mode
**Goal**: Custom commands and streamlined emergency workflows
**Depends on**: Phase 3 (requires command infrastructure to extend)
**Requirements**: ADV-01, ADV-02, ADV-03, ADV-04
**Success Criteria** (what must be TRUE):
  1. User's ~/.claude/agents/ custom commands sync to mobile
  2. User can invoke custom slash commands from Signal with autocomplete
  3. User can activate emergency fix mode for production incidents
  4. Emergency mode pre-approves safe operations and auto-commits changes
**TDD Strategy**: Test-first for sync algorithm and emergency mode rules
  - **TDD (write tests FIRST):**
    - Command syncer (detect new/modified/deleted commands in ~/.claude/agents/)
    - Delta calculator (local commands vs mobile cache → add/update/remove)
    - Emergency mode state machine (normal → emergency → auto-approve → auto-commit → normal)
    - Safe operation classifier (emergency mode: Read/Grep safe, Edit/Write need rules)
    - Auto-approval rules (emergency mode approves edits but not deletions/git push)
    - Auto-commit formatter (changes → commit message with emergency flag)
  - **Standard (build then test):**
    - File system watcher setup
    - Autocomplete UI formatting
  - **Test-first execution order:**
    1. Write failing tests for CommandSyncer.detect_changes() → added/modified/deleted
    2. Implement file watcher to pass tests
    3. Write failing tests for DeltaCalculator.calculate(local, remote) → delta
    4. Implement delta logic to pass tests
    5. Write failing tests for EmergencyMode.activate() → state transition
    6. Implement state machine to pass tests
    7. Write failing tests for SafeOperationClassifier.is_safe(op, emergency=True) → bool
    8. Implement classifier with emergency rules to pass tests
    9. Write failing tests for AutoApprovalRules.should_auto_approve(op) → bool
    10. Implement rules to pass tests
    11. Write failing tests for AutoCommitFormatter.format(changes) → commit_msg
    12. Implement formatter to pass tests
**Research**: Unlikely (custom command sync is file system operation)
**Plans**: 5 plans
**Completed**: 2026-01-28

Plans:
- [x] 09-01: Custom Command Sync (Registry + Syncer)
- [x] 09-02: Emergency Mode Core (State Machine + Auto-Approver + Auto-Committer)
- [x] 09-03: Custom Command Interface (/custom list/show/invoke)
- [x] 09-04: Emergency Commands Integration (/emergency activate/deactivate)
- [x] 09-05: Daemon Integration & Command Routing

### Phase 10: Testing & Quality Validation
**Goal**: Comprehensive test coverage with automated CI/CD
**Depends on**: Phases 1-9 (tests validate all functionality)
**Requirements**: TEST-01, TEST-02, TEST-03, TEST-04, TEST-05, TEST-06, TEST-07, TEST-08
**Success Criteria** (what must be TRUE):
  1. Core components have unit tests with >80% coverage
  2. Integration tests verify Signal ↔ Claude Code communication flows
  3. Rate limiting tests validate queue behavior under load
  4. Session persistence tests verify crash recovery
  5. Network drop tests verify reconnection behavior
  6. End-to-end tests validate complete user workflows (start → delegate → approve → complete)
  7. Tests run automatically in CI/CD before merges
  8. Test fixtures provide realistic Signal/Claude message payloads
**TDD Strategy**: Validate TDD discipline from all prior phases and add missing coverage
  - **TDD Validation (verify prior phases followed TDD):**
    - Audit all prior phase SUMMARYs for TDD commit patterns (test → feat → refactor)
    - Verify each business logic component has test file created BEFORE implementation
    - Check git history shows test commits before feature commits
    - Identify any components that skipped TDD and retrofit tests
  - **Coverage Gaps (write tests for any missing scenarios):**
    - Load testing (simulate 100 concurrent sessions)
    - Chaos testing (random network drops, process kills, corrupt state files)
    - Security testing (injection attacks, unauthorized access attempts)
    - Performance regression tests (ensure new features don't degrade speed)
  - **CI/CD Pipeline (build then test - infrastructure):**
    - GitHub Actions workflow configuration
    - Test fixtures and mocks
    - Coverage reporting setup
  - **Test-first execution order:**
    1. Audit Phases 1-9 commit history for TDD compliance
    2. Write report: which components followed TDD, which didn't
    3. For non-TDD components: write missing unit tests (retroactive TDD)
    4. Write failing load tests (100 concurrent sessions)
    5. Optimize code to pass load tests
    6. Write failing chaos tests (random failures, corrupt state)
    7. Harden code to pass chaos tests
    8. Write failing security tests (injection, auth bypass)
    9. Secure code to pass security tests
    10. Set up CI/CD pipeline with all tests
**Research**: Unlikely (Python testing patterns well-established)
**Plans**: 5 plans
**Completed**: 2026-01-28

Plans:
- [x] 10-01: TDD Audit & Coverage Baseline
- [x] 10-02: Integration Testing
- [x] 10-03: Load & Chaos Testing
- [x] 10-04: CI/CD Setup
- [x] 10-05: Coverage Gaps & Security Testing

### Phase 11: Claude Integration Wiring Fixes
**Goal**: Wire Claude command execution and response routing to restore primary user flow
**Depends on**: Phase 3 (builds on Claude Integration infrastructure)
**Requirements**: Restores CLDE-01, CLDE-02 (bidirectional communication)
**Gap Closure**: Closes 2 integration gaps + 1 flow gap from v1.0 milestone audit
**Success Criteria** (what must be TRUE):
  1. SessionCommands passes all required parameters to execute_command (recipient, thread_id)
  2. ClaudeOrchestrator routes responses using thread_id instead of session_id
  3. Primary user flow works: Start session → Send Claude command → Receive response
  4. Integration test validates full flow end-to-end
  5. No signature mismatches in Claude integration layer
**TDD Strategy**: Test-first for integration wiring
  - **TDD (write tests FIRST):**
    - Integration test for full user flow (start → command → response)
    - Signature validation test (execute_command receives all 4 parameters)
    - Response routing test (thread_id used for send_message)
  - **Implementation (after tests fail):**
    - Fix execute_command call in SessionCommands (add recipient, thread_id)
    - Store thread_id in ClaudeOrchestrator and use for routing
  - **Test-first execution order:**
    1. Write failing integration test: test_full_user_flow (start session → send command → verify response received)
    2. Run test → fails at execute_command call (signature mismatch)
    3. Fix SessionCommands line 237 → add recipient=thread_id, thread_id=thread_id
    4. Run test → fails at response routing (session_id used instead of thread_id)
    5. Fix ClaudeOrchestrator lines 67, 216 → store and use thread_id
    6. Run test → passes (full flow works)
**Research**: Not needed (simple parameter wiring)
**Plans**: 1 plan

Plans:
- [x] 11-01: Fix execute_command wiring and response routing

### Phase 12: Test Coverage Improvement
**Goal**: Improve unit test coverage for 4 critical modules from below 80% to 85%+
**Depends on**: Phase 10 (requires test infrastructure)
**Requirements**: Quality enhancement (improves TEST-01)
**Success Criteria** (what must be TRUE):
  1. SignalClient coverage ≥85% (from 55%)
  2. ClaudeProcess coverage ≥85% (from 70%)
  3. Daemon coverage ≥85% (from 71%)
  4. Orchestrator coverage ≥85% (from 73%)
  5. Overall coverage ≥90% (from 89%)
**TDD Strategy**: Test-first for uncovered code paths
  - **TDD (write tests FIRST):**
    - Unit tests for error paths in SignalClient (reconnection failures, state races)
    - Unit tests for error paths in ClaudeProcess (spawn failures, SIGKILL timeout)
    - Unit tests for error paths in Daemon (component init failures, concurrent operations)
    - Unit tests for error paths in Orchestrator (bridge errors, approval timeouts)
  - **Verification (after tests pass):**
    - Run coverage report to verify ≥85% per module
    - Run full test suite to ensure no regressions
  - **Test-first execution order:**
    1. Analyze coverage reports to identify uncovered lines
    2. Write failing unit test for uncovered error path
    3. Verify test passes against existing implementation
    4. Repeat for all 20 tests (5 per module)
    5. Run full coverage report to confirm improvements
**Research**: Not needed (testing existing code paths)
**Plans**: 1 plan

Plans:
- [ ] 12-01: Unit Test Coverage for Critical Modules

## Progress

**Execution Order:**
Phases execute sequentially: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Core Infrastructure | 4/4 | Complete | 2026-01-25 |
| 2. Session Management | 7/7 | Complete | 2026-01-26 |
| 3. Claude Integration | 5/5 | Complete | 2026-01-26 |
| 4. Multi-Project | 5/5 | Complete | 2026-01-26 |
| 5. Permissions | 5/5 | Complete | 2026-01-26 |
| 6. Code Display | 6/6 | Complete | 2026-01-26 |
| 7. Connection Resilience | 5/5 | Complete | 2026-01-28 |
| 8. Notifications | 5/5 | Complete | 2026-01-28 |
| 9. Advanced Features | 5/5 | Complete | 2026-01-28 |
| 10. Testing & Quality | 5/5 | Complete | 2026-01-28 |
| 11. Wiring Fixes | 1/1 | Complete | 2026-01-28 |
| 12. Test Coverage | 0/1 | Pending | - |
