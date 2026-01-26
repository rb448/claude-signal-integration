---
phase: 06-code-display
plan: 01
subsystem: ui
tags: [mobile, code-formatting, text-wrapping, python]

# Dependency graph
requires:
  - phase: 03-claude-integration
    provides: SignalResponder pattern for formatting messages
provides:
  - CodeFormatter class for mobile-optimized code display (50 char width)
  - LengthDetector class for inline vs attachment routing
affects: [06-02, 06-03, 06-04, 06-05]

# Tech tracking
tech-stack:
  added: []
  patterns: [mobile-first code formatting, width constraint wrapping, continuation markers]

key-files:
  created: [src/claude/code_formatter.py, tests/test_code_formatter.py]
  modified: []

key-decisions:
  - "MAX_WIDTH = 50 chars for 320px mobile screens (monospace ~6px/char)"
  - "Continuation marker (↪) for wrapped lines to indicate visual continuation"
  - "Word boundary breaking preferred over mid-word breaks"
  - "INLINE_MAX = 20 lines, ATTACH_MIN = 100 lines with mid-range defaulting to inline"
  - "Mid-range (20-100 lines) defaults to inline for better UX"

patterns-established:
  - "TDD RED-GREEN-REFACTOR cycle with test-first development"
  - "Helper method extraction (_wrap_line, _get_indent, _break_at_boundary)"
  - "Edge case testing (empty code, single line, boundary values)"

# Metrics
duration: 2min
completed: 2026-01-26
---

# Phase 06 Plan 01: Code Display Foundation Summary

**Mobile-optimized code formatter with 50-char width constraint and intelligent inline vs attachment detection for 320px screens**

## Performance

- **Duration:** 2 min
- **Started:** 2026-01-26T22:17:11Z
- **Completed:** 2026-01-26T22:19:42Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- CodeFormatter wraps long lines at 50 chars with continuation markers (↪)
- Preserves code indentation and empty lines (structural whitespace)
- LengthDetector routes code: inline (<20 lines), attachment (>100 lines), mid-range defaults to inline
- Comprehensive edge case handling (empty code, single line, boundary values)

## Task Commits

Each task was committed atomically following TDD RED-GREEN-REFACTOR:

1. **Task 1: Create CodeFormatter with mobile width constraints**
   - `6253bd9` (test) - Add failing tests for mobile code formatting
   - `d5cabd4` (feat) - Implement CodeFormatter with width constraints

2. **Task 2: Add LengthDetector for inline vs attachment decision**
   - `28b81b0` (test) - Add tests for length detection

_Note: LengthDetector implementation was included in feat commit d5cabd4 (GREEN phase)_

## Files Created/Modified

- `src/claude/code_formatter.py` - CodeFormatter class with MAX_WIDTH=50, word boundary breaking, and LengthDetector with INLINE_MAX=20/ATTACH_MIN=100 thresholds
- `tests/test_code_formatter.py` - 16 tests (7 for CodeFormatter, 9 for LengthDetector) covering wrapping, indentation, edge cases, and threshold logic

## Decisions Made

**MAX_WIDTH = 50 chars for 320px screens**
- Rationale: 320px ÷ 6px per monospace char ≈ 53 chars; 50 provides margin for padding/borders
- Impact: Ensures code readable on smallest mobile screens without horizontal scroll

**Continuation marker (↪) for wrapped lines**
- Rationale: Visual indicator that line continues below, prevents confusion with natural line breaks
- Implementation: Added after preserved indentation on wrapped lines

**Word boundary breaking**
- Rationale: Breaking mid-identifier creates confusing partial tokens
- Fallback: Hard break at MAX_WIDTH if no space found (prevents infinite loop on long tokens)

**Mid-range (20-100 lines) defaults to inline**
- Rationale: Better to show some context inline than force download; Phase 6 will add code folding/truncation
- Future: `/code full` command will override for complete view

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - implementation proceeded smoothly following TDD pattern.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- CodeFormatter and LengthDetector ready for integration with SignalResponder
- Next plan (06-02) can add syntax highlighting using these formatters
- Mobile width constraints established for all code display features
- Test patterns established for Phase 6 components

---
*Phase: 06-code-display*
*Completed: 2026-01-26*
