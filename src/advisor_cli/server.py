#!/usr/bin/env python3
"""
MCP Server для получения "второго мнения" от альтернативных LLM.

Сервер предоставляет инструменты для консультации с различными LLM моделями.
Доступны только те провайдеры, для которых указаны API ключи в .env.

Требует установки: pip install advisor-cli[mcp]
"""

import json
from typing import Optional

from mcp.server.fastmcp import FastMCP

from .core import (
    ConsultExpertInput,
    CompareExpertsInput,
    ResponseFormat,
    check_model_allowed,
    completion_with_auto_detect,
    format_error,
    get_enabled_models_hint,
    init_cache,
)

# ===== Инициализация =====
init_cache()

# ===== Инициализация сервера =====
mcp = FastMCP("advisor_mcp")


# ===== Tools =====
@mcp.tool(
    name="advisor_consult_expert",
    annotations={
        "title": "Консультация с экспертом",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def advisor_consult_expert(params: ConsultExpertInput) -> str:
    """
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
    """
    if not params.model:
        return f"Ошибка: Модель не указана. {get_enabled_models_hint()}"

    error = check_model_allowed(params.model)
    if error:
        return f"Ошибка: {error}"

    messages = [
        {"role": "system", "content": params.role},
        {
            "role": "user",
            "content": f"{params.query}\n\nКонтекст:\n{params.context}"
            if params.context
            else params.query,
        },
    ]

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
    except Exception as e:
        return format_error(e)


@mcp.tool(
    name="advisor_compare_experts",
    annotations={
        "title": "Сравнение мнений экспертов",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def advisor_compare_experts(params: CompareExpertsInput) -> str:
    """
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
    """
    import asyncio

    if not params.models:
        return f"Ошибка: Модели не указаны. {get_enabled_models_hint()}"

    model_list = [m.strip() for m in params.models.split(",") if m.strip()]

    if not model_list:
        return f"Ошибка: Список моделей пуст. {get_enabled_models_hint()}"

    messages = [
        {"role": "system", "content": params.role},
        {
            "role": "user",
            "content": f"{params.query}\n\nКонтекст:\n{params.context}"
            if params.context
            else params.query,
        },
    ]

    async def ask_model(model: str) -> tuple[str, str, Optional[str], bool]:
        error = check_model_allowed(model)
        if error:
            return model, f"Ошибка: {error}", None, True

        try:
            response, reasoning_content = await completion_with_auto_detect(
                model=model, messages=messages, reasoning=params.reasoning
            )
            return model, response.choices[0].message.content, reasoning_content, False
        except Exception as e:
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


def main():
    """Точка входа для запуска MCP сервера."""
    mcp.run()


if __name__ == "__main__":
    main()
