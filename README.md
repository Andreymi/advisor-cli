# Advisor CLI

[![PyPI](https://img.shields.io/pypi/v/advisor-cli)](https://pypi.org/project/advisor-cli/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Get second opinions from alternative LLMs — Gemini, GPT, DeepSeek, Ollama, and more.

## Why Advisor?

Using Claude but want a second opinion? Advisor lets you:

- **Validate decisions** — ask GPT-4o or Gemini to review suggestions
- **Compare approaches** — get parallel responses from multiple models
- **Specialize** — use DeepSeek for reasoning, Groq for speed

Works standalone CLI or integrated directly into Claude Code (MCP + Skill).

## Features

- **Multi-provider** — Gemini, OpenAI, Anthropic, DeepSeek, Groq, Ollama
- **Claude Code integration** — MCP tools + `/advisor` skill
- **Compare mode** — parallel queries to multiple models
- **Async execution** — background tasks for long queries
- **File input** — pipe stdin or pass files directly
- **Caching** — disk cache with configurable TTL

## Quick Start

```bash
# Install
uv tool install advisor-cli
# or: pip install advisor-cli[all]

# Configure
advisor setup

# Install integrations (MCP + Skill for Claude Code)
advisor install
```

## Installation

**Recommended (uv):**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install advisor-cli
```

**Via pip:**
```bash
pip install advisor-cli          # CLI only
pip install advisor-cli[mcp]     # + MCP server
pip install advisor-cli[wizard]  # + interactive wizard
pip install advisor-cli[all]     # everything
```

**From source:**
```bash
git clone https://github.com/Andreymi/advisor-cli
cd advisor-cli && uv sync --extra all
```

## Configuration

**Interactive wizard:**
```bash
advisor setup
```

**Environment variables (CI/scripts):**
```bash
GEMINI_API_KEY=xxx OPENAI_API_KEY=xxx advisor setup -y
```

**Config location:** `~/.config/advisor/config.env`

```bash
# View current configuration
advisor config show

# Set default models
advisor config single gemini/gemini-2.5-pro
advisor config compare "openai/gpt-4o,gemini/gemini-2.0-flash"
```

## Usage

### CLI Commands

```bash
# Single query
advisor ask "How to optimize this query?"
advisor ask "Review this code" -f mycode.py
cat code.py | advisor ask "Find bugs"

# Compare multiple models
advisor compare "Redis vs Memcached?"
advisor compare "Question" -m "openai/gpt-4o,gemini/gemini-2.0-flash"

# Async execution (background)
advisor compare "Deep analysis" --async
# => Task ID: abc123
advisor result abc123

# Status and models
advisor status
advisor models
```

**Options:**
- `-f FILE` — add file as context
- `-m MODEL` — specify model(s)
- `--format json|markdown` — output format
- `--async` — run in background

### MCP Integration

Adds `advisor_consult_expert` and `advisor_compare_experts` tools to Claude.

```bash
# Install to Claude Code and Desktop
advisor mcp install

# Project-only or user-wide
advisor mcp install --scope project
advisor mcp install --scope user

# Status and uninstall
advisor mcp status
advisor mcp uninstall
```

**MCP Tools:**
```python
advisor_consult_expert(
    query="Review for vulnerabilities",
    context="def get_user(id): ...",
    role="Senior Security Engineer"
)

advisor_compare_experts(
    query="Redis or Memcached?",
    models="gemini/gemini-2.0-flash,openai/gpt-4o"
)
```

### Claude Code Skill

Adds `/advisor` command to Claude Code for quick second opinions.

```bash
# Install skill
advisor skill install

# Project-only or user-wide
advisor skill install --scope project
advisor skill install --scope user

# Status and uninstall
advisor skill status
advisor skill uninstall
```

**Usage in Claude Code:**
```
/advisor Review this authentication code for security issues
/advisor Is O(n²) acceptable here or should I optimize?
```

### Unified Install

Install both MCP and Skill with one command:

```bash
advisor install                    # interactive
advisor install --scope project    # project only
advisor install --scope user       # user-wide
advisor install -y                 # non-interactive
```

## Providers

| Provider | Example models | API Key |
|----------|----------------|---------|
| **Gemini** | `gemini/gemini-2.0-flash`, `gemini-2.5-pro` | `GEMINI_API_KEY` |
| **OpenAI** | `openai/gpt-4o-mini`, `gpt-4o` | `OPENAI_API_KEY` |
| **Anthropic** | `anthropic/claude-3-5-haiku` | `ANTHROPIC_API_KEY` |
| **DeepSeek** | `deepseek/deepseek-chat` | `DEEPSEEK_API_KEY` |
| **Groq** | `groq/llama-3.3-70b-versatile` | `GROQ_API_KEY` |
| **OpenRouter** | `openrouter/google/gemini-2.0-flash` | `OPENROUTER_API_KEY` |
| **Ollama** | `ollama/llama3.2` (local) | `OLLAMA_HOST` |

## Examples

### Code Review
```bash
git diff | advisor ask "Review changes"
advisor ask "Find vulnerabilities" -f api.py
```

### Architecture Decisions
```bash
advisor compare "Rust vs Go for microservice"
advisor ask "Is there a better solution than O(n²)?" -f algo.py
```

### Specialized Roles
```bash
# Security audit
ADVISOR_DEFAULT_ROLE="Senior Security Engineer" advisor ask "Review" -f code.py

# Performance analysis
advisor ask "Find bottlenecks" -f slow_query.sql -m deepseek/deepseek-reasoner
```

| Task | Recommended Role |
|------|------------------|
| Security | "Senior Security Engineer. Find vulnerabilities." |
| Architecture | "Solution Architect. Evaluate scalability." |
| Performance | "Performance Engineer. Find bottlenecks." |
| Database | "DBA. Evaluate schema and queries." |

## Cleanup

```bash
advisor config purge   # remove API keys only
advisor uninstall      # remove all data (config + cache)
```

## License

MIT
