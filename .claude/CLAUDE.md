# Advisor CLI Project

## Tech Stack
- Python 3.10+ with FastMCP (MCP server framework)
- LiteLLM for multi-provider LLM support
- Pydantic for data validation
- diskcache for response caching
- typer + rich + questionary for CLI

## Project Structure
```
src/advisor_cli/
├── cli.py              — CLI entry point (94 lines)
├── cli_async.py        — Task API: TaskStatus, update_task_status, get_async_result
├── cli_output.py       — Output helpers (print_output, _parse_format)
├── cli_core.py         — Core commands (ask, compare, result, status, models)
├── cli_config.py       — Config commands (single, compare, format, show, purge, cache-clear)
├── cli_mcp.py          — MCP commands (install, uninstall, status)
├── cli_skill.py        — Skill commands (install, uninstall, status)
├── cli_install.py      — Unified install/uninstall commands
├── core.py             — LLM logic + CacheManager (no MCP dependency)
├── task_runner.py      — Background task execution with timeout (subprocess entry point)
├── config.py           — XDG config management
├── server.py           — MCP server (optional)
├── setup_wizard.py     — Interactive wizard
├── file_utils.py       — File operations
├── mcp_manager.py      — MCP installation logic
├── skill_manager.py    — Skill installation logic
├── utils.py            — Shared utilities (require_wizard, run_async)
└── data/skills/        — Bundled skill for distribution
```

## Commands

### Core
- `advisor ask "query"` — single LLM request
- `advisor compare "query"` — multi-model consilium
- `advisor result <id>` — get async task result
- `advisor status` — show current status
- `advisor models` — show model configuration

### Installation (unified)
- `advisor install` — install MCP + Skill (asks scope)
- `advisor install --scope project` — install to current project
- `advisor install --scope user` — install globally

### Config
- `advisor setup` — interactive configuration
- `advisor config show` — show config paths and values
- `advisor config single <model>` — set default model
- `advisor config compare <models>` — set consilium models
- `advisor config purge` — remove config (API keys)
- `advisor config cache-clear` — clear reasoning model cache
- `advisor uninstall` — remove all data (config + cache)

### MCP
- `advisor mcp install` — install MCP integration
- `advisor mcp uninstall` — remove MCP integration
- `advisor mcp status` — show MCP status
- `advisor run` — run MCP server (requires `[mcp]`)

### Skill
- `advisor skill install` — install Claude Code skill
- `advisor skill uninstall` — remove skill
- `advisor skill status` — show skill status

### Development
- `uv sync` — install dependencies
- `uv run pytest tests/ -v` — run tests

## CLI Features
- Stdin pipe: `cat code.py | advisor ask "Review this"`
- File input: `advisor ask -f code.py "Review"`
- Async mode: `advisor compare --async "query"` → `advisor result <id>`
- Formats: `--format json|markdown`

## Configuration Paths (XDG)
- Config: `~/.config/advisor/config.env`
- Cache: `~/.cache/advisor/`
- Skill (user): `~/.claude/skills/advisor/`
- Skill (project): `.claude/skills/advisor/`

## Optional Dependencies
- `pip install advisor-cli` — basic CLI
- `pip install advisor-cli[mcp]` — with MCP server
- `pip install advisor-cli[wizard]` — with interactive wizard
- `pip install advisor-cli[all]` — everything

## Supported Providers
- Gemini (`gemini/gemini-*`)
- OpenAI (`openai/gpt-*`)
- Anthropic (`anthropic/claude-*`)
- DeepSeek (`deepseek/*`)
- Groq (`groq/*`)
- OpenRouter (`openrouter/*`)
- Ollama Local (`ollama/*`)
- Ollama Cloud (`ollama-cloud/*`)
- Custom providers via `ADVISOR_CUSTOM_PROVIDERS` env var

## Hooks
- `PostToolUse` — ruff format/check for .py files
- `PreToolUse` — protect .env from editing

## Architecture Notes
- Task API lives in `cli_async.py` (single source of truth for TaskStatus, update_task_status)
- `task_runner.py` is subprocess entry point only — imports from cli_async
- Cache state in `CacheManager` class (core.py) — use `get_cache_manager()` singleton
- `docs/` directory is gitignored (internal documentation)

## Important
- Config contains API keys — do NOT commit, do NOT edit via Claude
- Use `advisor config show` to see current configuration

## Available Skills
- `/advisor` — get second opinion from alternative LLMs (Gemini, GPT, DeepSeek, etc.)
