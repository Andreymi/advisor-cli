# Advisor CLI — Roadmap развития

> Рекомендации собраны на основе консультаций с экспертами (Gemini, GPT-4o) и анализа возможностей LiteLLM.

---

## Текущее состояние

**Реализовано:**

*CLI команды:*
- `advisor ask` — консультация с одной моделью
- `advisor compare` — параллельный запрос к нескольким моделям
- `advisor result` — получение результата async задачи
- `advisor status` / `advisor models` — информация о конфигурации
- `advisor config single/compare/format` — настройка моделей
- `advisor setup` — интерактивный wizard (опционально)
- `advisor run` — запуск MCP сервера (опционально)

*Возможности:*
- Stdin pipe: `cat file.py | advisor ask "Review"`
- Файловый ввод: `advisor ask -f code.py "Review"`
- Async выполнение: `advisor compare --async`
- JSON/Markdown форматы: `--format json`
- Disk cache с TTL
- Поддержка провайдеров: Gemini, OpenAI, DeepSeek, Ollama, Anthropic, Groq, OpenRouter

*MCP инструменты:*
- `advisor_consult_expert` — консультация с одной моделью
- `advisor_compare_experts` — параллельный запрос к нескольким моделям

**Архитектура:**
- `core.py` — логика LLM (без зависимости от MCP)
- `cli.py` — CLI интерфейс
- `server.py` — MCP сервер (опциональная зависимость)
- Optional deps: `[mcp]`, `[wizard]`, `[all]`

**Используется:** базовый `acompletion()` из LiteLLM

---

## Приоритет P0 — Критично

### 1. LiteLLM Router (Отказоустойчивость)

**Зачем:** Автоматический fallback, load balancing, умные ретраи.

```python
from litellm import Router

model_list = [
    {
        "model_name": "gpt-4o",  # виртуальное имя для группы
        "litellm_params": {"model": "openai/gpt-4o", "api_key": "..."},
        "tpm": 60000, "rpm": 500
    },
    {
        "model_name": "gpt-4o",  # тот же алиас = автофейловер
        "litellm_params": {"model": "azure/gpt-4o", "api_key": "..."},
    },
    {
        "model_name": "cheap-models",
        "litellm_params": {"model": "gemini/gemini-2.0-flash"},
    }
]

router = Router(
    model_list=model_list,
    routing_strategy="latency-based-routing",  # или "least-busy"
    num_retries=3,
    fallbacks=[{"gpt-4o": ["gemini/gemini-2.0-flash"]}],
    context_window_fallbacks=[{"gpt-4o": ["cheap-models"]}],
    timeout=30
)

# Использование
response = await router.acompletion(model="gpt-4o", messages=messages)
```

**Что даёт:**
- Автоматический fallback между провайдерами
- Load balancing по TPM/RPM лимитам
- Latency-based routing — выбор самого быстрого
- Cooldown для упавших endpoint'ов

---

### 2. Callbacks и Cost Tracking

**Зачем:** Понимать стоимость запросов, собирать аналитику.

```python
import litellm
from litellm.integrations.custom_logger import CustomLogger

class AdvisorLogger(CustomLogger):
    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        cost = kwargs.get("response_cost", 0)
        model = kwargs.get("model")
        latency_ms = (end_time - start_time).total_seconds() * 1000

        # Логирование / сохранение в БД / Prometheus
        print(f"Model: {model}, Cost: ${cost:.6f}, Latency: {latency_ms:.0f}ms")

    def log_failure_event(self, kwargs, response_obj, start_time, end_time):
        error = kwargs.get("exception")
        model = kwargs.get("model")
        print(f"Error in {model}: {error}")

litellm.callbacks = [AdvisorLogger()]
```

**Новый инструмент `advisor_stats`:**
```python
@mcp.tool(name="advisor_stats")
async def advisor_stats() -> str:
    """Возвращает статистику использования сервера."""
    return {
        "total_cost_usd": ...,
        "requests_by_model": {...},
        "avg_latency_by_model": {...},
        "cache_hit_rate": ...,
    }
```

---

## Приоритет P1 — Важно

### 3. Budget Manager

**Зачем:** Защита от "сбежавших" запросов, контроль расходов.

```python
from litellm import BudgetManager

budget_manager = BudgetManager(project_name="mcp_advisor", type="local")

# Установить бюджет
budget_manager.create_budget(
    user="default",
    total_budget=10.0,  # $10 в месяц
    budget_duration="monthly"
)

# Проверка перед запросом
if budget_manager.get_current_cost(user) <= budget_manager.get_total_budget(user):
    response = await router.acompletion(...)
    budget_manager.update_cost(completion_obj=response, user=user)
else:
    return "Budget exceeded"
```

---

### 4. Vision / Multimodal Support

**Зачем:** Анализ скриншотов UI, диаграмм архитектуры, ошибок в консоли.

```python
import base64

class ConsultExpertInput(BaseModel):
    # ... existing fields
    image_url: Optional[str] = Field(default=None, description="URL изображения")
    image_base64: Optional[str] = Field(default=None, description="Base64 изображения")

def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode('utf-8')

async def consult_with_vision(model: str, text: str, image_path: str = None):
    content = [{"type": "text", "text": text}]

    if image_path:
        base64_image = encode_image(image_path)
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
        })

    messages = [{"role": "user", "content": content}]

    # LiteLLM сам конвертирует формат для Gemini/Claude/GPT
    return await router.acompletion(model=model, messages=messages)
```

---

### 5. Retry Policy (тонкая настройка)

```python
from litellm.router import RetryPolicy, AllowedFailsPolicy

retry_policy = RetryPolicy(
    RateLimitErrorRetries=5,      # 429 — много ретраев
    TimeoutErrorRetries=3,
    ContentPolicyViolationErrorRetries=0,  # не ретраить
    AuthenticationErrorRetries=0,
)

allowed_fails_policy = AllowedFailsPolicy(
    RateLimitErrorAllowedFails=100,
    ContentPolicyViolationErrorAllowedFails=1000,
)

router = Router(
    model_list=model_list,
    retry_policy=retry_policy,
    allowed_fails_policy=allowed_fails_policy,
)
```

---

## Приоритет P2 — Полезно

### 6. Streaming (потоковые ответы)

```python
@mcp.tool(name="advisor_consult_expert_stream")
async def advisor_consult_expert_stream(params: ConsultExpertInput):
    """Потоковая консультация — ответ приходит по частям."""

    response = await acompletion(
        messages=messages,
        stream=True,
        **kwargs
    )

    full_response = ""
    async for chunk in response:
        if chunk.choices[0].delta.content:
            full_response += chunk.choices[0].delta.content

    return full_response
```

---

### 7. Model Info — информация о моделях

```python
from litellm import get_model_info, model_cost

@mcp.tool(name="advisor_model_info")
async def advisor_model_info(model: str) -> str:
    """Информация о модели: лимиты, стоимость, возможности."""
    info = get_model_info(model)
    cost = model_cost.get(model, {})

    return {
        "max_tokens": info.get("max_tokens"),
        "supports_vision": info.get("supports_vision"),
        "supports_function_calling": info.get("supports_function_calling"),
        "input_cost_per_token": cost.get("input_cost_per_token"),
        "output_cost_per_token": cost.get("output_cost_per_token"),
    }
```

---

### 8. Ensemble — комбинирование ответов

```python
@mcp.tool(name="advisor_ensemble")
async def advisor_ensemble(params: EnsembleInput) -> str:
    """Собирает ответы от нескольких моделей и создаёт синтез."""
    responses = await advisor_compare_experts(params)

    meta_prompt = f"""Проанализируй ответы экспертов и создай синтезированный ответ:
    {responses}

    Выдели: консенсус, расхождения, итоговую рекомендацию."""

    return await router.acompletion(
        model="gemini/gemini-2.0-flash",
        messages=[{"role": "user", "content": meta_prompt}]
    )
```

---

## Приоритет P3 — На будущее

### 9. CLI: Streaming Output

```bash
advisor ask "Explain X" --stream
# Ответ выводится по мере генерации
```

### 10. CLI: Interactive Mode (REPL)

```bash
advisor chat
# Интерактивный режим с историей
> Объясни async/await
[ответ]
> А как это работает с aiohttp?
[ответ с контекстом предыдущего вопроса]
```

### 11. CLI: Pipe Chain

```bash
git diff | advisor ask "Review" | advisor ask "Summarize in 3 points"
```

### 13. Function Calling / Tools

Позволить LLM вызывать внешние функции для получения актуальных данных:
- Поиск в документации
- Проверка версий библиотек
- Запрос к внешним API

### 14. Dynamic Routing

Автоматический выбор модели на основе типа задачи:
```python
TASK_MODEL_MAP = {
    "code_review": "openai/gpt-4o",
    "creative": "anthropic/claude-3",
    "math": "gemini/gemini-2.0-flash",
    "fast": "openai/gpt-4o-mini"
}
```

### 15. Debate Mode

Организация дискуссии между моделями для глубокого анализа.

---

## Структура файлов после расширения

```
src/advisor_cli/
├── __init__.py
├── core.py             # Логика LLM (без MCP)
├── cli.py              # CLI интерфейс
├── server.py           # MCP сервер (опционально)
├── setup_wizard.py     # Интерактивный wizard (опционально)
├── file_utils.py       # Работа с файлами
├── router.py           # Конфигурация Router (NEW)
├── tools/
│   ├── __init__.py
│   ├── ensemble.py     # advisor ensemble (NEW)
│   ├── stats.py        # advisor stats (NEW)
│   └── model_info.py   # advisor model-info (NEW)
├── analytics/
│   ├── __init__.py
│   ├── callbacks.py    # Custom callbacks
│   └── budget.py       # Budget management
└── config/
    └── models.yaml     # Конфигурация моделей для Router
```

---

## Таблица приоритетов

| Приоритет | Фича | Сложность | Ценность |
|-----------|-------|-----------|----------|
| **P0** | Router + Fallback | Средняя | Критично |
| **P0** | Callbacks + Cost | Низкая | Высокая |
| **P1** | Budget Manager | Низкая | Средняя |
| **P1** | Vision | Низкая | Высокая |
| **P1** | Retry Policy | Низкая | Средняя |
| **P2** | Streaming | Средняя | Средняя |
| **P2** | Model Info | Низкая | Средняя |
| **P2** | Ensemble | Низкая | Высокая |
| **P3** | CLI: Streaming | Средняя | Высокая |
| **P3** | CLI: Interactive/REPL | Средняя | Высокая |
| **P3** | CLI: Pipe Chain | Низкая | Средняя |
| **P3** | Function Calling | Высокая | Средняя |
| **P3** | Dynamic Routing | Высокая | Средняя |
| **P3** | Debate Mode | Средняя | Средняя |

---

## Консенсус экспертов

**Gemini и GPT-4o согласны:**
1. **Router — самое важное.** Замена `acompletion` на `router.acompletion` без изменения бизнес-логики.
2. **Callbacks уже сегодня.** Статистика накапливается быстро и помогает оптимизировать выбор моделей.
3. **Вынести конфиг в YAML.** Централизованное управление моделями.

**Расхождение:** GPT-4o акцентирует compliance (GDPR, этичный AI), Gemini — на технических деталях реализации.

---

*Последнее обновление: 2026-01-22*
