#!/usr/bin/env python3
"""CLI интерфейс для mcp-advisor."""

import asyncio

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .server import main as run_server
from .setup_wizard import (
    PROVIDER_INFO,
    load_existing_env,
    run_setup,
    save_env,
    test_model,
)

console = Console()
app = typer.Typer(
    name="mcp-advisor",
    help="MCP Server для получения второго мнения от альтернативных LLM",
    no_args_is_help=True,
)

# Группа команд config
config_app = typer.Typer(help="Управление конфигурацией")
app.add_typer(config_app, name="config")


@app.command()
def run():
    """Запустить MCP сервер."""
    run_server()


@app.command()
def setup():
    """Интерактивная настройка конфигурации."""
    run_setup()


@app.command()
def status():
    """Показать текущий статус конфигурации."""
    from .server import CACHE_ACTIVE, CUSTOM_PROVIDERS, ENABLED_PROVIDERS

    console.print("\n[bold cyan]MCP Advisor — Статус[/bold cyan]\n")

    if ENABLED_PROVIDERS or CUSTOM_PROVIDERS:
        console.print("[green]Включённые провайдеры:[/green]")
        for provider in ENABLED_PROVIDERS:
            console.print(f"  • {provider}")
        for provider in CUSTOM_PROVIDERS:
            console.print(f"  • {provider} [dim](custom)[/dim]")
    else:
        console.print("[yellow]Нет включённых провайдеров.[/yellow]")
        console.print("Запустите [bold]mcp-advisor setup[/bold] для настройки.")

    console.print(
        f"\n[dim]Кэширование: {'включено' if CACHE_ACTIVE else 'выключено'}[/dim]\n"
    )


@app.command()
def models():
    """Показать настроенные модели и текущую конфигурацию."""
    from .server import (
        CUSTOM_PROVIDERS,
        DEFAULT_MODEL,
        DEFAULT_MODELS_COMPARE,
        ENABLED_PROVIDERS,
    )

    console.print("\n[bold cyan]Текущая конфигурация моделей[/bold cyan]\n")
    console.print(f"[green]Single (advisor_consult_expert):[/green] {DEFAULT_MODEL}")
    console.print(
        f"[green]Compare (advisor_compare_experts):[/green] {DEFAULT_MODELS_COMPARE}"
    )

    console.print("\n[bold]Доступные модели по провайдерам:[/bold]")
    for provider in ENABLED_PROVIDERS:
        info = PROVIDER_INFO.get(provider, {})
        name = info.get("name", provider)
        models_list = info.get("models", [])
        console.print(f"\n  [cyan]{name}:[/cyan]")
        for model in models_list:
            console.print(f"    • {model}")

    if CUSTOM_PROVIDERS:
        console.print("\n  [cyan]Custom провайдеры:[/cyan]")
        for provider in CUSTOM_PROVIDERS:
            console.print(f"    • {provider}/*")

    console.print()


@config_app.command("single")
def config_single(
    model: str = typer.Argument(..., help="Модель (например: gemini/gemini-2.5-pro)"),
    check: bool = typer.Option(
        True, "--check/--no-check", help="Проверить доступность модели"
    ),
):
    """Установить модель для advisor_consult_expert (одиночный запрос)."""
    if "/" not in model:
        console.print("[red]Ошибка: Формат модели: provider/model[/red]")
        raise typer.Exit(1)

    if check:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task(description="Проверка модели...", total=None)
            success, msg = asyncio.run(test_model(model))

        if not success:
            console.print(f"[red]Ошибка: {msg}[/red]")
            raise typer.Exit(1)
        console.print("[green]✓ Модель доступна[/green]")

    env = load_existing_env()
    env["ADVISOR_DEFAULT_MODEL"] = model
    save_env(env)
    console.print(f"[green]Модель по умолчанию: {model}[/green]")


@config_app.command("compare")
def config_compare(
    models_str: str = typer.Argument(
        ...,
        help="Модели через запятую (например: gemini/gemini-2.0-flash,openai/gpt-4o)",
    ),
    check: bool = typer.Option(
        True, "--check/--no-check", help="Проверить доступность моделей"
    ),
):
    """Установить модели для advisor_compare_experts (консилиум)."""
    model_list = [m.strip() for m in models_str.split(",") if m.strip()]

    if not model_list:
        console.print("[red]Ошибка: Список моделей пуст[/red]")
        raise typer.Exit(1)

    if check:
        all_ok = True
        for model in model_list:
            if "/" not in model:
                console.print(f"  {model}: [red]✗ Неверный формат[/red]")
                all_ok = False
                continue

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                progress.add_task(description=f"Проверка {model}...", total=None)
                success, msg = asyncio.run(test_model(model))

            if success:
                console.print(f"  {model}: [green]✓[/green]")
            else:
                console.print(f"  {model}: [red]✗ {msg}[/red]")
                all_ok = False

        if not all_ok:
            console.print("\n[yellow]Некоторые модели недоступны[/yellow]")

    env = load_existing_env()
    env["ADVISOR_DEFAULT_MODELS_COMPARE"] = ",".join(model_list)
    save_env(env)
    console.print(f"\n[green]Модели для сравнения: {', '.join(model_list)}[/green]")


if __name__ == "__main__":
    app()
