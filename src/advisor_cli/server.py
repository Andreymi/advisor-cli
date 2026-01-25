#!/usr/bin/env python3
"""
MCP Server для получения "второго мнения" от альтернативных LLM.

Сервер предоставляет инструменты для консультации с различными LLM моделями.
Доступны только те провайдеры, для которых указаны API ключи в .env.

Требует установки: pip install advisor-cli[mcp]
"""

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .core import (
    CompareExpertsInput,
    ConsultExpertInput,
    compare_experts,
    consult_expert,
    init_cache,
)

# ===== Инициализация =====
init_cache()

# ===== Инициализация сервера =====
mcp = FastMCP("advisor_mcp")


# ===== Tools =====
@mcp.tool(
    name="advisor_consult_expert",
    annotations=ToolAnnotations(
        title="Консультация с экспертом",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
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
    return await consult_expert(params)


@mcp.tool(
    name="advisor_compare_experts",
    annotations=ToolAnnotations(
        title="Сравнение мнений экспертов",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
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
    return await compare_experts(params)


def main():
    """Точка входа для запуска MCP сервера."""
    mcp.run()


if __name__ == "__main__":
    main()
