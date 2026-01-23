#!/usr/bin/env python3
"""
Core LLM logic for advisor-cli.

This module contains all LLM-related functionality without MCP dependencies.
"""

from typing import Optional
from enum import Enum
import asyncio
import hashlib
import os
import json

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ConfigDict
from litellm import acompletion
import litellm

from .config import CACHE_DIR, CONFIG_FILE

# ===== Загрузка конфигурации =====
# Загружаем из XDG-совместимого пути (~/.config/advisor/config.env)
if CONFIG_FILE.exists():
    load_dotenv(CONFIG_FILE)
else:
    # Fallback на переменные окружения
    load_dotenv()

# ===== Логирование =====
litellm.set_verbose = os.getenv("ADVISOR_VERBOSE", "false").lower() == "true"

# ===== Роль эксперта =====
DEFAULT_ROLE = os.getenv(
    "ADVISOR_DEFAULT_ROLE",
    "Ты опытный технический консультант. Твоя задача — дать критическую оценку, найти ошибки или предложить лучшее решение.",
)


def _hash_prompt(text: str) -> str:
    """Generate short hash for cache invalidation when prompt changes."""
    return hashlib.sha256(text.encode()).hexdigest()[:8]


# Версия кэша — автоматически меняется при изменении DEFAULT_ROLE
PROMPT_VERSION = _hash_prompt(DEFAULT_ROLE)

# ===== Кэширование =====
CACHE_ENABLED = os.getenv("ADVISOR_CACHE_ENABLED", "true").lower() == "true"
CACHE_TTL = int(os.getenv("ADVISOR_CACHE_TTL", "3600"))
# CACHE_DIR импортирован из config.py (~/.cache/advisor)
CACHE_ACTIVE = False


def init_cache() -> bool:
    """Initialize cache with graceful degradation."""
    global CACHE_ACTIVE

    if not CACHE_ENABLED:
        return False

    try:
        from litellm.caching.caching import Cache

        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            litellm.cache = Cache(type="redis", url=redis_url, ttl=CACHE_TTL)
        else:
            CACHE_DIR.mkdir(exist_ok=True)
            litellm.cache = Cache(
                type="disk", disk_cache_dir=str(CACHE_DIR), ttl=CACHE_TTL
            )
        CACHE_ACTIVE = True
        return True
    except (ImportError, OSError, PermissionError) as e:
        print(f"[advisor] Cache init failed: {e}. Continuing without cache.")
        return False


# ===== Конфигурация провайдеров =====
# Import here to avoid circular imports (PROVIDER_INFO is now in config.py)
from .config import PROVIDER_INFO


def _build_providers() -> dict:
    """Build PROVIDERS dict from PROVIDER_INFO."""
    providers = {}
    for pid, info in PROVIDER_INFO.items():
        env_key = info.get("env_key")
        providers[pid] = {
            "env_key": env_key,
            "enabled": bool(os.getenv(env_key)) if env_key else False,
        }
    return providers


PROVIDERS = _build_providers()

CUSTOM_PROVIDERS = [
    p.strip() for p in os.getenv("ADVISOR_CUSTOM_PROVIDERS", "").split(",") if p.strip()
]

OLLAMA_CLOUD_BASE = os.getenv("OLLAMA_CLOUD_BASE_URL", "https://ollama.com/v1")

ENABLED_PROVIDERS = [name for name, cfg in PROVIDERS.items() if cfg["enabled"]]

# ===== Модели по умолчанию =====
DEFAULT_MODEL = os.getenv("ADVISOR_DEFAULT_MODEL", "gemini/gemini-2.0-flash")
DEFAULT_MODELS_COMPARE = os.getenv(
    "ADVISOR_DEFAULT_MODELS_COMPARE", "gemini/gemini-2.0-flash,openai/gpt-4o-mini"
)


# ===== Enums =====
class ResponseFormat(str, Enum):
    """Response format from expert."""

    MARKDOWN = "markdown"
    JSON = "json"


# ===== Утилиты =====
def get_provider(model: str) -> str:
    """Extract provider name from model (gemini/model -> gemini)."""
    return model.split("/")[0] if "/" in model else model


def check_model_allowed(model: str) -> str | None:
    """Check if model is allowed. Returns error message or None."""
    provider = get_provider(model)

    if provider in PROVIDERS:
        if not PROVIDERS[provider]["enabled"]:
            env_key = PROVIDERS[provider]["env_key"]
            return f"Провайдер '{provider}' не включён. Добавьте {env_key} в .env"
        return None

    if provider in CUSTOM_PROVIDERS:
        return None

    return f"Неизвестный провайдер: {provider}. Доступные: {', '.join(list(PROVIDERS.keys()) + CUSTOM_PROVIDERS)}"


def get_enabled_models_hint() -> str:
    """Return hint about available providers."""
    all_enabled = ENABLED_PROVIDERS + CUSTOM_PROVIDERS
    if not all_enabled:
        return "Нет включённых провайдеров. Добавьте API ключи в .env"
    return f"Доступные провайдеры: {', '.join(all_enabled)}"


def get_completion_kwargs(model: str) -> dict:
    """Return completion kwargs based on model."""
    if model.startswith("ollama-cloud/"):
        actual_model = model.replace("ollama-cloud/", "openai/")
        return {
            "model": actual_model,
            "api_base": OLLAMA_CLOUD_BASE,
            "api_key": os.getenv("OLLAMA_API_KEY"),
        }
    return {"model": model}


def format_error(e: Exception, include_prefix: bool = True) -> str:
    """Format litellm exception into user-friendly message.

    Handles specific cases where litellm returns empty or
    uninformative error messages.

    Args:
        e: Exception to format.
        include_prefix: If True, adds "Ошибка: " prefix to message.

    Returns:
        Formatted error message.
    """
    error_type = type(e).__name__
    error_msg = str(e).strip()
    prefix = "Ошибка: " if include_prefix else ""

    # AuthenticationError с пустым или неинформативным сообщением
    if "AuthenticationError" in error_type or "AuthenticationError" in error_msg:
        if not error_msg or error_msg.endswith(":") or len(error_msg) < 30:
            return f"{prefix}Неверный API ключ или ключ не имеет доступа к модели"

    # Паттерны ошибок: (условие, сообщение)
    error_patterns = [
        (
            lambda t, m: "401" in m or "Unauthorized" in m,
            "Неверный API ключ. Проверьте переменные окружения.",
        ),
        (
            lambda t, m: "429" in m
            or "rate limit" in m.lower()
            or "RateLimitError" in t,
            "Превышен лимит запросов. Подождите и попробуйте снова.",
        ),
        (
            lambda t, m: "timeout" in m.lower() or "Timeout" in t,
            "Таймаут запроса. Попробуйте позже.",
        ),
        (
            lambda t, m: "404" in m or "NotFoundError" in t,
            "Модель не найдена. Проверьте название.",
        ),
        (
            lambda t, m: "APIConnectionError" in t or "Connection" in m,
            "Не удалось подключиться к API. Проверьте сеть.",
        ),
    ]

    for condition, message in error_patterns:
        if condition(error_type, error_msg):
            return f"{prefix}{message}"

    # Очистка сообщения от типичных префиксов litellm
    for litellm_prefix in ["litellm.", "AuthenticationError:", "APIError:"]:
        if error_msg.startswith(litellm_prefix):
            error_msg = error_msg[len(litellm_prefix) :].strip()

    # Обрезаем слишком длинные сообщения
    if len(error_msg) > 150:
        error_msg = error_msg[:150] + "..."

    if error_msg:
        return f"{prefix}{error_msg}"
    return f"{prefix}Неизвестная ошибка API"


# ===== Reasoning =====
THINKING_BUDGETS = {
    "low": 1024,
    "medium": 4096,
    "high": 16000,
}

KNOWN_REASONING_MODELS = {
    "sonnet": "thinking",
    "opus": "thinking",
    "deepseek-r1": "thinking",
    "deepseek-v3": "thinking",
    "kimi-k2-thinking": "thinking",
    "kimi-k2": "thinking",
    "minimax-m2": "thinking",
    "qwq": "thinking",
    "o1-": "reasoning_effort",
    "o3-": "reasoning_effort",
    "gemini-2.5": "thinking",
    "gemini-3": "thinking",
    "thinking": "thinking",
    "reasoner": "thinking",
}

REASONING_CACHE_FILE = CACHE_DIR / "reasoning_models.json"
_reasoning_cache: dict[str, Optional[str]] = {}


def _load_reasoning_cache() -> dict[str, Optional[str]]:
    """Load cache of auto-detected reasoning models."""
    try:
        if REASONING_CACHE_FILE.exists():
            with open(REASONING_CACHE_FILE, "r") as f:
                return json.load(f)
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def _save_reasoning_cache():
    """Save cache of auto-detected reasoning models."""
    try:
        CACHE_DIR.mkdir(exist_ok=True)
        with open(REASONING_CACHE_FILE, "w") as f:
            json.dump(_reasoning_cache, f, indent=2)
    except (OSError, PermissionError):
        pass


_reasoning_cache = _load_reasoning_cache()


def _get_reasoning_type_from_registry(model: str) -> Optional[str]:
    """Look up reasoning type in registry by model name patterns."""
    model_lower = model.lower()
    for pattern, reasoning_type in KNOWN_REASONING_MODELS.items():
        if pattern in model_lower:
            return reasoning_type
    return None


def _is_model_cached(model: str) -> bool:
    """Check if model is in cache (regardless of value)."""
    return model in _reasoning_cache


def _get_reasoning_type(model: str) -> Optional[str]:
    """Determine reasoning type for model."""
    if model in _reasoning_cache:
        return _reasoning_cache[model]

    from_registry = _get_reasoning_type_from_registry(model)
    if from_registry:
        return from_registry

    return None


def _cache_reasoning_type(model: str, reasoning_type: Optional[str]):
    """Save model's reasoning type to cache."""
    if model not in _reasoning_cache:
        _reasoning_cache[model] = reasoning_type
        _save_reasoning_cache()


def get_reasoning_kwargs(model: str, reasoning: Optional[str]) -> dict:
    """Convert reasoning level to model-specific parameters."""
    if not reasoning:
        return {}

    reasoning_type = _get_reasoning_type(model)
    budget = THINKING_BUDGETS.get(reasoning, 4096)

    if reasoning_type == "thinking":
        return {"thinking": {"type": "enabled", "budget_tokens": budget}}
    elif reasoning_type == "reasoning_effort":
        return {"reasoning_effort": reasoning}
    elif _is_model_cached(model):
        return {}

    provider = get_provider(model)
    if provider in ("openai", "xai"):
        return {
            "reasoning_effort": reasoning,
            "_auto_detect": True,
            "_auto_type": "reasoning_effort",
        }
    return {
        "thinking": {"type": "enabled", "budget_tokens": budget},
        "_auto_detect": True,
        "_auto_type": "thinking",
    }


def extract_reasoning(response) -> Optional[str]:
    """Extract reasoning_content from response (DeepSeek-R1, xAI, etc.)."""
    message = response.choices[0].message
    return getattr(message, "reasoning_content", None)


async def completion_with_auto_detect(
    model: str, messages: list, reasoning: Optional[str], **extra_kwargs
) -> tuple[any, Optional[str]]:
    """
    Perform completion with auto-detection of reasoning support.
    Returns (response, reasoning_content).
    """
    kwargs = get_completion_kwargs(model)
    kwargs["metadata"] = {"prompt_version": PROMPT_VERSION}
    kwargs.update(extra_kwargs)

    reasoning_kwargs = get_reasoning_kwargs(model, reasoning)
    auto_detect = reasoning_kwargs.pop("_auto_detect", False)
    auto_type = reasoning_kwargs.pop("_auto_type", "thinking")

    if reasoning_kwargs:
        kwargs.update(reasoning_kwargs)

    try:
        response = await acompletion(messages=messages, caching=CACHE_ACTIVE, **kwargs)
        reasoning_content = extract_reasoning(response)

        if auto_detect and reasoning:
            _cache_reasoning_type(model, auto_type)

        return response, reasoning_content

    except Exception as e:  # LiteLLM can raise various provider-specific exceptions
        error_str = str(e).lower()
        is_param_error = any(
            x in error_str
            for x in [
                "thinking",
                "budget_tokens",
                "reasoning_effort",
                "unsupported",
                "invalid parameter",
                "unknown parameter",
            ]
        )

        if auto_detect and is_param_error and reasoning_kwargs:
            for key in reasoning_kwargs:
                kwargs.pop(key, None)

            response = await acompletion(
                messages=messages, caching=CACHE_ACTIVE, **kwargs
            )
            _cache_reasoning_type(model, None)
            return response, None

        raise


# ===== Pydantic Models =====
class ConsultExpertInput(BaseModel):
    """Input parameters for expert consultation."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    query: str = Field(
        ...,
        description="Вопрос к эксперту",
        min_length=1,
        max_length=10000,
    )
    context: Optional[str] = Field(
        default="", description="Контекст задачи или код для анализа", max_length=100000
    )
    model: str = Field(
        default=DEFAULT_MODEL,
        description="Модель LLM",
    )
    role: str = Field(
        default=DEFAULT_ROLE,
        description="Роль/персона эксперта (system prompt)",
        max_length=2000,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Формат ответа: markdown или json",
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Уровень reasoning: low, medium, high",
        pattern="^(low|medium|high)$",
    )


class CompareExpertsInput(BaseModel):
    """Input parameters for comparing expert opinions."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    query: str = Field(
        ..., description="Вопрос к экспертам", min_length=1, max_length=10000
    )
    context: Optional[str] = Field(
        default="", description="Контекст задачи или код для анализа", max_length=100000
    )
    models: str = Field(
        default=DEFAULT_MODELS_COMPARE,
        description="Модели через запятую",
    )
    role: str = Field(
        default=DEFAULT_ROLE,
        description="Роль/персона экспертов (system prompt)",
        max_length=2000,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN, description="Формат ответа: markdown или json"
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Уровень reasoning: low, medium, high",
        pattern="^(low|medium|high)$",
    )


# ===== Core Functions =====
def _build_messages(query: str, context: str | None, role: str) -> list[dict]:
    """Build message list for LLM request.

    Args:
        query: User query
        context: Optional context
        role: System role

    Returns:
        List of message dicts for litellm
    """
    user_content = f"{query}\n\nКонтекст:\n{context}" if context else query
    return [
        {"role": "system", "content": role},
        {"role": "user", "content": user_content},
    ]


async def consult_expert(params: ConsultExpertInput) -> str:
    """Consult with expert LLM model."""
    if not params.model:
        return f"Ошибка: Модель не указана. {get_enabled_models_hint()}"

    error = check_model_allowed(params.model)
    if error:
        return f"Ошибка: {error}"

    messages = _build_messages(params.query, params.context, params.role)

    try:
        response, reasoning_content = await completion_with_auto_detect(
            model=params.model, messages=messages, reasoning=params.reasoning
        )
        answer = response.choices[0].message.content

        if params.response_format == ResponseFormat.JSON:
            result = {
                "model": params.model,
                "query": params.query,
                "answer": answer,
                "cached": getattr(response, "_hidden_params", {}).get(
                    "cache_hit", False
                ),
            }
            if reasoning_content:
                result["reasoning"] = reasoning_content
            return json.dumps(result, ensure_ascii=False, indent=2)

        output = f"## Ответ от {params.model}\n\n"
        if reasoning_content:
            output += f"<details>\n<summary>Reasoning</summary>\n\n{reasoning_content}\n\n</details>\n\n"
        output += answer
        return output
    except Exception as e:  # LiteLLM can raise various provider-specific exceptions
        return format_error(e)


async def compare_experts(params: CompareExpertsInput) -> str:
    """Get opinions from multiple LLM models in parallel."""
    if not params.models:
        return f"Ошибка: Модели не указаны. {get_enabled_models_hint()}"

    model_list = [m.strip() for m in params.models.split(",") if m.strip()]

    if not model_list:
        return f"Ошибка: Список моделей пуст. {get_enabled_models_hint()}"

    messages = _build_messages(params.query, params.context, params.role)

    async def ask_model(model: str) -> tuple[str, str, Optional[str], bool]:
        error = check_model_allowed(model)
        if error:
            return model, f"Ошибка: {error}", None, True

        try:
            response, reasoning_content = await completion_with_auto_detect(
                model=model, messages=messages, reasoning=params.reasoning
            )
            return model, response.choices[0].message.content, reasoning_content, False
        except Exception as e:  # LiteLLM can raise various provider-specific exceptions
            return model, format_error(e), None, True

    results = await asyncio.gather(*[ask_model(m) for m in model_list])

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(
            {
                "query": params.query,
                "experts": [
                    {
                        "model": model,
                        "answer": answer,
                        "reasoning": reasoning,
                        "error": is_error,
                    }
                    for model, answer, reasoning, is_error in results
                ],
            },
            ensure_ascii=False,
            indent=2,
        )

    output = [f"# Сравнение мнений экспертов\n\n**Вопрос:** {params.query}\n"]
    for model, answer, reasoning, is_error in results:
        status = "[ERROR]" if is_error else "[OK]"
        section = f"---\n\n## {status} {model}\n\n"
        if reasoning:
            section += f"<details>\n<summary>Reasoning</summary>\n\n{reasoning}\n\n</details>\n\n"
        section += f"{answer}\n"
        output.append(section)
    return "\n".join(output)
