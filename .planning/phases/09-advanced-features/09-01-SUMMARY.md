---
phase: 09-advanced-features
plan: 01
subsystem: custom-commands
tags: [watchdog, python-frontmatter, sqlite, file-monitoring, custom-agents]

# Dependency graph
requires:
  - phase: 02-session-management
    provides: SQLite persistence patterns with WAL mode
  - phase: 04-multi-project
    provides: Application Support directory pattern
provides:
  - CustomCommandRegistry with SQLite persistence for command metadata
  - CommandSyncer for real-time file system monitoring of ~/.claude/agents/
  - Frontmatter parsing for .md command files
affects: [09-02-custom-command-execution]

# Tech tracking
tech-stack:
  added:
    - watchdog>=6.0.0 (file system monitoring)
    - python-frontmatter>=1.0.0 (markdown frontmatter parsing)
  patterns:
    - File system event handling with asyncio.run_coroutine_threadsafe
    - YAML frontmatter parsing for command metadata
    - Event loop passing for thread-safe async calls

key-files:
  created:
    - src/custom_commands/__init__.py
    - src/custom_commands/registry.py
    - src/custom_commands/syncer.py
    - tests/test_custom_command_registry.py
    - tests/test_custom_command_syncer.py
    - tests/test_custom_command_integration.py
  modified:
    - requirements.txt

key-decisions:
  - "SQLite with WAL mode for custom_commands.db (Phase 2 pattern)"
  - "JSON metadata storage for flexibility (no schema migrations)"
  - "Idempotent operations for safe retry logic"
  - "asyncio.run_coroutine_threadsafe for thread-safe async from watchdog"
  - "Event loop passed to CommandSyncer.start() for test compatibility"
  - "Filename stem used for deletion (file content unavailable)"

patterns-established:
  - "Watchdog Observer with asyncio integration via run_coroutine_threadsafe"
  - "Frontmatter parsing with python-frontmatter library"
  - "Real-time file monitoring with .md extension filtering"

# Metrics
duration: 5min
completed: 2026-01-28
---

# Phase 09 Plan 01: Custom Command Sync Summary

**Real-time ~/.claude/agents/ monitoring with SQLite registry, watchdog file system events, and frontmatter parsing**

## Performance

- **Duration:** 5 minutes
- **Started:** 2026-01-28T16:23:19Z
- **Completed:** 2026-01-28T16:28:40Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- CustomCommandRegistry with SQLite persistence (WAL mode, UTC timestamps, idempotent operations)
- CommandSyncer detects file creation/modification/deletion in real-time using watchdog
- Frontmatter parsing extracts command name, description, and parameters from .md files
- Integration tests verify end-to-end file → registry flow
- 25 tests passing (11 registry + 9 syncer + 5 integration)

## Task Commits

Each task was committed atomically following TDD (RED-GREEN-REFACTOR):

1. **Task 1: CustomCommandRegistry with TDD**
   - `591c4db` (test: add failing tests for CustomCommandRegistry)
   - `4374a6f` (feat: implement CustomCommandRegistry with SQLite persistence)

2. **Task 2: CommandSyncer with TDD**
   - `93b22fc` (test: add failing tests for CommandSyncer)
   - `220cd00` (feat: implement CommandSyncer with watchdog file monitoring)

3. **Task 3: Integration test for syncer + registry**
   - `686b608` (test: add integration tests for syncer + registry)

## Files Created/Modified

**Created:**
- `src/custom_commands/__init__.py` - Package exports for CustomCommandRegistry and CommandSyncer
- `src/custom_commands/registry.py` - SQLite-backed command registry with CRUD operations
- `src/custom_commands/syncer.py` - Watchdog-based file system monitor for ~/.claude/agents/
- `tests/test_custom_command_registry.py` - TDD tests for registry (11 tests)
- `tests/test_custom_command_syncer.py` - TDD tests for syncer (9 tests)
- `tests/test_custom_command_integration.py` - Integration tests (5 tests)

**Modified:**
- `requirements.txt` - Added watchdog and python-frontmatter dependencies

## Decisions Made

**1. asyncio.run_coroutine_threadsafe for thread-safe async calls**
- Watchdog observer runs in separate thread, can't use asyncio.create_task directly
- run_coroutine_threadsafe schedules coroutine in main event loop
- Event loop passed to CommandSyncer.start() for test compatibility

**2. Filename stem for deletion detection**
- Deleted file content unavailable for parsing
- Use file_path.stem (filename without .md extension) as command name
- Assumes convention: filename matches command name field

**3. Idempotent add_command for updates**
- CommandSyncer calls add_command for both create and modify events
- Uses SQLite ON CONFLICT DO UPDATE for upsert behavior
- Simplifies syncer logic (single method for both operations)

**4. ~/.claude/agents/ directory creation**
- Syncer creates directory if missing (mkdir parents=True, exist_ok=True)
- Prevents FileNotFoundError on first run
- Matches ~/.claude/ pattern from existing codebase

## Deviations from Plan

None - plan executed exactly as written. All tasks completed via TDD (RED-GREEN-REFACTOR) without deviations.

## Issues Encountered

**1. RuntimeError: no running event loop**
- **Issue:** asyncio.create_task() called from watchdog observer thread
- **Solution:** Use asyncio.run_coroutine_threadsafe with explicit event loop reference
- **Impact:** Event loop must be passed to CommandSyncer.start() method

**2. Test call args access pattern**
- **Issue:** AsyncMock call args accessed as call[0][0] but should handle kwargs
- **Solution:** Use `call.kwargs.get("name") or call.args[0]` for flexible access
- **Impact:** Tests robust to positional vs keyword argument calls

**3. YAML float parsing**
- **Issue:** YAML parses "1.0" as float 1.0, not string "1.0"
- **Solution:** Adjusted test assertions to expect float type
- **Impact:** None - metadata stored as-is from frontmatter parsing

## User Setup Required

None - no external service configuration required.

**Database creation:** `~/Library/Application Support/claude-signal-bot/custom_commands.db` created automatically on first registry initialization.

**Agents directory:** `~/.claude/agents/` created automatically on first syncer start if missing. User already has 22 custom command files in this directory.

## Next Phase Readiness

**Ready for 09-02 (Custom Command Execution):**
- Registry provides `list_commands()`, `get_command(name)` for command discovery
- Syncer keeps registry synchronized in real-time
- Command metadata includes name, description, parameters for execution context

**Integration points:**
- SessionCommands can query registry for available custom commands
- ClaudeOrchestrator can load command metadata for prompt context
- Command execution will need parameter parsing and agent delegation

**No blockers or concerns.**

---
*Phase: 09-advanced-features*
*Completed: 2026-01-28*
