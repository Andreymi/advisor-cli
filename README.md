# Advisor CLI

CLI и MCP сервер для получения "второго мнения" от альтернативных LLM (Gemini, GPT, Ollama Cloud).

## Возможности

**CLI команды:**
- `advisor ask` — получить ответ от одной модели
- `advisor compare` — сравнить ответы нескольких моделей
- `advisor result` — получить результат async задачи

**Дополнительно:**
- Stdin pipe: `cat file.py | advisor ask "Review"`
- Файловый ввод: `advisor ask -f code.py "Review"`
- Async выполнение: `advisor compare --async`
- JSON/Markdown форматы
- MCP сервер (опционально)
- Disk cache с TTL

## Установка

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

Или через uv:

```bash
git clone <repo-url>
cd mcp-advisor
uv sync                    # базовая установка
uv pip install -e ".[all]" # с MCP и wizard
```

## Конфигурация

### Интерактивный wizard

```bash
advisor setup
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

## MCP использование

### Подключение к Claude Code

Добавить в `.mcp.json`:

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

Или через uv:

```json
{
  "mcpServers": {
    "advisor_mcp": {
      "command": "uv",
      "args": ["run", "advisor", "run"]
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
