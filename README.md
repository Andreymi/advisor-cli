# Advisor CLI

Get second opinions from alternative LLMs (Gemini, GPT, DeepSeek, Ollama).

CLI и MCP сервер для получения "второго мнения" от альтернативных LLM.

## Quick Start

```bash
# One-line install (installs uv if needed)
curl -fsSL https://raw.githubusercontent.com/mironovdm/advisor-cli/main/install.sh | sh

# Then configure
advisor setup
advisor mcp install
```

## Возможности

**CLI команды:**
- `advisor ask` — получить ответ от одной модели
- `advisor compare` — сравнить ответы нескольких моделей
- `advisor mcp install` — установить MCP в Claude Code/Desktop

**Дополнительно:**
- Stdin pipe: `cat file.py | advisor ask "Review"`
- Файловый ввод: `advisor ask -f code.py "Review"`
- Async выполнение: `advisor compare --async`
- JSON/Markdown форматы
- Автоматическая MCP интеграция
- Disk cache с TTL

## Установка

### Рекомендуемый способ (uv tool)

```bash
# Установить uv (если нет)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Установить advisor-cli
uv tool install advisor-cli
```

### Через pip

```bash
# Базовая установка (только CLI)
pip install advisor-cli

# С MCP сервером
pip install advisor-cli[mcp]

# С интерактивным wizard
pip install advisor-cli[wizard]

# Всё включено
pip install advisor-cli[all]
```

### Из исходников

```bash
git clone https://github.com/mironovdm/advisor-cli
cd advisor-cli
uv sync --extra all
```

## Конфигурация

### Интерактивный wizard

```bash
advisor setup
```

### Автоматическая настройка (CI/Scripts)

```bash
# Из переменных окружения
GEMINI_API_KEY=xxx OPENAI_API_KEY=xxx advisor setup -y

# Установить MCP без вопросов
advisor mcp install -y
```

### Ручная настройка (.env)

```bash
# Провайдеры (включены только с ключами)
GEMINI_API_KEY=your_key
OPENAI_API_KEY=your_key
OLLAMA_API_KEY=your_key  # Ollama Cloud

# Модели по умолчанию
ADVISOR_DEFAULT_MODEL=gemini/gemini-2.0-flash
ADVISOR_DEFAULT_MODELS_COMPARE=gemini/gemini-2.0-flash,openai/gpt-4o-mini

# Кэширование
ADVISOR_CACHE_ENABLED=true
ADVISOR_CACHE_TTL=3600
```

## CLI использование

### Одиночный запрос

```bash
# Простой вопрос
advisor ask "Как оптимизировать этот запрос?"

# С контекстом из файла
advisor ask "Review this code" -f mycode.py

# Через stdin
cat mycode.py | advisor ask "Find bugs"
git diff | advisor ask "Review changes"

# JSON формат
advisor ask "Question" --format json

# Указать модель
advisor ask "Question" -m openai/gpt-4o
```

### Консилиум (несколько моделей)

```bash
# Сравнить мнения
advisor compare "Redis vs Memcached для кэширования?"

# Указать модели
advisor compare "Question" -m "openai/gpt-4o,gemini/gemini-2.0-flash"

# Async выполнение (в фоне)
advisor compare "Deep analysis" -f big_file.py --async
# => Task ID: abc123

# Получить результат
advisor result abc123
```

### Конфигурация

```bash
# Показать статус
advisor status

# Показать модели
advisor models

# Установить модель по умолчанию
advisor config single gemini/gemini-2.5-pro
advisor config compare "openai/gpt-4o,gemini/gemini-2.0-flash"

# Установить формат по умолчанию
advisor config format json
```

## MCP Integration

### Автоматическая установка (рекомендуется)

```bash
# Установить в Claude Code и Claude Desktop
advisor mcp install

# Только в текущий проект
advisor mcp install --scope project

# Только в Claude Desktop
advisor mcp install --target desktop

# Проверить статус
advisor mcp status

# Удалить
advisor mcp uninstall
```

### Ручная настройка

Добавить в `.mcp.json` (Claude Code):

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
# Один эксперт
advisor_consult_expert(
    query="Оцени этот код на уязвимости",
    context="def get_user(id): ...",
    role="Ты Senior Security Engineer"
)

# Сравнение экспертов
advisor_compare_experts(
    query="Redis или in-memory cache для 100 req/час?",
    models="gemini/gemini-2.0-flash,openai/gpt-4o-mini"
)
```

---

## Use Cases

### Разработка и проектирование

| Сценарий | Пример |
|----------|--------|
| **Выбор стека** | `advisor compare "Rust vs Go для микросервиса"` |
| **Валидация алгоритма** | `advisor ask "Есть ли решение лучше O(n²)?" -f algo.py` |
| **Code review** | `git diff | advisor ask "Review changes"` |

### Brainstorming

| Сценарий | Пример |
|----------|--------|
| **Альтернативы** | `advisor ask "SQL запрос медленный — предложи 3 решения"` |
| **Адвокат дьявола** | `advisor ask "Раскритикуй хранение JWT в LocalStorage"` |

### Security и отладка

| Сценарий | Пример |
|----------|--------|
| **Security audit** | `advisor ask "Найди уязвимости" -f api.py` |
| **Отладка** | `advisor compare "Почему этот код падает?" -f crash.log` |

---

## Специализированные роли

Используйте системный промпт для глубоких ответов:

```bash
# Через переменную окружения
ADVISOR_DEFAULT_ROLE="Ты Senior Security Engineer" advisor ask "Review" -f code.py
```

| Задача | Роль |
|--------|------|
| Security | "Ты Senior Security Engineer. Найди уязвимости." |
| Architecture | "Ты Solution Architect. Оцени масштабируемость." |
| Performance | "Ты Performance Engineer. Найди узкие места." |
| Database | "Ты DBA. Оцени схему и запросы." |

---

## Архитектура

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

## Доступные провайдеры

| Провайдер | Примеры моделей |
|-----------|-----------------|
| **Gemini** | `gemini/gemini-2.0-flash`, `gemini/gemini-2.5-pro` |
| **OpenAI** | `openai/gpt-4o-mini`, `openai/gpt-4o` |
| **Ollama Cloud** | `ollama-cloud/llama3.2` |
| **DeepSeek** | `deepseek/deepseek-chat` |
| **Anthropic** | `anthropic/claude-3-5-haiku` |
| **Groq** | `groq/llama-3.3-70b-versatile` |
| **OpenRouter** | `openrouter/google/gemini-2.0-flash` |

---

## Лицензия

MIT
