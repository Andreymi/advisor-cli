# MCP Advisor Project

## Tech Stack
- Python 3.10+ с FastMCP (MCP server framework)
- LiteLLM для мульти-провайдерной поддержки LLM
- Pydantic для валидации данных
- diskcache для кэширования ответов

## Project Structure
- `src/mcp_advisor/server.py` — основной сервер
- `.env` — API ключи для провайдеров (Gemini, OpenAI, Ollama)

## Commands
- `uv run mcp-advisor` — запуск сервера
- `uv sync` — установка зависимостей

## Hooks (автоматизация)
- `PostToolUse` — ruff format/check для .py файлов
- `PreToolUse` — защита .env от редактирования

## Supported Providers
- Gemini (`gemini/gemini-*`)
- OpenAI (`openai/gpt-*`)
- Ollama Cloud (`ollama-cloud/*`)
- DeepSeek (`deepseek/*`)

## Important
- `.env` содержит API ключи — НЕ коммитить, НЕ редактировать через Claude
- Кэш ответов в `.mcp_cache/`

## Available Skills

- `/advisor` — get second opinion from alternative LLMs (Gemini, GPT, Ollama Cloud)
