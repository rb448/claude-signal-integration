# Claude Code Signal Integration

## What This Is

A Signal bot that provides full mobile access to Claude Code sessions running on a desktop Mac, working with local file system directories. Enables starting new sessions, resuming existing work, giving commands, reviewing code changes, and managing multiple projects entirely from a mobile device through Signal's encrypted messaging platform.

## Core Value

Enable complete Claude Code functionality from mobile without requiring GitHub repos - users can continue development work with local directories while away from their desk.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] **Desktop Service** - Manually-started background service that runs on Mac and maintains connection to Signal
- [ ] **Signal Bot Integration** - Bidirectional communication bridge between Signal messages and Claude Code CLI
- [ ] **Session Management** - Ability to start new Claude Code sessions or resume existing sessions via Signal commands
- [ ] **Multi-Project Support** - Separate Signal threads map to different project directories, each maintaining independent Claude session state
- [ ] **Authentication** - Phone number verification to ensure only authorized user can send commands
- [ ] **Progress Streaming** - Real-time updates about Claude's actions sent as Signal messages (tool calls, file operations, etc.)
- [ ] **Configurable Notifications** - User-adjustable verbosity levels:
  - Real-time tool notifications (every Read, Edit, Write, Bash command)
  - Milestone updates only (major step completions)
  - Summary on request (silent until asked)
  - Approval gates (pause before destructive operations)
- [ ] **Code Display System** - Multiple formats for presenting code on mobile:
  - Inline formatted snippets for short code blocks
  - Plain-English summaries of changes
  - File attachments for full code review
- [ ] **Command Parity** - Full Claude Code command set accessible via Signal (not just monitoring)
- [ ] **Code Review Workflow** - View diffs, approve/reject changes, review commits from mobile
- [ ] **Connection Resilience** - Claude continues working if mobile connection drops; user catches up on reconnection
- [ ] **Message Threading** - Organize conversations by project using Signal's thread/group features
- [ ] **Mobile-First UX** - All interactions designed for usability on phone screen

### Out of Scope

- **GitHub-first workflow** - This is specifically for local directories, not GitHub repos
- **Always-on daemon** - User explicitly starts/stops service when needed, not 24/7 background process
- **Wake-on-demand** - Desktop must be manually running; no remote wake capabilities
- **Additional auth layers** - Relying on Signal E2E encryption + phone verification, no extra tokens/passphrases
- **Web viewer** - No separate web interface for code; all interaction through Signal
- **Multi-user support** - Single user (owner) only in v1.0
- **Desktop-to-mobile file sync** - Working with desktop files remotely, not syncing to mobile device

## Context

### Inspiration

Based on happy-coder's approach to mobile development via chat:
- GitHub integration patterns (commits, PRs, diffs) adapted for local files
- Message threading for project organization
- Progress streaming for visibility into Claude's work
- Mobile-first UX principles

### Use Cases

1. **Monitoring** - Started work from desktop, watch progress while commuting
2. **Delegation** - Give Claude new tasks to work on while away from desk
3. **Code Review** - Approve changes, review diffs, make commit decisions from phone
4. **Emergency Fixes** - Handle urgent bugs or time-sensitive changes when not at computer

### Technical Environment

- **Desktop**: macOS (user's development machine)
- **Mobile**: iOS/Android with Signal installed
- **Network**: Desktop must be on local network or have remote access configured
- **File System**: Working with local directories on desktop Mac

## Constraints

- **Manual Service Start**: Desktop service must be manually started by user before mobile access possible — no automatic/always-on operation
- **Desktop Availability**: Desktop Mac must be powered on and accessible (local network or VPN) for system to function
- **Signal Dependency**: Requires Signal's infrastructure and APIs; system unavailable if Signal is down
- **Phone Number Auth**: Security model tied to Signal phone number verification; changing numbers requires reconfiguration
- **Local File Access Only**: Desktop service can only access files on the desktop machine's file system
- **Single User**: v1.0 designed for single user (the owner); no multi-user or team collaboration features

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Signal over other chat platforms | E2E encryption built-in, phone-centric auth, good API support | — Pending |
| Separate threads per project | Natural context separation, clear conversation history per project | — Pending |
| Manual start service | Simpler than always-on daemon, gives user explicit control over when desktop is accessible | — Pending |
| Phone number verification | Leverages Signal's existing security, no additional auth infrastructure needed | — Pending |
| Keep working on disconnect | Don't halt progress due to mobile connection issues; resilient by default | — Pending |
| Multiple code display formats | Different contexts need different levels of detail (summary vs full code) | — Pending |
| Tech stack agnostic | Choose best fit based on Signal/Claude API support and async requirements during implementation | — Pending |

---
*Last updated: 2026-01-25 after initialization*
