#!/usr/bin/env python3
'''
MCP Server для получения "второго мнения" от альтернативных LLM.

Сервер предоставляет инструменты для консультации с различными LLM моделями.
Доступны только те провайдеры, для которых указаны API ключи в .env.
'''

from typing import Optional
from enum import Enum
import asyncio
import hashlib
import os
import json
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP
from litellm import acompletion
from litellm.caching.caching import Cache
import litellm

# ===== Загрузка .env =====
# Ищем .env в директории проекта (рядом с pyproject.toml)
_project_root = Path(__file__).parent.parent.parent
_env_file = _project_root / ".env"
if _env_file.exists():
    load_dotenv(_env_file)
else:
    # Попробуем текущую директорию
    load_dotenv()

# ===== Инициализация сервера =====
mcp = FastMCP("advisor_mcp")

# ===== Логирование =====
litellm.set_verbose = os.getenv("ADVISOR_VERBOSE", "false").lower() == "true"

# ===== Роль эксперта =====
DEFAULT_ROLE = os.getenv(
    "ADVISOR_DEFAULT_ROLE",
    "Ты опытный технический консультант. Твоя задача — дать критическую оценку, найти ошибки или предложить лучшее решение."
)


def _hash_prompt(text: str) -> str:
    """Генерирует короткий хэш для инвалидации кэша при смене промпта."""
    return hashlib.sha256(text.encode()).hexdigest()[:8]


# Версия кэша — автоматически меняется при изменении DEFAULT_ROLE
PROMPT_VERSION = _hash_prompt(DEFAULT_ROLE)

# ===== Кэширование =====
CACHE_ENABLED = os.getenv("ADVISOR_CACHE_ENABLED", "true").lower() == "true"
CACHE_TTL = int(os.getenv("ADVISOR_CACHE_TTL", "3600"))
CACHE_DIR = _project_root / ".mcp_cache"


def _init_cache() -> bool:
    """Инициализация кэша с graceful degradation."""
    if not CACHE_ENABLED:
        return False

    try:
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            litellm.cache = Cache(type="redis", url=redis_url, ttl=CACHE_TTL)
        else:
            # Disk cache — персистентный, переживает перезапуски
            CACHE_DIR.mkdir(exist_ok=True)
            litellm.cache = Cache(type="disk", disk_cache_dir=str(CACHE_DIR), ttl=CACHE_TTL)
        return True
    except Exception as e:
        print(f"[advisor_mcp] Cache init failed: {e}. Continuing without cache.")
        return False


CACHE_ACTIVE = _init_cache()

# ===== Конфигурация провайдеров =====
# Провайдер включён только если указан API ключ в .env

PROVIDERS = {
    "gemini": {
        "env_key": "GEMINI_API_KEY",
        "enabled": bool(os.getenv("GEMINI_API_KEY")),
    },
    "openai": {
        "env_key": "OPENAI_API_KEY",
        "enabled": bool(os.getenv("OPENAI_API_KEY")),
    },
    "deepseek": {
        "env_key": "DEEPSEEK_API_KEY",
        "enabled": bool(os.getenv("DEEPSEEK_API_KEY")),
    },
    "ollama": {
        "env_key": "OLLAMA_HOST",  # локальный Ollama
        "enabled": bool(os.getenv("OLLAMA_HOST")),
    },
    "ollama-cloud": {
        "env_key": "OLLAMA_API_KEY",
        "enabled": bool(os.getenv("OLLAMA_API_KEY")),
    },
    "anthropic": {
        "env_key": "ANTHROPIC_API_KEY",
        "enabled": bool(os.getenv("ANTHROPIC_API_KEY")),
    },
}

# Ollama Cloud настройки
OLLAMA_CLOUD_BASE = os.getenv("OLLAMA_CLOUD_BASE_URL", "https://ollama.com/v1")

# Список включённых провайдеров
ENABLED_PROVIDERS = [name for name, cfg in PROVIDERS.items() if cfg["enabled"]]

# ===== Модели по умолчанию =====
# gemini/gemini-2.0-flash, openai/gpt-4o-mini, ollama-cloud/gpt-oss:120b-cloud
DEFAULT_MODEL = os.getenv("ADVISOR_DEFAULT_MODEL", "gemini/gemini-2.0-flash")
DEFAULT_MODELS_COMPARE = os.getenv("ADVISOR_DEFAULT_MODELS_COMPARE", "gemini/gemini-2.0-flash,openai/gpt-4o-mini")


# ===== Enums =====
class ResponseFormat(str, Enum):
    '''Формат ответа от эксперта.'''
    MARKDOWN = "markdown"
    JSON = "json"


# ===== Утилиты =====
def _get_provider(model: str) -> str:
    '''Извлекает имя провайдера из модели (gemini/model -> gemini).'''
    return model.split("/")[0] if "/" in model else model


def _check_model_allowed(model: str) -> str | None:
    '''Проверяет доступность модели. Возвращает ошибку или None.'''
    provider = _get_provider(model)

    if provider not in PROVIDERS:
        return f"Неизвестный провайдер: {provider}. Доступные: {', '.join(PROVIDERS.keys())}"

    if not PROVIDERS[provider]["enabled"]:
        env_key = PROVIDERS[provider]["env_key"]
        return f"Провайдер '{provider}' не включён. Добавьте {env_key} в .env"

    return None


def _get_enabled_models_hint() -> str:
    '''Возвращает подсказку о доступных провайдерах.'''
    if not ENABLED_PROVIDERS:
        return "Нет включённых провайдеров. Добавьте API ключи в .env"
    return f"Доступные провайдеры: {', '.join(ENABLED_PROVIDERS)}"


def _get_completion_kwargs(model: str) -> dict:
    '''Возвращает параметры для completion в зависимости от модели.'''
    if model.startswith("ollama-cloud/"):
        actual_model = model.replace("ollama-cloud/", "openai/")
        return {
            "model": actual_model,
            "api_base": OLLAMA_CLOUD_BASE,
            "api_key": os.getenv("OLLAMA_API_KEY"),
        }
    return {"model": model}


def _format_error(e: Exception) -> str:
    '''Форматирует ошибку с понятным сообщением.'''
    error_msg = str(e)
    if "401" in error_msg or "Unauthorized" in error_msg:
        return "Ошибка: Неверный API ключ. Проверьте переменные окружения."
    elif "429" in error_msg or "rate limit" in error_msg.lower():
        return "Ошибка: Превышен лимит запросов. Подождите и попробуйте снова."
    elif "timeout" in error_msg.lower():
        return "Ошибка: Таймаут запроса. Попробуйте позже."
    return f"Ошибка: {error_msg}"


# Бюджет токенов для thinking по уровням
THINKING_BUDGETS = {
    "low": 1024,
    "medium": 4096,
    "high": 16000,
}

# ===== Справочник reasoning моделей =====
# Формат: паттерн в имени модели -> тип параметра ("thinking" или "reasoning_effort")
KNOWN_REASONING_MODELS = {
    # Anthropic (только Sonnet и Opus, не Haiku)
    "sonnet": "thinking",
    "opus": "thinking",
    # DeepSeek семейство
    "deepseek-r1": "thinking",
    "deepseek-v3": "thinking",
    # Kimi
    "kimi-k2-thinking": "thinking",
    "kimi-k2": "thinking",
    # MiniMax
    "minimax-m2": "thinking",
    # Qwen QwQ
    "qwq": "thinking",
    # OpenAI reasoning
    "o1-": "reasoning_effort",
    "o3-": "reasoning_effort",
    # Gemini thinking models
    "gemini-2.5": "thinking",
    "gemini-3": "thinking",
    # Общие паттерны
    "thinking": "thinking",
    "reasoner": "thinking",
}

# Disk cache для автообнаруженных моделей
REASONING_CACHE_FILE = CACHE_DIR / "reasoning_models.json"
_reasoning_cache: dict[str, Optional[str]] = {}  # model -> type или None


def _load_reasoning_cache() -> dict[str, Optional[str]]:
    """Загружает кэш автообнаруженных reasoning моделей."""
    try:
        if REASONING_CACHE_FILE.exists():
            with open(REASONING_CACHE_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_reasoning_cache():
    """Сохраняет кэш автообнаруженных reasoning моделей."""
    try:
        CACHE_DIR.mkdir(exist_ok=True)
        with open(REASONING_CACHE_FILE, 'w') as f:
            json.dump(_reasoning_cache, f, indent=2)
    except Exception:
        pass


# Загружаем кэш при старте
_reasoning_cache = _load_reasoning_cache()


def _get_reasoning_type_from_registry(model: str) -> Optional[str]:
    """Ищет тип reasoning в справочнике по паттернам в имени модели."""
    model_lower = model.lower()
    for pattern, reasoning_type in KNOWN_REASONING_MODELS.items():
        if pattern in model_lower:
            return reasoning_type
    return None


def _is_model_cached(model: str) -> bool:
    """Проверяет, есть ли модель в кэше (независимо от значения)."""
    return model in _reasoning_cache


def _get_reasoning_type(model: str) -> Optional[str]:
    """
    Определяет тип reasoning для модели.
    Приоритет: disk cache -> справочник -> auto_detect
    """
    # 1. Из disk cache (автообнаруженные ранее) — приоритет
    if model in _reasoning_cache:
        return _reasoning_cache[model]

    # 2. Из справочника (по паттернам в имени)
    from_registry = _get_reasoning_type_from_registry(model)
    if from_registry:
        return from_registry

    # 3. Все остальные — auto_detect
    # Даже anthropic: Haiku не поддерживает thinking, только Sonnet/Opus
    return None


def _cache_reasoning_type(model: str, reasoning_type: Optional[str]):
    """Сохраняет тип reasoning модели в кэш."""
    if model not in _reasoning_cache:
        _reasoning_cache[model] = reasoning_type
        _save_reasoning_cache()


def _get_reasoning_kwargs(model: str, reasoning: Optional[str]) -> dict:
    """Конвертирует уровень reasoning в параметры для конкретной модели."""
    if not reasoning:
        return {}

    reasoning_type = _get_reasoning_type(model)
    budget = THINKING_BUDGETS.get(reasoning, 4096)

    if reasoning_type == "thinking":
        return {"thinking": {"type": "enabled", "budget_tokens": budget}}
    elif reasoning_type == "reasoning_effort":
        return {"reasoning_effort": reasoning}
    elif _is_model_cached(model):
        # Модель в кэше с None — точно не поддерживает reasoning
        return {}

    # Неизвестная модель — пробуем thinking (автообнаружение по ответу)
    return {"thinking": {"type": "enabled", "budget_tokens": budget}, "_auto_detect": True}


def _extract_reasoning(response) -> Optional[str]:
    """Извлекает reasoning_content из ответа (DeepSeek-R1, xAI и др.)."""
    message = response.choices[0].message
    return getattr(message, 'reasoning_content', None)


async def _completion_with_auto_detect(
    model: str,
    messages: list,
    reasoning: Optional[str],
    **extra_kwargs
) -> tuple[any, Optional[str]]:
    """
    Выполняет completion с автообнаружением reasoning поддержки.
    Возвращает (response, reasoning_content).
    При ошибке с неизвестной моделью — retry без reasoning параметров.
    """
    kwargs = _get_completion_kwargs(model)
    kwargs["metadata"] = {"prompt_version": PROMPT_VERSION}
    kwargs.update(extra_kwargs)

    # Получаем параметры reasoning
    reasoning_kwargs = _get_reasoning_kwargs(model, reasoning)
    auto_detect = reasoning_kwargs.pop("_auto_detect", False)

    if reasoning_kwargs:
        kwargs.update(reasoning_kwargs)

    try:
        response = await acompletion(messages=messages, caching=CACHE_ACTIVE, **kwargs)
        reasoning_content = _extract_reasoning(response)

        # Автообнаружение: успех — кэшируем тип
        if auto_detect and reasoning:
            _cache_reasoning_type(model, "thinking")

        return response, reasoning_content

    except Exception as e:
        error_str = str(e).lower()
        is_param_error = any(x in error_str for x in [
            "thinking", "budget_tokens", "reasoning_effort",
            "unsupported", "invalid parameter", "unknown parameter"
        ])

        # Если ошибка из-за параметра и это автообнаружение — retry без reasoning
        if auto_detect and is_param_error and reasoning_kwargs:
            # Убираем reasoning параметры и пробуем снова
            for key in reasoning_kwargs:
                kwargs.pop(key, None)

            response = await acompletion(messages=messages, caching=CACHE_ACTIVE, **kwargs)
            # Кэшируем что модель не поддерживает reasoning
            _cache_reasoning_type(model, None)
            return response, None

        raise


# ===== Pydantic Models =====
class ConsultExpertInput(BaseModel):
    '''Входные параметры для консультации с экспертом.'''
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    query: str = Field(
        ...,
        description="Вопрос к эксперту (например: 'Как улучшить этот код?', 'Есть ли тут ошибки?')",
        min_length=1,
        max_length=10000
    )
    context: Optional[str] = Field(
        default="",
        description="Контекст задачи или код для анализа",
        max_length=100000
    )
    model: str = Field(
        default=DEFAULT_MODEL,
        description="Модель LLM: gemini/gemini-2.0-flash, openai/gpt-4o, ollama/llama3.2, ollama-cloud/llama3.2, deepseek/deepseek-chat"
    )
    role: str = Field(
        default=DEFAULT_ROLE,
        description="Роль/персона эксперта (system prompt)",
        max_length=2000
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Формат ответа: markdown (читаемый) или json (структурированный)"
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Уровень reasoning для thinking-моделей: low, medium, high. Автоматически конвертируется в нужный формат для модели.",
        pattern="^(low|medium|high)$"
    )


class CompareExpertsInput(BaseModel):
    '''Входные параметры для сравнения мнений экспертов.'''
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    query: str = Field(
        ...,
        description="Вопрос к экспертам",
        min_length=1,
        max_length=10000
    )
    context: Optional[str] = Field(
        default="",
        description="Контекст задачи или код для анализа",
        max_length=100000
    )
    models: str = Field(
        default=DEFAULT_MODELS_COMPARE,
        description="Модели через запятую (например: gemini/gemini-2.0-flash,openai/gpt-4o)"
    )
    role: str = Field(
        default=DEFAULT_ROLE,
        description="Роль/персона экспертов (system prompt)",
        max_length=2000
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Формат ответа: markdown или json"
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Уровень reasoning для thinking-моделей: low, medium, high. Автоматически конвертируется в нужный формат для модели.",
        pattern="^(low|medium|high)$"
    )


# ===== Tools =====
@mcp.tool(
    name="advisor_consult_expert",
    annotations={
        "title": "Консультация с экспертом",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True
    }
)
async def advisor_consult_expert(params: ConsultExpertInput) -> str:
    '''
    Консультируется с внешней экспертной LLM моделью.

    Используй для получения "второго мнения", критики кода, альтернативного
    решения или экспертной оценки от другой модели (Gemini, OpenAI, Ollama, DeepSeek).

    Args:
        params (ConsultExpertInput): Параметры запроса:
            - query (str): Вопрос к эксперту
            - context (str): Контекст или код для анализа
            - model (str): Модель LLM (gemini/gemini-2.0-flash, openai/gpt-4o, и др.)
            - role (str): System prompt для эксперта
            - response_format (str): markdown или json

    Returns:
        str: Ответ от эксперта в выбранном формате

    Examples:
        - "Проверь этот код на ошибки" + код в context
        - "Как лучше реализовать кэширование?"
        - "Сравни подходы A и B для этой задачи"
    '''
    # Проверка что модель указана
    if not params.model:
        return f"Ошибка: Модель не указана. {_get_enabled_models_hint()}"

    # Проверка что провайдер включён
    error = _check_model_allowed(params.model)
    if error:
        return f"Ошибка: {error}"

    messages = [
        {"role": "system", "content": params.role},
        {"role": "user", "content": f"{params.query}\n\nКонтекст:\n{params.context}" if params.context else params.query}
    ]

    try:
        response, reasoning_content = await _completion_with_auto_detect(
            model=params.model,
            messages=messages,
            reasoning=params.reasoning
        )
        answer = response.choices[0].message.content

        if params.response_format == ResponseFormat.JSON:
            result = {
                "model": params.model,
                "query": params.query,
                "answer": answer,
                "cached": getattr(response, '_hidden_params', {}).get('cache_hit', False)
            }
            if reasoning_content:
                result["reasoning"] = reasoning_content
            return json.dumps(result, ensure_ascii=False, indent=2)

        # Добавляем reasoning в markdown если есть
        output = f"## Ответ от {params.model}\n\n"
        if reasoning_content:
            output += f"<details>\n<summary>💭 Reasoning</summary>\n\n{reasoning_content}\n\n</details>\n\n"
        output += answer
        return output
    except Exception as e:
        return _format_error(e)


@mcp.tool(
    name="advisor_compare_experts",
    annotations={
        "title": "Сравнение мнений экспертов",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True
    }
)
async def advisor_compare_experts(params: CompareExpertsInput) -> str:
    '''
    Получает мнения от нескольких LLM моделей параллельно и сравнивает их.

    Используй когда нужно получить разные точки зрения на одну проблему
    от нескольких моделей одновременно.

    Args:
        params (CompareExpertsInput): Параметры запроса:
            - query (str): Вопрос к экспертам
            - context (str): Контекст или код для анализа
            - models (str): Модели через запятую
            - role (str): System prompt для экспертов
            - response_format (str): markdown или json

    Returns:
        str: Ответы от всех моделей в выбранном формате

    Examples:
        - models="gemini/gemini-2.0-flash,openai/gpt-4o" для сравнения двух моделей
        - models="ollama/llama3.2,deepseek/deepseek-chat" для сравнения open-source
    '''
    # Проверка что модели указаны
    if not params.models:
        return f"Ошибка: Модели не указаны. {_get_enabled_models_hint()}"

    model_list = [m.strip() for m in params.models.split(",") if m.strip()]

    if not model_list:
        return f"Ошибка: Список моделей пуст. {_get_enabled_models_hint()}"

    messages = [
        {"role": "system", "content": params.role},
        {"role": "user", "content": f"{params.query}\n\nКонтекст:\n{params.context}" if params.context else params.query}
    ]

    async def ask_model(model: str) -> tuple[str, str, Optional[str], bool]:
        # Проверка что провайдер включён
        error = _check_model_allowed(model)
        if error:
            return model, f"Ошибка: {error}", None, True

        try:
            response, reasoning_content = await _completion_with_auto_detect(
                model=model,
                messages=messages,
                reasoning=params.reasoning
            )
            return model, response.choices[0].message.content, reasoning_content, False
        except Exception as e:
            return model, _format_error(e), None, True

    results = await asyncio.gather(*[ask_model(m) for m in model_list])

    if params.response_format == ResponseFormat.JSON:
        return json.dumps({
            "query": params.query,
            "experts": [
                {"model": model, "answer": answer, "reasoning": reasoning, "error": is_error}
                for model, answer, reasoning, is_error in results
            ]
        }, ensure_ascii=False, indent=2)

    output = [f"# Сравнение мнений экспертов\n\n**Вопрос:** {params.query}\n"]
    for model, answer, reasoning, is_error in results:
        status = "❌" if is_error else "✅"
        section = f"---\n\n## {status} {model}\n\n"
        if reasoning:
            section += f"<details>\n<summary>💭 Reasoning</summary>\n\n{reasoning}\n\n</details>\n\n"
        section += f"{answer}\n"
        output.append(section)
    return "\n".join(output)


def main():
    '''Точка входа для запуска MCP сервера.'''
    mcp.run()


if __name__ == "__main__":
    main()
