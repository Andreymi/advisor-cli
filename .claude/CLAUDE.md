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

## Available Skills

- `/advisor` — get second opinion from alternative LLMs (Gemini, GPT, Ollama Cloud)
