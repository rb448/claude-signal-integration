# Architecture Research

**Domain:** Remote Development Systems with Chat Interfaces
**Researched:** 2026-01-25
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                         Mobile Client Layer                       │
│  ┌────────────┐                                                   │
│  │   Signal   │ ◄──── Commands from user                          │
│  │   Mobile   │ ────► Notifications, results, progress            │
│  └─────┬──────┘                                                   │
└────────┼─────────────────────────────────────────────────────────┘
         │ (Signal API - bidirectional messaging)
         │
┌────────┼─────────────────────────────────────────────────────────┐
│        ▼              Desktop Service Layer (macOS)               │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │              Service Daemon (launchd managed)             │    │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────┐  │    │
│  │  │ Signal Client  │  │ Message Queue  │  │Session Mgr │  │    │
│  │  │   (WebSocket)  │  │   (In-Memory)  │  │  Registry  │  │    │
│  │  └────────┬───────┘  └───────┬────────┘  └──────┬─────┘  │    │
│  └───────────┼──────────────────┼──────────────────┼────────┘    │
│              │                  │                  │              │
│              ▼                  ▼                  ▼              │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │              Session Manager (Process Orchestrator)        │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │   │
│  │  │  Project A  │  │  Project B  │  │  Project C  │       │   │
│  │  │   Session   │  │   Session   │  │   Session   │       │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘       │   │
│  └─────────┼─────────────────┼─────────────────┼─────────────┘   │
└────────────┼─────────────────┼─────────────────┼─────────────────┘
             │                 │                 │
             ▼                 ▼                 ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Claude API Session Layer                       │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐             │
│  │  Claude    │    │  Claude    │    │  Claude    │             │
│  │  Session 1 │    │  Session 2 │    │  Session 3 │             │
│  │  (API)     │    │  (API)     │    │  (API)     │             │
│  └────────────┘    └────────────┘    └────────────┘             │
│  (Independent conversation contexts per project)                  │
└──────────────────────────────────────────────────────────────────┘
             │                 │                 │
             ▼                 ▼                 ▼
┌──────────────────────────────────────────────────────────────────┐
│                      Persistence Layer                            │
│  ┌─────────────────────────────────────────────────────┐         │
│  │              Session State Store (File-based)        │         │
│  │  ~/Library/Application Support/SignalClaudeBot/     │         │
│  │  ├── sessions/                                       │         │
│  │  │   ├── project-a.json   (session metadata)        │         │
│  │  │   ├── project-b.json                             │         │
│  │  │   └── project-c.json                             │         │
│  │  ├── conversations/        (message history)        │         │
│  │  └── config.json          (service configuration)    │         │
│  └─────────────────────────────────────────────────────┘         │
└──────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| **Service Daemon** | Long-running background process managing lifecycle, crash recovery, and inter-process communication | macOS launchd-managed Node.js process using PM2 for auto-restart |
| **Signal Client** | Bidirectional message transport with Signal API | WebSocket connection with reconnection logic and message queue |
| **Message Queue** | Buffer incoming commands and outgoing notifications; handles ordering and backpressure | In-memory queue (asyncio.Queue pattern) with persistence fallback |
| **Session Manager** | Spawn/resume Claude sessions, maintain project-to-session mapping, enforce isolation | Process orchestrator spawning child processes per project |
| **Session State Store** | Persist session metadata, conversation history, and configuration across restarts | JSON files in Application Support directory with atomic writes |
| **Progress Streamer** | Real-time updates from Claude to Signal during long-running operations | Server-Sent Events (SSE) or WebSocket streaming with message chunking |
| **Code Formatter** | Render code, diffs, and file changes for mobile display | Syntax-aware formatter with inline/summary/attachment modes |

## Recommended Project Structure

```
signal-claude-bot/
├── src/
│   ├── daemon/              # Main service process
│   │   ├── index.ts         # Entry point, launchd lifecycle
│   │   ├── service.ts       # Core daemon logic
│   │   └── health.ts        # Health check endpoint
│   ├── signal/              # Signal integration
│   │   ├── client.ts        # WebSocket connection to Signal API
│   │   ├── message-queue.ts # Queue for incoming/outgoing messages
│   │   └── formatter.ts     # Message formatting for mobile
│   ├── session/             # Claude session management
│   │   ├── manager.ts       # Session lifecycle and registry
│   │   ├── spawner.ts       # Process spawning for Claude API
│   │   ├── state.ts         # Session state persistence
│   │   └── isolation.ts     # Multi-project isolation logic
│   ├── api/                 # Claude API integration
│   │   ├── client.ts        # Claude API wrapper
│   │   ├── streaming.ts     # Progress streaming handler
│   │   └── context.ts       # Conversation context management
│   ├── display/             # Code display system
│   │   ├── code-formatter.ts   # Syntax highlighting, wrapping
│   │   ├── diff-renderer.ts    # Git diff formatting
│   │   └── attachment-builder.ts # File attachments
│   ├── persistence/         # State storage
│   │   ├── session-store.ts    # Session metadata persistence
│   │   ├── conversation-store.ts # Message history
│   │   └── config-store.ts     # Configuration management
│   └── shared/              # Shared utilities
│       ├── logger.ts        # Structured logging
│       ├── errors.ts        # Error types and handlers
│       └── types.ts         # TypeScript type definitions
├── config/
│   ├── com.signal-claude.daemon.plist  # launchd configuration
│   └── default-config.json             # Default service settings
├── scripts/
│   ├── install-daemon.sh    # Install service to launchd
│   ├── uninstall-daemon.sh  # Remove service from launchd
│   └── health-check.sh      # Service health monitoring
└── tests/
    ├── integration/         # End-to-end tests
    └── unit/                # Component tests
```

### Structure Rationale

- **daemon/:** Service entry point and lifecycle management. Handles macOS-specific concerns (launchd, process management).
- **signal/:** Isolates Signal API integration. WebSocket client can be swapped for other messaging platforms.
- **session/:** Core business logic for managing concurrent Claude sessions. Enforces project isolation.
- **api/:** Claude API wrapper. Abstracts API details and handles streaming responses.
- **display/:** Mobile-specific formatting logic. Converts code and diffs to Signal-friendly format.
- **persistence/:** All state storage in one place. File-based for simplicity, easily swappable for database.

## Architectural Patterns

### Pattern 1: Frontend-Backend Split with RPC

**What:** Separate the service daemon (backend) from the Signal messaging interface (frontend). Backend hosts active sessions and provides data via RPC/JSON protocol.

**When to use:** When the messaging client and session management have different lifecycles or need to run on different machines/processes.

**Trade-offs:**
- **Pros:** Clean separation of concerns, easier to test, supports remote messaging clients, session persistence independent of messaging transport.
- **Cons:** Additional RPC overhead, more complex error handling across process boundaries.

**Example:**
```typescript
// Backend: Session Manager exposes RPC interface
class SessionManagerBackend {
  private sessions: Map<string, ClaudeSession> = new Map();

  async executeCommand(projectId: string, command: string): Promise<void> {
    const session = this.sessions.get(projectId) || await this.createSession(projectId);
    return session.execute(command);
  }

  async getSessionState(projectId: string): Promise<SessionState> {
    const session = this.sessions.get(projectId);
    return session?.getState() || null;
  }
}

// Frontend: Signal client calls backend via RPC
class SignalFrontend {
  private backend: RPCClient<SessionManagerBackend>;

  async handleIncomingMessage(msg: SignalMessage): Promise<void> {
    const projectId = this.resolveProject(msg);
    await this.backend.call('executeCommand', projectId, msg.text);
  }
}
```

### Pattern 2: Producer-Consumer Queue with WebSocket

**What:** Use a producer-consumer pattern where a producer checks for new messages via WebSocket and creates tasks for registered commands that consumers work off.

**When to use:** When message processing has variable latency and you need to keep the messaging interface responsive.

**Trade-offs:**
- **Pros:** Decouples message receipt from processing, handles backpressure naturally, enables parallel processing of independent commands.
- **Cons:** Requires careful queue size management, adds complexity for ordered operations, needs dead-letter queue for failures.

**Example:**
```typescript
// Producer: Signal WebSocket connection
class SignalProducer {
  private messageQueue: AsyncQueue<SignalMessage>;

  async connect(): Promise<void> {
    this.ws.on('message', (msg: SignalMessage) => {
      this.messageQueue.enqueue(msg);
    });
  }
}

// Consumer: Process messages from queue
class MessageConsumer {
  private messageQueue: AsyncQueue<SignalMessage>;
  private sessionManager: SessionManager;

  async run(): Promise<void> {
    while (true) {
      const msg = await this.messageQueue.dequeue();
      try {
        await this.processMessage(msg);
      } catch (error) {
        await this.handleError(msg, error);
      }
    }
  }
}
```

### Pattern 3: Session State Persistence with Atomic Writes

**What:** Store session metadata and conversation history in JSON files with atomic write operations to prevent corruption during crashes.

**When to use:** For persisting session state across daemon restarts without requiring a database.

**Trade-offs:**
- **Pros:** Simple, no external dependencies, human-readable for debugging, suitable for moderate session counts.
- **Cons:** Not suitable for high-frequency writes, manual management of concurrent access, limited query capabilities.

**Example:**
```typescript
class SessionStore {
  private storePath: string = '~/Library/Application Support/SignalClaudeBot/sessions';

  async saveSession(projectId: string, state: SessionState): Promise<void> {
    const filePath = path.join(this.storePath, `${projectId}.json`);
    const tempPath = `${filePath}.tmp`;

    // Write to temp file first (atomic operation)
    await fs.writeFile(tempPath, JSON.stringify(state, null, 2));

    // Atomic rename (ensures consistency even during crash)
    await fs.rename(tempPath, filePath);
  }

  async loadSession(projectId: string): Promise<SessionState | null> {
    const filePath = path.join(this.storePath, `${projectId}.json`);
    try {
      const data = await fs.readFile(filePath, 'utf8');
      return JSON.parse(data);
    } catch (error) {
      if (error.code === 'ENOENT') return null;
      throw error;
    }
  }
}
```

### Pattern 4: Tenant Isolation via Process Spawning

**What:** Spawn independent Claude API client processes for each project, ensuring complete state isolation between concurrent sessions.

**When to use:** When you need strong isolation guarantees between projects and can tolerate the overhead of multiple processes.

**Trade-offs:**
- **Pros:** Complete memory isolation, crash in one session doesn't affect others, simpler state management per process, enforces API rate limiting per project.
- **Cons:** Higher memory overhead, more complex inter-process communication, slower cold-start for new sessions.

**Example:**
```typescript
class SessionManager {
  private processes: Map<string, ChildProcess> = new Map();

  async spawnSession(projectId: string, workingDir: string): Promise<void> {
    const childProcess = spawn('claude-api-client', [
      '--project-id', projectId,
      '--working-dir', workingDir,
      '--ipc-socket', `/tmp/signal-claude-${projectId}.sock`
    ]);

    this.processes.set(projectId, childProcess);

    // Handle crashes and auto-restart
    childProcess.on('exit', (code) => {
      if (code !== 0) {
        this.handleCrash(projectId);
      }
    });
  }

  private async handleCrash(projectId: string): Promise<void> {
    // Abort restart if last crash was <60s ago (prevent restart loops)
    const lastCrash = this.crashTimestamps.get(projectId);
    if (lastCrash && Date.now() - lastCrash < 60000) {
      await this.notifyUser(projectId, 'Session crashed repeatedly, manual intervention needed');
      return;
    }

    this.crashTimestamps.set(projectId, Date.now());
    await this.spawnSession(projectId, this.getWorkingDir(projectId));
  }
}
```

### Pattern 5: Server-Sent Events for Progress Streaming

**What:** Use SSE (Server-Sent Events) to stream real-time progress updates from long-running Claude operations to Signal.

**When to use:** When you need unidirectional server-to-client streaming for progress updates without the overhead of WebSockets.

**Trade-offs:**
- **Pros:** Simpler than WebSockets for one-way streaming, automatic reconnection, works over HTTP, lower overhead.
- **Cons:** Unidirectional only (need separate channel for commands), less efficient than WebSockets for bidirectional needs.

**Example:**
```typescript
class ProgressStreamer {
  async streamToSignal(projectId: string, stream: ReadableStream): Promise<void> {
    for await (const chunk of stream) {
      // Format progress update for mobile
      const formatted = this.formatProgress(chunk);

      // Send to Signal (non-blocking)
      await this.signalClient.sendMessage(projectId, formatted);

      // Optional: throttle updates to avoid overwhelming mobile
      await this.throttle(100); // 100ms between updates
    }
  }

  private formatProgress(chunk: ProgressChunk): string {
    if (chunk.type === 'tool_call') {
      return `🔧 ${chunk.tool}: ${chunk.description}`;
    } else if (chunk.type === 'completion') {
      return `✓ ${chunk.summary}`;
    } else if (chunk.type === 'error') {
      return `✗ Error: ${chunk.message}`;
    }
    return chunk.text;
  }
}
```

## Data Flow

### Request Flow (Command from Mobile)

```
[User sends command via Signal Mobile]
    ↓
[Signal API] → WebSocket → [Signal Client]
    ↓
[Message Queue] (enqueue command)
    ↓
[Message Consumer] (dequeue, process)
    ↓
[Session Manager] (resolve or create session for project)
    ↓
[Claude API Client] (execute command in project context)
    ↓ (streaming response)
[Progress Streamer] (format for mobile)
    ↓
[Signal Client] → WebSocket → [Signal API]
    ↓
[User receives updates on Signal Mobile]
```

### State Management Flow

```
[Daemon Starts]
    ↓
[Session Store] → load all persisted sessions → [Session Manager]
    ↓
[Session Manager] (rebuilds session registry)
    ↓
[For each project with active session]
    ↓
[Spawn Claude API Client Process]
    ↓
[Restore conversation context from disk]
    ↓
[Ready to receive commands]

(During operation)
    ↓
[Session State Change] (new message, context update)
    ↓
[Session Store] (atomic write to disk)
```

### Crash Recovery Flow

```
[Daemon Process Crashes or System Restart]
    ↓
[launchd] (detects crash, waits backoff period)
    ↓
[launchd] (restarts daemon process)
    ↓
[Daemon Init] → [Session Store] (load persisted state)
    ↓
[Session Manager] (rebuild session registry)
    ↓
[For each project]
    ↓
[Check last crash timestamp]
    ↓
[If < 60s ago] → Abort restart, notify user
[If > 60s ago] → Spawn new Claude session, restore context
    ↓
[Signal Client] (reconnect WebSocket with backoff)
    ↓
[Resume normal operation]
```

### Multi-Project Isolation

```
[Incoming Message from Signal]
    ↓
[Tenant Resolution] (extract project ID from message context)
    ↓
[Session Registry Lookup] (find or create session for project)
    ↓
[Process-Level Isolation]
    │
    ├─► [Project A Process]
    │   ├── Working Dir: ~/projects/project-a
    │   ├── Session State: /sessions/project-a.json
    │   └── IPC Socket: /tmp/signal-claude-project-a.sock
    │
    ├─► [Project B Process]
    │   ├── Working Dir: ~/projects/project-b
    │   ├── Session State: /sessions/project-b.json
    │   └── IPC Socket: /tmp/signal-claude-project-b.sock
    │
    └─► [Project C Process]
        ├── Working Dir: ~/projects/project-c
        ├── Session State: /sessions/project-c.json
        └── IPC Socket: /tmp/signal-claude-project-c.sock

(No shared state between processes - complete isolation)
```

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1-5 projects | Single daemon process, in-memory queue, file-based persistence is sufficient. SSE for progress streaming. |
| 5-20 projects | Consider PM2 cluster mode for daemon (load balancing), Redis for message queue (persistence), separate process per active session. |
| 20-100 projects | Database-backed session store (PostgreSQL/SQLite), connection pooling for Claude API, implement session timeouts and cleanup, horizontal scaling with multiple daemon instances. |
| 100+ projects | Database-per-tenant or schema-per-tenant for session isolation, distributed message queue (RabbitMQ/Kafka), session affinity with load balancer, auto-scaling based on active sessions. |

### Scaling Priorities

1. **First bottleneck:** Message queue saturation when multiple projects send commands simultaneously. **Fix:** Move from in-memory queue to Redis with persistence and backpressure handling.

2. **Second bottleneck:** File I/O contention when many sessions persist state concurrently. **Fix:** Batch state updates, implement write coalescing, or migrate to database with connection pooling.

3. **Third bottleneck:** Claude API rate limits with many concurrent projects. **Fix:** Implement per-project rate limiting, queue commands during rate limit windows, use exponential backoff.

## Anti-Patterns

### Anti-Pattern 1: Shared State Between Sessions

**What people do:** Store session state in a shared global object or singleton, using a tenant_id field to distinguish projects.

**Why it's wrong:**
- Memory leaks from one session affect all sessions
- Race conditions when multiple sessions update shared state
- Crash in one session can corrupt state for all projects
- Difficult to enforce API rate limits per project

**Do this instead:** Use process-level isolation with independent Claude API client processes per project. Each process has its own memory space, state, and lifecycle. Communicate via IPC (sockets, pipes) rather than shared memory.

### Anti-Pattern 2: Synchronous Message Processing

**What people do:** Process each incoming Signal message synchronously, blocking the WebSocket connection until Claude responds.

**Why it's wrong:**
- Long-running Claude operations block all other messages
- WebSocket connection can timeout during long operations
- No way to handle concurrent commands from multiple projects
- Poor user experience (no progress updates during execution)

**Do this instead:** Use producer-consumer pattern with message queue. Producer immediately acknowledges message receipt and enqueues for processing. Consumer processes messages asynchronously and streams progress updates via separate channel (SSE or status messages).

### Anti-Pattern 3: Direct File Write Without Atomicity

**What people do:** Directly write session state to JSON files using `fs.writeFile()` without atomic guarantees.

**Why it's wrong:**
- Daemon crash during write corrupts state file
- Partial writes leave invalid JSON
- No way to recover from corrupted state
- Silent data loss during system crashes

**Do this instead:** Write to temporary file first, then atomic rename. Use write-ahead logging for critical operations. Implement checksum verification on load to detect corruption early.

### Anti-Pattern 4: No Crash Restart Backoff

**What people do:** Automatically restart crashed sessions immediately without checking crash frequency.

**Why it's wrong:**
- Persistent errors cause infinite restart loops
- Wastes system resources on broken sessions
- Floods logs with repeated crashes
- Prevents investigation of root cause

**Do this instead:** Track crash timestamps per session. If last crash was <60 seconds ago, abort automatic restart and notify user. Implement exponential backoff for restart attempts. Log detailed crash information for debugging.

### Anti-Pattern 5: Blocking on Daemon Lifecycle Hooks

**What people do:** Put long-running initialization or cleanup logic in daemon start/stop handlers without timeout.

**Why it's wrong:**
- launchd expects daemons to respond to lifecycle signals quickly
- System may force-kill daemon if it doesn't respond
- Graceful shutdown never completes
- Resource leaks from incomplete cleanup

**Do this instead:** Use async initialization with health check endpoint. Respond to SIGTERM quickly (< 5 seconds), then trigger graceful shutdown in background. Save critical state immediately, defer non-critical cleanup.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| **Signal API** | WebSocket connection with reconnection logic | Maintain single connection per daemon. Use ControlMaster pattern to avoid re-authentication on reconnect. Implement exponential backoff on connection failures. |
| **Claude API** | REST API with streaming responses | One client instance per project session. Handle rate limits with exponential backoff. Stream responses via SSE for real-time updates. Persist conversation context on each turn. |
| **macOS launchd** | Launch daemon with plist configuration | Register as LaunchDaemon (system-wide) or LaunchAgent (per-user). Use `KeepAlive` with crash tracking. Configure `StandardOutPath` and `StandardErrorPath` for logging. |
| **File System** | Application Support directory for state | `~/Library/Application Support/SignalClaudeBot/` for user-scoped data. Use atomic writes for state files. Implement file locking for concurrent access. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| **Daemon ↔ Session Manager** | Direct function calls (same process) | Session Manager is core module within daemon process. Synchronous API for session lifecycle operations. |
| **Session Manager ↔ Claude API Process** | IPC via Unix domain sockets | Each project session runs in separate process. Communicate via JSON-RPC over Unix sockets. Unidirectional command flow (manager → process). |
| **Signal Client ↔ Message Queue** | In-memory queue (asyncio pattern) | Producer-consumer pattern. Queue sits between WebSocket listener and message processor. Backpressure handling when queue fills. |
| **Progress Streamer ↔ Signal Client** | Event emitter pattern | Session emits progress events. Streamer subscribes and formats for mobile. Non-blocking sends to avoid backpressure on session. |
| **Session Store ↔ File System** | Direct file I/O with atomic writes | Abstraction layer over file operations. Implements retry logic and corruption detection. Can be swapped for database later. |

## macOS Service Deployment Patterns

### launchd Configuration

Modern macOS services use launchd for process lifecycle management. The service daemon should be designed as launch-on-demand compliant.

**Key launchd patterns:**
- Use `bootstrap` command (not legacy `load`) for modern deployment
- Configure `KeepAlive` with crash detection to auto-restart on failure
- Set appropriate `ThrottleInterval` to prevent restart loops (60 seconds recommended)
- Use `StandardOutPath` and `StandardErrorPath` for logging
- Configure `UserName` if running as specific user (agents run as logged-in user, daemons as root or specified user)

**Process management:**
- launchd handles backgrounding; do NOT daemonize in code (no fork/setsid)
- Respond to SIGTERM within 5 seconds for clean shutdown
- Use `RunAtLoad` for services that should start immediately
- Implement health check endpoint for monitoring

**File structure:**
```
/Library/LaunchDaemons/com.signal-claude.daemon.plist      # System-wide daemon
~/Library/LaunchAgents/com.signal-claude.agent.plist       # Per-user agent
```

### Daemon vs Agent Decision

**Use LaunchDaemon when:**
- Service needs to run system-wide, independent of logged-in users
- No GUI access required
- Runs as root or specific system user
- Example: Signal API client that serves all users

**Use LaunchAgent when:**
- Service is user-specific
- Needs access to user's files and preferences
- Coordinates with user session
- Example: Per-user Signal bot with user-specific projects

**Hybrid approach (recommended for this project):**
- LaunchAgent for user-scoped Signal bot
- Coordinates with user's Signal account and project directories
- Runs in user context for file access permissions
- Automatically starts when user logs in

### Crash Recovery Strategy

**Detection:**
- launchd detects process exit with non-zero code
- Waits ThrottleInterval before restart attempt
- Tracks restart frequency to prevent loops

**Recovery:**
1. launchd restarts daemon process
2. Daemon initialization loads persisted session state
3. Session Manager rebuilds session registry from disk
4. For each active session:
   - Check last crash timestamp
   - If < 60s ago: abort restart, notify user via Signal
   - If > 60s ago: spawn new Claude API process
   - Restore conversation context from persistence layer
5. Signal Client reconnects WebSocket with exponential backoff
6. Resume normal operation

**State persistence requirements:**
- Session metadata (project ID, working directory, last activity)
- Conversation context (message history, current task)
- Message queue state (pending commands)
- Configuration (user preferences, API keys)

All state must be persisted atomically to survive crashes at any point.

## Session Lifecycle Management

### Session States

```
[IDLE] → User sends first command
    ↓
[INITIALIZING] → Spawn Claude API process, restore context
    ↓
[ACTIVE] → Processing commands, streaming responses
    ↓
[IDLE] → No activity for timeout period (e.g., 30 minutes)
    ↓
[SUSPENDED] → Keep session metadata, release API resources
    ↓
[RESUMING] → User sends new command, restore from suspended
    ↓
[ACTIVE]

(Alternative paths)
[ACTIVE] → Explicit stop command
    ↓
[TERMINATING] → Graceful shutdown, persist state
    ↓
[TERMINATED] → Session removed from registry

[ACTIVE] → Crash detected
    ↓
[CRASHED] → Check recovery policy
    ↓
[RECOVERING] → Reload state, spawn new process
    ↓
[ACTIVE]
```

### Session Timeouts

- **Idle timeout:** 30 minutes of no activity → SUSPENDED state
- **Suspended timeout:** 24 hours suspended → TERMINATED state
- **Crash backoff:** 60 seconds between restart attempts
- **Health check interval:** 5 minutes per active session

### Context Management

Each session maintains:
1. **Conversation history:** Full message log for Claude API context
2. **Working directory:** Project root path
3. **Session metadata:** Creation time, last activity, command count
4. **Tool call history:** Track all file operations for rollback
5. **User preferences:** Project-specific settings (formatting, notification level)

**Context pruning:**
- Keep last 100 messages in active memory
- Older messages stored in conversation-store on disk
- On context limit: automatically summarize old messages
- Never lose data, just compact representation

## Code Display System

### Display Modes

**1. Inline Mode**
Best for: Short snippets (< 10 lines), syntax errors, single function changes

```
Format: Syntax-highlighted code block in Signal message
Example:
```typescript
function greet(name: string): string {
  return `Hello, ${name}!`;
}
```
```

**2. Summary Mode**
Best for: Medium changes (10-50 lines), multiple file changes, diffs

```
Format: File list + change summary + expandable details
Example:
📝 Modified 3 files:
  src/api/client.ts: Added error handling (23 lines)
  src/session/manager.ts: Fixed session cleanup (15 lines)
  tests/session.test.ts: Added recovery test (42 lines)

[Tap to view diffs]
```

**3. Attachment Mode**
Best for: Large changes (> 50 lines), full file content, binary files

```
Format: File attachment with metadata
Example:
📎 src/api/client.ts
   356 lines, +87 -23
   [Download file]
```

### Diff Rendering

**Unified diff format for mobile:**
```
src/api/client.ts
@@ -45,7 +45,12 @@ class APIClient {
   async request(endpoint: string): Promise<Response> {
-    return await fetch(endpoint);
+    try {
+      return await fetch(endpoint);
+    } catch (error) {
+      this.logger.error('Request failed', error);
+      throw new APIError(error.message);
+    }
   }
```

**Smart formatting:**
- Syntax highlighting for 10+ languages
- Line wrapping at 60 characters for mobile
- Collapse large unchanged sections (show first/last 5 lines)
- Color coding: green for additions, red for deletions
- Emoji indicators: ✅ success, ❌ error, ⚠️ warning, 🔧 tool call

## Sources

### Primary (HIGH confidence)
- [JetBrains Platform Debugger Architecture for Remote Development (2026)](https://blog.jetbrains.com/platform/2026/01/platform-debugger-architecture-redesign-for-remote-development-in-2026-1/) - Frontend-backend separation patterns
- [Apple Developer - Designing Daemons and Services](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/DesigningDaemons.html) - macOS daemon best practices
- [Zed SSH Remote Development](https://zed.dev/blog/remote-development) - Persistent daemon sessions
- [PM2 Cluster Mode Documentation](https://pm2.keymetrics.io/docs/usage/cluster-mode/) - Process management patterns

### Secondary (MEDIUM confidence)
- [How to Build a Chatbot: Components & Architecture in 2026](https://research.aimultiple.com/chatbot-architecture/) - Chatbot architecture overview
- [Real-Time UI Updates with SSE](https://www.codingwithmuhib.com/blogs/real-time-ui-updates-with-sse-simpler-than-websockets) - Progress streaming patterns
- [Multi-Tenant Database Architecture Patterns](https://www.bytebase.com/blog/multi-tenant-database-architecture-patterns-explained/) - Session isolation strategies
- [GitHub Copilot CLI - Enhanced Agents and Context Management (2026)](https://github.blog/changelog/2026-01-14-github-copilot-cli-enhanced-agents-context-management-and-new-ways-to-install/) - Concurrent session management
- [Lindy - Complete Guide to AI Agent Architecture in 2026](https://www.lindy.ai/blog/ai-agent-architecture) - AI agent state management

### Tertiary (LOW confidence)
- [signalbot Python package](https://pypi.org/project/signalbot/) - Producer-consumer pattern for Signal bots
- [Auto-recovery of crashed services with systemd](https://singlebrook.com/2017/10/23/auto-restart-crashed-service-systemd/) - Crash recovery patterns
- Community discussions on Signal webhook implementation

---
*Architecture research for: Remote Development Systems with Chat Interfaces*
*Researched: 2026-01-25*
*Valid until: 2026-02-25 (30 days - stable domain)*
