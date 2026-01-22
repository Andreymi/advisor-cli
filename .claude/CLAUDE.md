# Advisor CLI Project

## Tech Stack
- Python 3.10+ с FastMCP (MCP server framework)
- LiteLLM для мульти-провайдерной поддержки LLM
- Pydantic для валидации данных
- diskcache для кэширования ответов
- typer + rich + questionary для CLI

## Project Structure
- `src/advisor_cli/core.py` — логика LLM (без MCP зависимости)
- `src/advisor_cli/server.py` — MCP сервер (optional)
- `src/advisor_cli/cli.py` — CLI интерфейс
- `src/advisor_cli/setup_wizard.py` — интерактивный wizard
- `src/advisor_cli/file_utils.py` — работа с файлами
- `.env` — API ключи для провайдеров

## Commands
- `advisor ask "query"` — одиночный запрос к LLM
- `advisor compare "query"` — консилиум нескольких моделей
- `advisor result <id>` — получить результат async задачи
- `advisor config single <model>` — установить модель по умолчанию
- `advisor config compare <models>` — установить модели для консилиума
- `advisor models` — показать конфигурацию моделей
- `advisor setup` — интерактивная настройка
- `advisor setup -y` — неинтерактивная настройка из env vars
- `advisor mcp install` — установить MCP в Claude Code/Desktop
- `advisor mcp uninstall` — удалить MCP из конфигов
- `advisor mcp status` — показать статус MCP интеграции
- `advisor run` — запуск MCP сервера (требует `[mcp]`)
- `advisor status` — показать статус
- `uv sync` — установка зависимостей
- `uv run pytest tests/ -v` — запуск тестов

## CLI Features
- Stdin pipe: `cat code.py | advisor ask "Review this"`
- File input: `advisor ask -f code.py "Review"`
- Async mode: `advisor ask --async "Long query"` → `advisor result <id>`
- Formats: `--format json|markdown`

## Optional Dependencies
- `pip install .` — базовый CLI без MCP
- `pip install .[mcp]` — с MCP сервером
- `pip install .[wizard]` — с интерактивным wizard
- `pip install .[all]` — всё

## Hooks (автоматизация)
- `PostToolUse` — ruff format/check для .py файлов
- `PreToolUse` — защита .env от редактирования

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

### GigaChat (advanced)
GigaChat требует отдельного пакета `litellm-gigachat`:
```bash
pip install litellm-gigachat
litellm-gigachat  # запуск прокси на :4000
```
Затем использовать через OpenRouter или custom provider.

## Important
- `.env` содержит API ключи — НЕ коммитить, НЕ редактировать через Claude
- Кэш ответов в `.mcp_cache/`

## Available Skills

- `/advisor` — get second opinion from alternative LLMs (Gemini, GPT, Ollama Cloud)
