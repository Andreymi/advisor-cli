# Advisor CLI

Get second opinions from alternative LLMs (Gemini, GPT, DeepSeek, Ollama).

CLI and MCP server for consulting alternative LLMs when you need a different perspective.

## Quick Start

```bash
# One-line install (installs uv if needed)
curl -fsSL https://raw.githubusercontent.com/Andreymi/advisor-cli/main/install.sh | sh

# Configure
advisor setup
advisor mcp install
```

## Features

**CLI commands:**
- `advisor ask` — get response from a single model
- `advisor compare` — compare responses from multiple models
- `advisor mcp install` — add MCP integration to Claude Code/Desktop

**Additional:**
- Stdin pipe: `cat file.py | advisor ask "Review"`
- File input: `advisor ask -f code.py "Review"`
- Async execution: `advisor compare --async`
- JSON/Markdown output formats
- Automatic MCP integration
- Disk cache with TTL

## Installation

### Recommended (uv tool)

```bash
# Install uv (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install advisor-cli
uv tool install advisor-cli
```

### Via pip

```bash
# Basic install (CLI only)
pip install advisor-cli

# With MCP server
pip install advisor-cli[mcp]

# With interactive wizard
pip install advisor-cli[wizard]

# Everything included
pip install advisor-cli[all]
```

### From source

```bash
git clone https://github.com/Andreymi/advisor-cli
cd advisor-cli
uv sync --extra all
```

## Configuration

### Interactive wizard

```bash
advisor setup
```

### Automatic setup (CI/Scripts)

```bash
# From environment variables
GEMINI_API_KEY=xxx OPENAI_API_KEY=xxx advisor setup -y

# Install MCP without prompts
advisor mcp install -y
```

### Manual configuration (.env)

```bash
# Providers (enabled only with keys)
GEMINI_API_KEY=your_key
OPENAI_API_KEY=your_key
ANTHROPIC_API_KEY=your_key
DEEPSEEK_API_KEY=your_key

# Default models
ADVISOR_DEFAULT_MODEL=gemini/gemini-2.0-flash
ADVISOR_DEFAULT_MODELS_COMPARE=gemini/gemini-2.0-flash,openai/gpt-4o-mini

# Caching
ADVISOR_CACHE_ENABLED=true
ADVISOR_CACHE_TTL=3600
```

## CLI Usage

### Single query

```bash
# Simple question
advisor ask "How to optimize this query?"

# With file context
advisor ask "Review this code" -f mycode.py

# Via stdin
cat mycode.py | advisor ask "Find bugs"
git diff | advisor ask "Review changes"

# JSON format
advisor ask "Question" --format json

# Specify model
advisor ask "Question" -m openai/gpt-4o
```

### Compare (multiple models)

```bash
# Compare opinions
advisor compare "Redis vs Memcached for caching?"

# Specify models
advisor compare "Question" -m "openai/gpt-4o,gemini/gemini-2.0-flash"

# Async execution (background)
advisor compare "Deep analysis" -f big_file.py --async
# => Task ID: abc123

# Get result
advisor result abc123
```

### Configuration commands

```bash
# Show status
advisor status

# Show models
advisor models

# Set default model
advisor config single gemini/gemini-2.5-pro
advisor config compare "openai/gpt-4o,gemini/gemini-2.0-flash"
```

## MCP Integration

### Automatic installation (recommended)

```bash
# Install to Claude Code and Claude Desktop
advisor mcp install

# Project only
advisor mcp install --scope project

# Claude Desktop only
advisor mcp install --target desktop

# Check status
advisor mcp status

# Uninstall
advisor mcp uninstall
```

### Manual configuration

Add to `.mcp.json` (Claude Code):

```json
{
  "mcpServers": {
    "advisor_mcp": {
      "command": "advisor",
      "args": ["run"]
    }
  }
}
```

### MCP Tools

```python
# Single expert
advisor_consult_expert(
    query="Review this code for vulnerabilities",
    context="def get_user(id): ...",
    role="You are a Senior Security Engineer"
)

# Compare experts
advisor_compare_experts(
    query="Redis or in-memory cache for 100 req/hour?",
    models="gemini/gemini-2.0-flash,openai/gpt-4o-mini"
)
```

---

## Use Cases

### Development and Design

| Scenario | Example |
|----------|---------|
| **Stack choice** | `advisor compare "Rust vs Go for microservice"` |
| **Algorithm validation** | `advisor ask "Is there a better solution than O(n²)?" -f algo.py` |
| **Code review** | `git diff \| advisor ask "Review changes"` |

### Brainstorming

| Scenario | Example |
|----------|---------|
| **Alternatives** | `advisor ask "SQL query is slow — suggest 3 solutions"` |
| **Devil's advocate** | `advisor ask "Critique storing JWT in LocalStorage"` |

### Security and Debugging

| Scenario | Example |
|----------|---------|
| **Security audit** | `advisor ask "Find vulnerabilities" -f api.py` |
| **Debugging** | `advisor compare "Why does this code crash?" -f crash.log` |

---

## Specialized Roles

Use system prompts for deeper responses:

```bash
# Via environment variable
ADVISOR_DEFAULT_ROLE="You are a Senior Security Engineer" advisor ask "Review" -f code.py
```

| Task | Role |
|------|------|
| Security | "You are a Senior Security Engineer. Find vulnerabilities." |
| Architecture | "You are a Solution Architect. Evaluate scalability." |
| Performance | "You are a Performance Engineer. Find bottlenecks." |
| Database | "You are a DBA. Evaluate schema and queries." |

---

## Architecture

```
┌─────────────────────────────────────────┐
│              advisor-cli                │
├─────────────────────────────────────────┤
│  CLI (ask, compare, result)             │
│  MCP Server (optional)                  │
├─────────────────────────────────────────┤
│  core.py — LLM logic                    │
├─────────────────────────────────────────┤
│  LiteLLM (unified API)                  │
├─────────┬─────────┬─────────┬───────────┤
│ Gemini  │ OpenAI  │ Ollama  │ DeepSeek  │
└─────────┴─────────┴─────────┴───────────┘
```

## Supported Providers

| Provider | Example models |
|----------|----------------|
| **Gemini** | `gemini/gemini-2.0-flash`, `gemini/gemini-2.5-pro` |
| **OpenAI** | `openai/gpt-4o-mini`, `openai/gpt-4o` |
| **Anthropic** | `anthropic/claude-3-5-haiku` |
| **DeepSeek** | `deepseek/deepseek-chat` |
| **Groq** | `groq/llama-3.3-70b-versatile` |
| **OpenRouter** | `openrouter/google/gemini-2.0-flash` |
| **Ollama** | `ollama/llama3.2` (local) |

---

## License

MIT
