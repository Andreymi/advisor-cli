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
        kwargs = _get_completion_kwargs(params.model)
        kwargs["metadata"] = {"prompt_version": PROMPT_VERSION}
        response = await acompletion(messages=messages, caching=CACHE_ACTIVE, **kwargs)
        answer = response.choices[0].message.content

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({
                "model": params.model,
                "query": params.query,
                "answer": answer,
                "cached": getattr(response, '_hidden_params', {}).get('cache_hit', False)
            }, ensure_ascii=False, indent=2)

        return f"## Ответ от {params.model}\n\n{answer}"
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

    async def ask_model(model: str) -> tuple[str, str, bool]:
        # Проверка что провайдер включён
        error = _check_model_allowed(model)
        if error:
            return model, f"Ошибка: {error}", True

        try:
            kwargs = _get_completion_kwargs(model)
            kwargs["metadata"] = {"prompt_version": PROMPT_VERSION}
            response = await acompletion(messages=messages, caching=CACHE_ACTIVE, **kwargs)
            return model, response.choices[0].message.content, False
        except Exception as e:
            return model, _format_error(e), True

    results = await asyncio.gather(*[ask_model(m) for m in model_list])

    if params.response_format == ResponseFormat.JSON:
        return json.dumps({
            "query": params.query,
            "experts": [
                {"model": model, "answer": answer, "error": is_error}
                for model, answer, is_error in results
            ]
        }, ensure_ascii=False, indent=2)

    output = [f"# Сравнение мнений экспертов\n\n**Вопрос:** {params.query}\n"]
    for model, answer, is_error in results:
        status = "❌" if is_error else "✅"
        output.append(f"---\n\n## {status} {model}\n\n{answer}\n")
    return "\n".join(output)


def main():
    '''Точка входа для запуска MCP сервера.'''
    mcp.run()


if __name__ == "__main__":
    main()
