# Technical Debt

Tracking technical debt for advisor-cli project.

## Priority Levels

- **HIGH** — Affects functionality or security, fix soon
- **MEDIUM** — Code quality issue, fix when touching related code
- **LOW** — Nice to have, fix when time permits

---

## Active Debt

### MEDIUM Priority

#### 1. Subprocess security in async mode
**File:** `cli_core.py:43-66`

**Problem:** Background task execution via subprocess has issues:
- No timeout — could hang forever
- `start_new_session=True` orphans process if parent dies
- No logging of subprocess start/failure

**Partial fix (2026-01-24):** Added OSError handling in `_run_background_task()`.

**Remaining:** Add timeout mechanism or structured async task queue.

---

### LOW Priority

#### 2. Magic numbers without constants
**Files:** `core.py`, `file_utils.py`

**Examples:**
- `error_msg[:150]` — arbitrary truncation
- `MAX_FILE_SIZE = 100 * 1024` — arbitrary limit

**Partial fix (2026-01-24):**
- `TASK_TTL` → `TASK_TTL_SECONDS` with documentation
- `uuid[:8]` → `TASK_ID_LENGTH = 8` constant

**Solution:** Extract remaining to named constants with documentation.

---

#### 4. Global state management
**File:** `core.py`

**Problem:** Module-level mutable state:
- `CACHE_ACTIVE = False` — modified by `init_cache()`
- `_reasoning_cache = {}` — modified at runtime

**Issues:**
- Not thread-safe
- Hard to test (requires mocking globals)
- Init order dependent

**Solution:** Class-based initialization or dataclasses.

---

#### 5. Reasoning cache performance
**File:** `core.py:271-329`

**Problem:**
- Cache loaded only once at startup
- New models discovered during session not persisted until explicit save
- No cache invalidation mechanism

**Solution:** LRU cache or explicit cache refresh command.

---

## Resolved Debt

### 2026-01-23: Code Simplification Sprint
- ✅ Consolidated error formatting (`format_error`)
- ✅ Extracted `build_context` helper
- ✅ Extracted `_parse_format` helper
- ✅ Added `require_wizard` decorator
- ✅ Added `update_config` helper
- ✅ Removed wrapper functions in setup_wizard
- ✅ Extracted `_build_messages` helper

### 2026-01-23: Tech Debt Sprint
- ✅ Added tests for helper functions (+31 tests)
- ✅ Consolidated PROVIDER_INFO into config.py
- ✅ Standardized docstrings to English
- ✅ Added return type hints to CLI commands
- ✅ Replaced bare `except:` with specific exceptions
- ✅ Centralized `asyncio.run()` into `run_async` helper

### 2026-01-24: CLI Split Sprint
- ✅ Split cli.py from 1102 lines to 94 lines (91.5% reduction)
- ✅ Created 7 focused modules:
  - `cli_async.py` — async task utilities (TASK_TTL_SECONDS, TASK_ID_LENGTH)
  - `cli_output.py` — print_output, _parse_format
  - `cli_core.py` — ask, compare, result, status, models commands
  - `cli_config.py` — config sub-app (single, compare, format, show, purge)
  - `cli_mcp.py` — mcp sub-app (install, uninstall, status)
  - `cli_skill.py` — skill sub-app (install, uninstall, status)
  - `cli_install.py` — unified install/uninstall commands
- ✅ Added OSError handling for subprocess in _run_background_task()
- ✅ Documented TASK_TTL_SECONDS constant (was TASK_TTL)
- ✅ Added TASK_ID_LENGTH constant for UUID truncation
- ✅ Added 27 new tests for CLI modules

---

## How to Update

When adding new debt:
1. Add to appropriate priority section
2. Include file path and line numbers
3. Describe problem and solution

When resolving debt:
1. Move to "Resolved Debt" section
2. Add date and brief description
