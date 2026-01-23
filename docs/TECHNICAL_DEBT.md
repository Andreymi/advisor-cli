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
**File:** `cli.py:214-247`

**Problem:** Background task execution via subprocess has issues:
- No error handling if subprocess fails
- No timeout — could hang forever
- `start_new_session=True` orphans process if parent dies
- No logging of subprocess start/failure

**Solution:** Use structured async task queue or add proper error handling.

---

#### 2. cli.py too large (1100+ lines)
**File:** `cli.py`

**Problem:** Single file with 20 commands, hard to navigate.

**Solution:** Split into modules:
```
cli.py          → entry point (~50 lines)
cli_utils.py    → shared helpers (~100 lines)
cli_core.py     → ask, compare, result, status (~300 lines)
cli_config.py   → config sub-app (~150 lines)
cli_mcp.py      → mcp sub-app (~250 lines)
cli_skill.py    → skill sub-app (~150 lines)
cli_install.py  → unified install (~100 lines)
```

---

### LOW Priority

#### 3. Magic numbers without constants
**Files:** `cli.py`, `core.py`, `file_utils.py`

**Examples:**
- `TASK_TTL = 3600` — no comment explaining 1 hour
- `str(uuid.uuid4())[:8]` — arbitrary truncation
- `error_msg[:150]` — arbitrary truncation
- `MAX_FILE_SIZE = 100 * 1024` — arbitrary limit

**Solution:** Extract to named constants with documentation.

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

---

## How to Update

When adding new debt:
1. Add to appropriate priority section
2. Include file path and line numbers
3. Describe problem and solution

When resolving debt:
1. Move to "Resolved Debt" section
2. Add date and brief description
