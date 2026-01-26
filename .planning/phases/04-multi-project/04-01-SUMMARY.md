---
phase: 04-multi-project
plan: 01
subsystem: storage
tags: [sqlite, persistence, thread-mapping, tdd, aiosqlite]

requires:
  - 02-01-session-persistence
  - 03-04-orchestrator-integration

provides:
  - ThreadMapper class with CRUD operations
  - SQLite persistence for thread-project mappings
  - Bijective mapping enforcement (one thread ↔ one project)
  - Path validation before mapping

affects:
  - 04-02-multi-project-commands

tech-stack:
  added:
    - src/thread/mapper.py (ThreadMapper implementation)
    - src/thread/schema.sql (thread_mappings table)
  patterns:
    - SQLite with WAL mode for concurrent access
    - aiosqlite for async database operations
    - TDD RED-GREEN-REFACTOR cycle
    - Path validation with pathlib.Path
    - Idempotent operations (unmap)

decisions:
  - thread_id as PRIMARY KEY, project_path as UNIQUE: Enforces bijection at database level
  - Path validation before mapping: Fail fast with clear error if directory doesn't exist
  - Idempotent unmap operation: No error if thread not mapped, enables safe retry
  - Reverse lookup index on project_path: Efficient bidirectional queries
  - ThreadMappingError for all validation failures: Single exception type for all mapping errors
  - UTC timestamps with datetime.now(UTC): Consistent with Phase 2 session patterns

key-files:
  created:
    - src/thread/__init__.py
    - src/thread/schema.sql
    - src/thread/mapper.py
    - tests/test_thread_mapper.py
  modified: []

metrics:
  duration: 2 minutes
  completed: 2026-01-26
  tasks: 3/3
  commits: 3
  test-coverage: 12 tests, 100% passing
---

# Phase 04 Plan 01: Thread-to-Project Mapping Storage Summary

**One-liner:** SQLite persistence for bijective Signal thread ↔ project directory mappings with path validation and TDD coverage.

## What Was Built

Created `ThreadMapper` class providing persistent storage for Signal thread to project directory associations. Enables multi-project support by maintaining mappings that survive daemon restarts.

**Core functionality:**
- **ThreadMapper class** with full CRUD operations (map, get_by_thread, get_by_path, list_all, unmap)
- **ThreadMapping dataclass** representing associations with timestamps
- **SQLite schema** with bijection enforcement (PRIMARY KEY on thread_id, UNIQUE on project_path)
- **Path validation** rejects non-existent directories before mapping
- **Reverse lookups** via index on project_path for efficient bidirectional queries
- **Idempotent operations** (unmap doesn't fail if mapping doesn't exist)

**TDD implementation:**
- RED phase: 12 failing tests covering all CRUD operations and validation
- GREEN phase: ThreadMapper implementation passes all tests
- Test coverage: 100% (12/12 passing)

## Architecture Decisions

### 1. Bijection Enforcement at Database Level
**Decision:** Use PRIMARY KEY on thread_id and UNIQUE constraint on project_path.
**Rationale:** Prevents duplicate mappings at the database level, not just application level. One thread can map to only one project, and one project can map to only one thread.
**Impact:** Simple, reliable enforcement. Database rejects violations automatically.

### 2. Path Validation Before Mapping
**Decision:** Check Path.exists() before creating mapping, raise ThreadMappingError if path missing.
**Rationale:** Fail fast with clear error message. Prevents invalid mappings from being stored.
**Impact:** Users get immediate feedback if they specify wrong path. No orphaned mappings to non-existent directories.

### 3. Idempotent Unmap Operation
**Decision:** unmap() doesn't raise error if thread not mapped.
**Rationale:** Enables safe retry logic in higher layers. Caller doesn't need to check existence first.
**Impact:** Simpler error handling in SessionCommands. Multiple unmap calls safe.

### 4. Reverse Lookup Index
**Decision:** CREATE INDEX on project_path for reverse lookups.
**Rationale:** Need to query both directions efficiently (thread→path and path→thread).
**Impact:** O(1) lookups in both directions. Supports "which thread is working on this project?" queries.

### 5. Single Exception Type
**Decision:** ThreadMappingError for all validation failures (path missing, duplicate thread, duplicate path).
**Rationale:** Simpler exception handling. Caller catches one type, examines message for details.
**Impact:** Cleaner code in higher layers. Error messages are descriptive.

## Technical Implementation

### Database Schema
```sql
CREATE TABLE IF NOT EXISTS thread_mappings (
    thread_id TEXT PRIMARY KEY,
    project_path TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_thread_mappings_path ON thread_mappings(project_path);
```

### ThreadMapper API
```python
class ThreadMapper:
    async def map(thread_id: str, project_path: str) -> ThreadMapping
    async def get_by_thread(thread_id: str) -> ThreadMapping | None
    async def get_by_path(project_path: str) -> ThreadMapping | None
    async def list_all() -> list[ThreadMapping]
    async def unmap(thread_id: str) -> None
```

### Validation Rules
1. **Path must exist:** Path.exists() check before INSERT
2. **No duplicate threads:** Check existing thread_id before INSERT
3. **No duplicate paths:** Check existing project_path before INSERT
4. **Database enforces:** PRIMARY KEY and UNIQUE constraints as backstop

### Patterns From Phase 2
- **aiosqlite** for async SQLite operations
- **WAL mode** (PRAGMA journal_mode=WAL) for concurrent access
- **UTC timestamps** with datetime.now(UTC)
- **Structured logging** with structlog
- **TDD cycle** RED-GREEN-REFACTOR

## Test Coverage

All 12 tests passing:
1. ✅ test_map_creates_new_mapping - Basic mapping creation
2. ✅ test_map_rejects_nonexistent_path - Path validation
3. ✅ test_map_rejects_duplicate_thread - No duplicate thread_id
4. ✅ test_map_rejects_duplicate_path - No duplicate project_path
5. ✅ test_get_by_thread - Forward lookup works
6. ✅ test_get_by_thread_nonexistent - Returns None if missing
7. ✅ test_get_by_path - Reverse lookup works
8. ✅ test_get_by_path_nonexistent - Returns None if missing
9. ✅ test_list_all - Returns all mappings ordered by created_at DESC
10. ✅ test_list_all_empty - Handles empty database
11. ✅ test_unmap_removes_mapping - Deletion works
12. ✅ test_unmap_nonexistent_noop - Idempotent behavior

## Integration Points

### Provided by This Plan
- `ThreadMapper` class ready for integration in SessionCommands
- `ThreadMappingError` exception for error handling
- SQLite schema automatically created on initialize()

### Required by Next Plans
**Plan 04-02** will integrate ThreadMapper into SessionCommands:
- Replace in-memory thread_sessions dict with ThreadMapper
- Add /thread map, /thread unmap, /thread list commands
- Persist thread-session associations across daemon restarts

### Dependencies
- Follows patterns from **02-01** (session persistence)
- Complements **03-04** (orchestrator integration)
- Enables **04-02** (multi-project commands)

## Deviations from Plan

None - plan executed exactly as written.

## Lessons Learned

### What Worked Well
1. **TDD cycle** - RED-GREEN phases kept implementation focused. All tests passed first try after implementation.
2. **Following Phase 2 patterns** - Reusing established patterns (aiosqlite, WAL mode, UTC timestamps) made implementation straightforward.
3. **Database-level constraints** - PRIMARY KEY and UNIQUE constraints provide reliability beyond application-level checks.

### For Future Plans
1. **Bijection pattern** established here can be reused for other one-to-one mappings.
2. **Path validation** pattern (check existence before store) should be standard for all filesystem-related storage.
3. **Idempotent operations** simplify error handling in higher layers.

## Next Phase Readiness

**Ready for Plan 04-02:** Thread-Project Command Integration
- ThreadMapper fully implemented and tested
- All CRUD operations working
- Bijection enforcement verified
- No blockers

**Phase 4 Progress:** 1/4 plans complete (25%)
