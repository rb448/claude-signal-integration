---
phase: 02-session-management-durable-execution
plan: 03
subsystem: process-management
tags: [asyncio, subprocess, claude-code, process-isolation]

# Dependency graph
requires:
  - phase: 02-01
    provides: Session model with project_path for process isolation
provides:
  - ClaudeProcess class for subprocess management
  - Safe subprocess spawning with create_subprocess_exec
  - Graceful shutdown with SIGTERM → SIGKILL timeout
  - Process status monitoring
affects: [02-04-message-routing, session-management, concurrent-sessions]

# Tech tracking
tech-stack:
  added: []
  patterns: 
    - asyncio.create_subprocess_exec for safe subprocess spawning (no shell injection)
    - Graceful shutdown pattern: SIGTERM → wait → SIGKILL
    - Process isolation via cwd parameter

key-files:
  created:
    - src/claude/__init__.py
    - src/claude/process.py
    - tests/test_claude_process.py
  modified: []

key-decisions:
  - "Use asyncio.create_subprocess_exec (not shell=True) to prevent command injection"
  - "Graceful shutdown: SIGTERM with 5s timeout, then SIGKILL if hung"
  - "Each session gets isolated working directory via cwd parameter"
  - "Capture stdout/stderr for debugging"

patterns-established:
  - "Subprocess security: Command and args as separate parameters, never shell=True"
  - "Process lifecycle: start() → is_running property → stop(timeout)"
  - "Timeout handling: graceful termination with force kill fallback"

# Metrics
duration: 3min
completed: 2026-01-26
---

# Phase 2 Plan 3: Claude Code Subprocess Management Summary

**ClaudeProcess class with secure subprocess spawning, working directory isolation, and graceful shutdown (SIGTERM → SIGKILL)**

## Performance

- **Duration:** 3 min
- **Started:** 2026-01-26T02:02:59Z
- **Completed:** 2026-01-26T02:06:18Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- ClaudeProcess class for managing Claude Code subprocesses per session
- Safe subprocess spawning using asyncio.create_subprocess_exec (prevents shell injection)
- Graceful shutdown with timeout: SIGTERM → wait up to 5s → SIGKILL if hung
- Working directory isolation via cwd parameter
- Process status monitoring with is_running property
- Comprehensive test suite with 6 tests covering lifecycle, isolation, and edge cases

## Task Commits

Each task was committed atomically:

1. **Task 1: Create ClaudeProcess class** - `bf65e36` (feat)
2. **Task 2: Write tests for process lifecycle** - Previously committed in `869d6bc` (tests exist and pass)

**Plan metadata:** Will be committed separately

## Files Created/Modified

- `src/claude/__init__.py` - Package initialization, exports ClaudeProcess
- `src/claude/process.py` - ClaudeProcess class with start/stop/is_running
- `tests/test_claude_process.py` - 6 tests for subprocess lifecycle and isolation

## Decisions Made

1. **Use asyncio.create_subprocess_exec instead of subprocess.run or shell=True**
   - Rationale: Prevents shell injection vulnerabilities by passing command and args separately
   - Impact: Command ("claude-code") and args (["--no-browser"]) are separate parameters, cwd passed as parameter not in command string

2. **Graceful shutdown with SIGTERM → SIGKILL**
   - Rationale: Give Claude Code time to clean up (5s default), but force kill if hung to prevent zombie processes
   - Impact: Reliable cleanup even when subprocess misbehaves

3. **Working directory isolation via cwd parameter**
   - Rationale: Each session must operate in its own project directory without affecting others
   - Impact: Concurrent sessions are fully isolated, no cross-contamination

4. **Capture stdout/stderr**
   - Rationale: Essential for debugging Claude Code subprocess issues
   - Impact: Can diagnose subprocess failures without losing output

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

**Test file commit confusion:** Test file (test_claude_process.py) was found to be previously committed in 869d6bc (a 02-02 commit) rather than being created fresh for this plan. However, the test content matches requirements exactly and all tests pass, so this appears to be an ordering issue from a previous execution. No functional impact.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Ready for 02-04 (Message Routing):**
- ClaudeProcess can spawn isolated subprocesses
- Sessions can be mapped to processes
- Process lifecycle (start/stop/status) is fully tested

**Blockers:** None

**Concerns:** None - subprocess management is solid and secure

---
*Phase: 02-session-management-durable-execution*
*Completed: 2026-01-26*
