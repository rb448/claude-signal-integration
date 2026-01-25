# Roadmap: Claude Code Signal Integration

## Overview

Build a Signal bot that provides complete mobile access to Claude Code sessions running on a desktop Mac. Journey from basic Signal daemon infrastructure through session management, Claude integration, multi-project support, permission workflows, code display, connection resilience, notifications, advanced features, and comprehensive testing.

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
- [ ] **Phase 10: Testing & Quality** - Comprehensive test suite and CI/CD

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
**Research**: Likely (durable execution framework evaluation needed)
**Research topics**: Temporal vs Restate vs DBOS comparison, SQLite atomic write patterns, subprocess management for process isolation
**Plans**: TBD

Plans:
- [ ] 02-01: TBD during phase planning

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
**Research**: Unlikely (standard process isolation patterns)
**Plans**: TBD

Plans:
- [ ] 04-01: TBD during phase planning

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
**Research**: Unlikely (mobile notification best practices established)
**Plans**: TBD

Plans:
- [ ] 08-01: TBD during phase planning

### Phase 9: Advanced Features & Emergency Mode
**Goal**: Custom commands and streamlined emergency workflows
**Depends on**: Phase 3 (requires command infrastructure to extend)
**Requirements**: ADV-01, ADV-02, ADV-03, ADV-04
**Success Criteria** (what must be TRUE):
  1. User's ~/.claude/agents/ custom commands sync to mobile
  2. User can invoke custom slash commands from Signal with autocomplete
  3. User can activate emergency fix mode for production incidents
  4. Emergency mode pre-approves safe operations and auto-commits changes
**Research**: Unlikely (custom command sync is file system operation)
**Plans**: TBD

Plans:
- [ ] 09-01: TBD during phase planning

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
**Research**: Unlikely (Python testing patterns well-established)
**Plans**: TBD

Plans:
- [ ] 10-01: TBD during phase planning

## Progress

**Execution Order:**
Phases execute sequentially: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Core Infrastructure | 0/TBD | Not started | - |
| 2. Session Management | 0/TBD | Not started | - |
| 3. Claude Integration | 0/TBD | Not started | - |
| 4. Multi-Project | 0/TBD | Not started | - |
| 5. Permissions | 0/TBD | Not started | - |
| 6. Code Display | 0/TBD | Not started | - |
| 7. Connection Resilience | 0/TBD | Not started | - |
| 8. Notifications | 0/TBD | Not started | - |
| 9. Advanced Features | 0/TBD | Not started | - |
| 10. Testing & Quality | 0/TBD | Not started | - |
