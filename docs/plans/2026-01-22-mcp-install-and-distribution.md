# Design: MCP Install CLI & Distribution

**Date:** 2026-01-22
**Status:** Approved

## Goal

1. Add CLI commands for automatic MCP configuration management
2. Prepare advisor-cli for public distribution via PyPI
3. Create onboarding shell script for easy installation

## Target Audience

Universal: both Claude Code developers and Claude Desktop users.

## Distribution

**Primary:** `uv tool install advisor-cli`

**Onboarding script:**
```bash
curl -fsSL https://raw.githubusercontent.com/USER/advisor-cli/main/install.sh | sh
```

## New CLI Commands

### Structure

```
advisor mcp
├── install     # Add to Claude config
├── uninstall   # Remove from config
└── status      # Show installation status
```

### Flags

```bash
advisor mcp install
  --scope project|user    # Override smart logic
  --target claude-code|desktop|all  # Where to install (default: all)
  --force                 # Overwrite without asking
  -y                      # Non-interactive mode

advisor mcp uninstall
  --scope project|user
  --all                   # Remove from everywhere

advisor mcp status        # No flags needed
```

## Smart Scope Logic

1. If `.mcp.json` exists in current directory → suggest project scope
2. Otherwise → ask user: project or global (user)
3. With `-y` flag → default to user scope

## Conflict Detection

| Type | Description | Action |
|------|-------------|--------|
| duplicate | advisor_mcp already in target config | Offer update |
| override | Project config overrides global | Warn only |
| name_collision | advisor_mcp points to different server | Ask: rename or replace |
| outdated | Old command (mcp-advisor → advisor run) | Offer update |

## MCP Install Flow

```python
def mcp_install(scope, target, force, yes):
    # 1. Check if providers configured
    if not has_configured_providers():
        if yes:
            if not setup_from_env():
                error("No API keys")
                return
        else:
            if confirm("No providers. Run setup?"):
                run_setup()
            else:
                return

    # 2. Determine scope (smart logic)
    if scope is None:
        if Path(".mcp.json").exists():
            scope = "project"
        elif not yes:
            scope = ask_scope()
        else:
            scope = "user"

    # 3. Check conflicts
    conflicts = check_conflicts(scope, target)
    if conflicts and not force:
        handle_conflicts(conflicts, yes)

    # 4. Install
    install_to_targets(scope, target)
```

## Config Paths

```python
CONFIG_PATHS = {
    "claude_code_user": Path.home() / ".claude.json",
    "claude_code_project": Path.cwd() / ".mcp.json",
    "claude_desktop": Path.home() / "Library/Application Support/Claude/claude_desktop_config.json",
    "claude_desktop_linux": Path.home() / ".config/Claude/claude_desktop_config.json",
    "claude_desktop_win": Path.home() / "AppData/Roaming/Claude/claude_desktop_config.json",
}
```

## MCP Config Template

```python
# For Claude Code (uses PATH)
{
    "advisor_mcp": {
        "command": "advisor",
        "args": ["run"]
    }
}

# For Claude Desktop (needs absolute path)
{
    "advisor_mcp": {
        "command": "/Users/x/.local/bin/advisor",
        "args": ["run"]
    }
}
```

## Install Script (install.sh)

```bash
#!/bin/sh
set -e

echo "Installing advisor-cli..."

# 1. Install uv if needed
if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# 2. Install advisor-cli
uv tool install advisor-cli

# 3. Auto-setup if API keys in env
if [ -n "$GEMINI_API_KEY" ] || [ -n "$OPENAI_API_KEY" ]; then
    advisor setup -y
    advisor mcp install -y
else
    echo "Done! Now run:"
    echo "   advisor setup"
    echo "   advisor mcp install"
fi
```

## Setup -y Flag

Add non-interactive mode to `advisor setup`:

```bash
advisor setup -y              # Use defaults + env vars
advisor setup -y -p gemini    # Specify providers
advisor setup -y -m model     # Specify default model
```

## PyPI Publishing

```toml
[project]
name = "advisor-cli"
version = "0.2.0"
description = "Get second opinions from alternative LLMs (Gemini, GPT, DeepSeek, Ollama)"
license = "MIT"
keywords = ["llm", "cli", "mcp", "ai", "gemini", "openai", "claude"]
```

## New Files

| File | Purpose |
|------|---------|
| `src/advisor_cli/mcp_manager.py` | MCP install/uninstall/status logic |
| `install.sh` | Onboarding script |

## Modified Files

| File | Changes |
|------|---------|
| `src/advisor_cli/cli.py` | Add `mcp` command group |
| `src/advisor_cli/setup_wizard.py` | Add `-y` non-interactive mode |
| `pyproject.toml` | Update metadata for PyPI |

## Verification

1. `advisor mcp install` — interactive flow works
2. `advisor mcp install -y` — non-interactive with env vars
3. `advisor mcp status` — shows correct info
4. `advisor mcp uninstall` — removes from config
5. Conflict detection works for all 4 types
6. `install.sh` works on fresh machine
7. `uv tool install advisor-cli` works from PyPI
