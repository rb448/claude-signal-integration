---
phase: 08-notification-system
plan: 02
subsystem: notification
tags: [tdd, sqlite, preferences, persistence, notifications]
dependencies:
  requires: [phase-02-session-management, phase-04-thread-mapper]
  provides: [notification-preferences-storage, preference-matching-algorithm]
  affects: [08-03-notification-integration, 08-04-preference-commands]
tech-stack:
  added: []
  patterns: [async-sqlite, wal-mode, preference-matching, urgency-priority]
key-files:
  created:
    - src/notification/__init__.py
    - src/notification/types.py
    - src/notification/preferences.py
    - src/notification/schema.sql
    - tests/test_notification_preferences.py
  modified: []
decisions:
  - decision: "UrgencyLevel enum with 4 levels (URGENT, IMPORTANT, INFORMATIONAL, SILENT)"
    rationale: "Clear hierarchy for notification prioritization"
    plan: "08-02"
  - decision: "URGENT overrides user preferences (always notify)"
    rationale: "Critical events (errors, approvals) must not be silenced"
    plan: "08-02"
  - decision: "SILENT overrides user preferences (never notify)"
    rationale: "Internal events should never create user-facing notifications"
    plan: "08-02"
  - decision: "Default preferences by urgency: IMPORTANT=True, INFORMATIONAL=False"
    rationale: "Completion/reconnection events useful by default, progress events chatty"
    plan: "08-02"
  - decision: "Application Support directory for notification_prefs.db"
    rationale: "Follows macOS standards, consistent with thread/session databases"
    plan: "08-02"
  - decision: "Composite primary key (thread_id, event_type)"
    rationale: "Enables per-thread, per-event-type granular preference control"
    plan: "08-02"
  - decision: "Idempotent upsert with ON CONFLICT"
    rationale: "Follows Phase 2-5 patterns, safe retry logic without special-casing"
    plan: "08-02"
metrics:
  duration: "3 minutes"
  completed: "2026-01-28"
---

# Phase 08 Plan 02: Notification Preferences Summary

Per-thread notification preference storage with SQLite persistence and urgency-aware preference matching algorithm.

## One-liner

SQLite-backed per-thread notification preferences with urgency priority rules (URGENT overrides, SILENT blocks) and default policies (IMPORTANT=enabled, INFORMATIONAL=disabled).

## What Was Built

### TDD Execution

**RED Phase (commit cedae8a):**
- Created 13 comprehensive tests covering:
  - Database initialization and schema creation
  - CRUD operations (set/get preference, get all preferences)
  - Preference persistence across database reconnections
  - Urgency priority rules (URGENT overrides, SILENT blocks)
  - Default preference fallback (IMPORTANT=True, INFORMATIONAL=False)
  - Concurrent access safety with WAL mode
- Created stub implementation that returns None/False/empty dicts
- Result: 8 tests failed as expected, 5 tests passed (expecting None/False/empty)

**GREEN Phase (commit 25d6dd0):**
- Implemented full NotificationPreferences class with:
  - Async SQLite operations using aiosqlite
  - WAL mode for concurrent access safety
  - CRUD operations: `get_preference()`, `set_preference()`, `get_all_preferences()`
  - Preference matching: `should_notify(thread_id, event_type, urgency_level)`
  - DEFAULT_PREFERENCES constant mapping urgency levels to default behavior
  - Idempotent upsert using `ON CONFLICT DO UPDATE`
  - UTC timestamps with `datetime.now(UTC)`
- Database location: `~/Library/Application Support/claude-signal-daemon/notification_prefs.db`
- Result: All 13 tests pass

**REFACTOR Phase:**
- Not needed - implementation clean and follows established patterns
- Code structure matches SessionManager and ThreadMapper patterns
- Clear separation of concerns with well-documented methods

### Database Schema

```sql
CREATE TABLE notification_preferences (
    thread_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (thread_id, event_type)
);

CREATE INDEX idx_thread_preferences ON notification_preferences(thread_id);
```

### Preference Matching Algorithm

`should_notify()` implements 4-level priority logic:

1. **URGENT urgency** → Always True (overrides user preferences)
   - Critical events: errors, approval_needed
   - Cannot be disabled by users

2. **SILENT urgency** → Always False (overrides user preferences)
   - Internal events: debug, internal state changes
   - Cannot be enabled by users

3. **User preference** → Use stored preference if set
   - User has explicitly configured this thread + event type

4. **Default preference** → Fall back to urgency-based default
   - IMPORTANT: True (completion, reconnection events)
   - INFORMATIONAL: False (progress, chatty events)

### Supporting Types

Created `src/notification/types.py` with `UrgencyLevel` enum:
- `URGENT` - Always notify (errors, approvals)
- `IMPORTANT` - Notify by default (completions, reconnection)
- `INFORMATIONAL` - Don't notify by default (progress)
- `SILENT` - Never notify (internal events)

## Architectural Decisions

### Urgency Priority Override System

**Decision:** URGENT and SILENT urgency levels override user preferences.

**Rationale:**
- URGENT events (errors, approvals) are critical and must not be missed
- User attempting to disable error notifications would harm their experience
- SILENT events (debug, internal) should never create user-facing noise
- User attempting to enable debug notifications would cause confusion

**Impact:**
- User preferences only affect IMPORTANT and INFORMATIONAL urgency levels
- System maintains control over critical notification behavior
- Prevents user misconfiguration from degrading experience

### Default Preferences by Urgency

**Decision:** Default to enabled for IMPORTANT, disabled for INFORMATIONAL.

**Rationale:**
- IMPORTANT events (completion, reconnection) provide useful feedback
- INFORMATIONAL events (progress updates) are too chatty for default behavior
- Users can customize per thread/event if needed
- Conservative default prevents notification fatigue

**Impact:**
- First-time users see completion and error notifications
- Progress updates don't spam users until explicitly enabled
- Balances discoverability with noise reduction

### Composite Primary Key

**Decision:** Use (thread_id, event_type) composite primary key.

**Rationale:**
- Enables per-thread, per-event granular control
- User can disable progress in one thread, enable in another
- User can disable completion events for noisy projects
- Natural bijection enforced at database level

**Impact:**
- Fine-grained user control without complex preference hierarchies
- Simple queries: "Is this specific notification enabled?"
- No need for preference inheritance or cascading rules

## Patterns Established

### Async SQLite with WAL Mode

Follows Phase 2 SessionManager pattern:
- `initialize()` creates directory, connects, enables WAL, loads schema
- `close()` closes connection and sets to None
- All operations use `async with self._lock` for thread safety
- Schema in separate `.sql` file loaded at initialization

### Idempotent Operations

`set_preference()` uses upsert pattern:
```python
INSERT INTO ... VALUES (?, ?, ?, ?)
ON CONFLICT(thread_id, event_type) DO UPDATE SET
    enabled = excluded.enabled,
    updated_at = excluded.updated_at
```

Same pattern as Phase 2-5 for safe retry logic.

### Default Constants

Preference defaults extracted to module-level constant:
```python
DEFAULT_PREFERENCES = {
    UrgencyLevel.URGENT: True,
    UrgencyLevel.IMPORTANT: True,
    UrgencyLevel.INFORMATIONAL: False,
    UrgencyLevel.SILENT: False,
}
```

Single source of truth, easy to modify, clear intent.

## Testing

### Test Coverage

13 tests covering:
- Database lifecycle (initialize, persistence, concurrent access)
- CRUD operations (set, get, get_all, upsert)
- Preference matching (urgency rules, defaults, stored preferences)
- Edge cases (missing thread, unknown event, WAL mode safety)

All tests pass. Coverage estimated >95% (all public methods covered).

### Test Patterns

- Used `tmp_path` fixture for isolated test databases
- Async test fixture pattern: `@pytest.fixture async def preferences(tmp_path)`
- Tested persistence by closing and reopening database
- Tested concurrency with `asyncio.gather()`

## Integration Points

### For Phase 08-03 (Notification Integration)

NotificationPreferences ready for integration:
```python
prefs = NotificationPreferences()
await prefs.initialize()

# Check if notification should be sent
if await prefs.should_notify(thread_id, "completion", UrgencyLevel.IMPORTANT):
    await send_notification(...)
```

### For Phase 08-04 (Preference Commands)

CRUD operations ready for command layer:
```python
# /notify prefs list
prefs_dict = await prefs.get_all_preferences(thread_id)

# /notify prefs set completion off
await prefs.set_preference(thread_id, "completion", enabled=False)

# /notify prefs get progress
enabled = await prefs.get_preference(thread_id, "progress")
```

## Deviations from Plan

None - plan executed exactly as written.

## Next Phase Readiness

### Ready for 08-03 (Notification Integration)

- ✓ NotificationPreferences component complete
- ✓ Preference matching algorithm tested
- ✓ UrgencyLevel enum available for categorization
- ✓ Database schema stable

### Ready for 08-04 (Preference Commands)

- ✓ CRUD API complete for command layer
- ✓ get_all_preferences() returns user-friendly dict format
- ✓ set_preference() idempotent for safe retries

### Blocked

None.

### Concerns

None.

## Files Changed

### Created

**src/notification/__init__.py**
- Empty package initializer

**src/notification/types.py** (19 lines)
- UrgencyLevel enum with 4 levels
- Shared type for categorization and preferences

**src/notification/preferences.py** (201 lines)
- NotificationPreferences class
- Async SQLite CRUD operations
- Preference matching algorithm with urgency priority rules
- DEFAULT_PREFERENCES constant
- Follows SessionManager pattern

**src/notification/schema.sql** (10 lines)
- notification_preferences table
- Composite primary key (thread_id, event_type)
- Index on thread_id for efficient queries

**tests/test_notification_preferences.py** (219 lines)
- 13 comprehensive TDD tests
- Database lifecycle, CRUD, preference matching, concurrency
- All tests pass

### Modified

None.

## Commits

### TDD Cycle

1. **cedae8a** - `test(08-02): add failing tests for NotificationPreferences`
   - RED phase: 13 tests, 8 failing, 5 passing (stub behavior)
   - Tests for CRUD, persistence, urgency rules, defaults, concurrency

2. **25d6dd0** - `feat(08-02): implement NotificationPreferences with SQLite persistence`
   - GREEN phase: Full implementation, all 13 tests pass
   - Async SQLite, WAL mode, preference matching algorithm

## Metrics

- **Duration:** 3 minutes
- **Tests:** 13 passed, 0 failed
- **Lines of code:** 201 (implementation) + 219 (tests) = 420 total
- **Files created:** 5
- **Files modified:** 0
- **TDD commits:** 2 (test + feat)

## Knowledge Captured

### For Future Claude Sessions

When working with notification preferences:
1. Use `should_notify()` not raw `get_preference()` - it handles urgency rules
2. URGENT and SILENT override user preferences - don't bypass with get_preference()
3. Database location: `~/Library/Application Support/claude-signal-daemon/notification_prefs.db`
4. Preferences are per-thread AND per-event-type (not just per-thread)
5. DEFAULT_PREFERENCES constant defines fallback behavior

### Lessons Learned

1. **TDD discipline paid off:** 13 tests written before implementation caught edge cases early
2. **Pattern reuse effective:** Following SessionManager pattern made implementation straightforward
3. **Urgency priority rules essential:** Without URGENT override, users could disable critical error notifications
4. **Composite key powerful:** (thread_id, event_type) enables fine-grained control without complexity

## Success Criteria

- ✅ Failing test written and committed (RED phase)
- ✅ Implementation passes test (GREEN phase)
- ✅ Refactor assessed (not needed - clean implementation)
- ✅ 2 TDD commits present (test → feat)
- ✅ Preference storage persists across restarts
- ✅ Urgency rules override user preferences correctly
- ✅ All verification criteria met (pytest passes, WAL mode, CRUD works, priority rules correct)
