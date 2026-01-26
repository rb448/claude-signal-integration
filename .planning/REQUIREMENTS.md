# Requirements: Claude Code Signal Integration

**Defined:** 2026-01-25
**Core Value:** Enable complete Claude Code functionality from mobile without requiring GitHub repos - users can continue development work with local directories while away from their desk.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Signal Bot Infrastructure

- [ ] **INFRA-01**: Signal bot daemon runs in JSON-RPC mode via signal-cli-rest-api
- [ ] **INFRA-02**: WebSocket connection maintains real-time message receipt from Signal
- [ ] **INFRA-03**: Phone number verification authenticates authorized user
- [ ] **INFRA-04**: Message queue implements exponential backoff for rate limiting protection
- [ ] **INFRA-05**: launchd service configuration manages macOS daemon lifecycle with auto-restart

### Session Management

- [ ] **SESS-01**: User can start new Claude Code session from Signal message
- [ ] **SESS-02**: User can resume existing Claude Code session with full conversation context
- [ ] **SESS-03**: System manages session lifecycle (create/resume/terminate) reliably
- [ ] **SESS-04**: Each project session runs in isolated Claude Code process
- [ ] **SESS-05**: System automatically recovers session state after crash or restart
- [ ] **SESS-06**: SQLite database persists session state with atomic writes (write-to-temp, then rename)

### Claude Code Integration

- [ ] **CLDE-01**: Bidirectional communication syncs commands from Signal to Claude Code CLI
- [ ] **CLDE-02**: Bidirectional communication syncs responses from Claude Code CLI to Signal
- [ ] **CLDE-03**: User can execute full Claude Code command set from Signal messages
- [ ] **CLDE-04**: System streams Claude tool calls in real-time to Signal
- [ ] **CLDE-05**: System streams progress updates to show Claude's current action
- [ ] **CLDE-06**: System displays user-facing error messages when operations fail

### Multi-Project Support

- [ ] **PROJ-01**: System maps each Signal thread to unique project directory
- [ ] **PROJ-02**: System maintains independent session state per Signal thread
- [ ] **PROJ-03**: User can create new project thread with directory selection
- [ ] **PROJ-04**: User can switch between project threads without context loss
- [ ] **PROJ-05**: System persists project-to-directory mappings across restarts

### Permission & Approval System

- [ ] **PERM-01**: System detects destructive operations (file edits, deletions, git push)
- [ ] **PERM-02**: System sends approval request with operation context before executing
- [ ] **PERM-03**: User receives push notification for pending approval requests
- [ ] **PERM-04**: User can approve operation via Signal message
- [ ] **PERM-05**: User can reject operation via Signal message
- [ ] **PERM-06**: System handles approval timeout (10 minutes) by pausing work and notifying user
- [ ] **PERM-07**: User can approve all operations in a batch with single command

### Code Display System

- [ ] **CODE-01**: System displays code snippets (<20 lines) inline with monospace formatting
- [ ] **CODE-02**: System sends long code (>100 lines) as file attachments
- [ ] **CODE-03**: System applies syntax highlighting optimized for mobile screens (320px)
- [ ] **CODE-04**: System renders diffs with side-by-side or overlay mode
- [ ] **CODE-05**: System provides plain-English summaries of code changes
- [ ] **CODE-06**: User can request full code view when summary is insufficient

### Connection Resilience

- [ ] **CONN-01**: System automatically reconnects WebSocket after network drop with exponential backoff
- [ ] **CONN-02**: System buffers outgoing messages during disconnect and sends on reconnect
- [ ] **CONN-03**: System synchronizes session state after reconnection
- [ ] **CONN-04**: System displays connection status indicators (connected/reconnecting/offline/syncing)
- [ ] **CONN-05**: Claude continues working during mobile disconnect, user catches up on reconnect

### Notification System

- [ ] **NOTF-01**: System sends push notifications for critical events (errors, approval needed)
- [ ] **NOTF-02**: User can configure notification preferences per project thread
- [ ] **NOTF-03**: System categorizes notifications by urgency tier (urgent/important/informational/silent)
- [ ] **NOTF-04**: User can enable/disable notifications per event type (errors vs progress vs completions)

### Advanced Features

- [ ] **ADV-01**: System syncs user's ~/.claude/agents/ custom commands to mobile
- [ ] **ADV-02**: User can invoke custom slash commands from Signal with autocomplete
- [ ] **ADV-03**: User can activate emergency fix mode for streamlined production incident response
- [ ] **ADV-04**: Emergency fix mode pre-approves safe operations and auto-commits changes

### Testing & Quality (TDD Framework)

- [ ] **TEST-01**: All core components have unit tests with >80% coverage
- [ ] **TEST-02**: Integration tests verify Signal ↔ Claude Code communication flows
- [ ] **TEST-03**: Tests validate rate limiting and message queue behavior under load
- [ ] **TEST-04**: Tests verify session persistence and crash recovery scenarios
- [ ] **TEST-05**: Tests simulate network drops and verify reconnection behavior
- [ ] **TEST-06**: End-to-end tests validate complete user workflows (start → delegate → approve → complete)
- [ ] **TEST-07**: Tests run automatically in CI/CD pipeline before merges
- [ ] **TEST-08**: Test fixtures provide realistic Signal message payloads and Claude responses

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Voice Interface

- **VOICE-01**: User can send voice messages with task descriptions
- **VOICE-02**: System transcribes voice input using speech recognition
- **VOICE-03**: System reads progress updates aloud for hands-free monitoring
- **VOICE-04**: User can configure voice agent preferences (speed, voice type)

### Session Management Enhancements

- **SESS-07**: User can search session history across all projects
- **SESS-08**: User can view session timeline with timestamps
- **SESS-09**: System archives old sessions after configurable period

### Code Display Enhancements

- **CODE-07**: User can zoom and pan on code attachments
- **CODE-08**: System highlights relevant code sections in long files
- **CODE-09**: User can comment on specific code lines

### Collaboration

- **COLLAB-01**: Multiple users can observe same Claude session
- **COLLAB-02**: Users can hand off session control between devices
- **COLLAB-03**: System logs all user interactions for audit trail

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| **Full IDE on mobile** | Mobile keyboards terrible for coding - defeats purpose of AI assistant. Users should delegate to Claude, not type code on phone. |
| **Real-time keystroke streaming** | Excessive notifications, battery drain, cellular data waste. Sentence-level streaming sufficient. |
| **Video/screen sharing** | High bandwidth, tiny screen makes text unreadable. VNC/TeamViewer exist for this. Structured updates beat raw screen access. |
| **Inline file editing in Signal** | Signal isn't code editor - no git integration, syntax validation, IDE features. Creates shadow edits. |
| **Automatic permission approval** | Defeats monitoring/approval use case. Users specifically want review. Alternative: approval profiles with trust levels. |
| **GitHub/GitLab integration** | Adds external service dependency, auth complexity. Claude Code works with local repos. Users push to remote manually. |
| **Multi-device sync** | Edge case - most users have one phone. Adds encryption key management complexity. |
| **Always-on daemon** | User explicitly starts/stops service. Manual control simpler than 24/7 background process. |
| **Wake-on-demand** | Desktop must be manually running. No remote wake capabilities - adds complexity. |
| **Web viewer interface** | Signal-only for v1.0. No separate web UI - keeps architecture simpler. |
| **Custom notification sounds** | Polish feature not adoption driver. Defer to v2+ if requested. |

## Traceability

Which phases cover which requirements. Updated by create-roadmap.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 1 | Complete |
| INFRA-02 | Phase 1 | Complete |
| INFRA-03 | Phase 1 | Complete |
| INFRA-04 | Phase 1 | Complete |
| INFRA-05 | Phase 1 | Complete |
| SESS-01 | Phase 2 | Complete |
| SESS-02 | Phase 2 | Complete |
| SESS-03 | Phase 2 | Complete |
| SESS-04 | Phase 2 | Complete |
| SESS-05 | Phase 2 | Complete |
| SESS-06 | Phase 2 | Complete |
| CLDE-01 | Phase 3 | Complete |
| CLDE-02 | Phase 3 | Complete |
| CLDE-03 | Phase 3 | Complete |
| CLDE-04 | Phase 3 | Complete |
| CLDE-05 | Phase 3 | Complete |
| CLDE-06 | Phase 3 | Complete |
| PROJ-01 | Phase 4 | Complete |
| PROJ-02 | Phase 4 | Complete |
| PROJ-03 | Phase 4 | Complete |
| PROJ-04 | Phase 4 | Complete |
| PROJ-05 | Phase 4 | Complete |
| PERM-01 | Phase 5 | Pending |
| PERM-02 | Phase 5 | Pending |
| PERM-03 | Phase 5 | Pending |
| PERM-04 | Phase 5 | Pending |
| PERM-05 | Phase 5 | Pending |
| PERM-06 | Phase 5 | Pending |
| PERM-07 | Phase 5 | Pending |
| CODE-01 | Phase 6 | Pending |
| CODE-02 | Phase 6 | Pending |
| CODE-03 | Phase 6 | Pending |
| CODE-04 | Phase 6 | Pending |
| CODE-05 | Phase 6 | Pending |
| CODE-06 | Phase 6 | Pending |
| CONN-01 | Phase 7 | Pending |
| CONN-02 | Phase 7 | Pending |
| CONN-03 | Phase 7 | Pending |
| CONN-04 | Phase 7 | Pending |
| CONN-05 | Phase 7 | Pending |
| NOTF-01 | Phase 8 | Pending |
| NOTF-02 | Phase 8 | Pending |
| NOTF-03 | Phase 8 | Pending |
| NOTF-04 | Phase 8 | Pending |
| ADV-01 | Phase 9 | Pending |
| ADV-02 | Phase 9 | Pending |
| ADV-03 | Phase 9 | Pending |
| ADV-04 | Phase 9 | Pending |
| TEST-01 | Phase 10 | Pending |
| TEST-02 | Phase 10 | Pending |
| TEST-03 | Phase 10 | Pending |
| TEST-04 | Phase 10 | Pending |
| TEST-05 | Phase 10 | Pending |
| TEST-06 | Phase 10 | Pending |
| TEST-07 | Phase 10 | Pending |
| TEST-08 | Phase 10 | Pending |

**Coverage:**
- v1 requirements: 56 total
- Mapped to phases: 56
- Unmapped: 0 ✓

---
*Requirements defined: 2026-01-25*
*Last updated: 2026-01-25 after initial definition*
