#!/usr/bin/env python3
"""CLI интерфейс для advisor-cli."""

import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")
warnings.filterwarnings("ignore", message="coroutine .* was never awaited")

import asyncio
import json
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Optional

import typer

from .core import (
    CUSTOM_PROVIDERS,
    DEFAULT_MODEL,
    DEFAULT_MODELS_COMPARE,
    ENABLED_PROVIDERS,
    ConsultExpertInput,
    CompareExpertsInput,
    ResponseFormat,
    consult_expert,
    compare_experts,
    init_cache,
)
from .file_utils import read_context_file

app = typer.Typer(
    name="advisor",
    help="CLI для получения второго мнения от альтернативных LLM",
    no_args_is_help=True,
)

# Группа команд config
config_app = typer.Typer(help="Управление конфигурацией")
app.add_typer(config_app, name="config")

# Группа команд mcp
mcp_app = typer.Typer(help="Управление MCP интеграцией")
app.add_typer(mcp_app, name="mcp")

# ===== Async Tasks =====
TASK_DIR = Path(tempfile.gettempdir()) / "advisor-tasks"
TASK_TTL = 3600  # 1 час


def create_async_task(task_id: str, result: dict):
    """Сохранить результат во временный файл."""
    TASK_DIR.mkdir(exist_ok=True)
    task_file = TASK_DIR / f"{task_id}.json"
    task_file.write_text(
        json.dumps(
            {
                "result": result,
                "created": time.time(),
            },
            ensure_ascii=False,
        )
    )


def get_async_result(task_id: str, keep: bool = False) -> dict | None:
    """Получить результат, удалить файл если не keep."""
    task_file = TASK_DIR / f"{task_id}.json"
    if not task_file.exists():
        return None
    data = json.loads(task_file.read_text())
    if not keep:
        task_file.unlink()
    return data["result"]


def cleanup_old_tasks():
    """Удалить задачи старше TTL при запуске."""
    if not TASK_DIR.exists():
        return
    now = time.time()
    for f in TASK_DIR.glob("*.json"):
        try:
            if now - f.stat().st_mtime > TASK_TTL:
                f.unlink()
        except Exception:
            pass


# ===== Output =====
def print_output(text: str, error: bool = False):
    """Простой вывод в stdout/stderr."""
    if error:
        sys.stderr.write(text + "\n")
    else:
        sys.stdout.write(text + "\n")


def read_stdin() -> str | None:
    """Читает stdin если есть данные."""
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return None


# ===== Commands =====
@app.command()
def ask(
    query: str = typer.Argument(..., help="Вопрос к модели"),
    context: Optional[str] = typer.Option(
        None, "--context", "-c", help="Контекст inline"
    ),
    file: Optional[Path] = typer.Option(None, "--file", "-f", help="Файл с контекстом"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Модель LLM"),
    format: Optional[str] = typer.Option(
        None, "--format", help="Формат: markdown|json"
    ),
    reasoning: Optional[str] = typer.Option(
        None, "--reasoning", "-r", help="Уровень reasoning: low|medium|high"
    ),
):
    """Получить ответ от LLM."""
    cleanup_old_tasks()
    init_cache()

    # Собираем контекст
    final_context = context or ""

    # Из stdin
    stdin_data = read_stdin()
    if stdin_data:
        final_context = (
            stdin_data if not final_context else f"{final_context}\n\n{stdin_data}"
        )

    # Из файла
    if file:
        try:
            file_content = read_context_file(file)
            final_context = (
                file_content
                if not final_context
                else f"{final_context}\n\n{file_content}"
            )
        except (ValueError, FileNotFoundError) as e:
            print_output(str(e), error=True)
            raise typer.Exit(1)

    # Формат ответа
    response_format = ResponseFormat.MARKDOWN
    if format:
        if format.lower() == "json":
            response_format = ResponseFormat.JSON
        elif format.lower() != "markdown":
            print_output(
                f"Неизвестный формат: {format}. Используйте markdown или json",
                error=True,
            )
            raise typer.Exit(1)

    params = ConsultExpertInput(
        query=query,
        context=final_context,
        model=model or DEFAULT_MODEL,
        response_format=response_format,
        reasoning=reasoning,
    )

    result = asyncio.run(consult_expert(params))
    print_output(result)


@app.command()
def compare(
    query: str = typer.Argument(..., help="Вопрос к моделям"),
    context: Optional[str] = typer.Option(
        None, "--context", "-c", help="Контекст inline"
    ),
    file: Optional[Path] = typer.Option(None, "--file", "-f", help="Файл с контекстом"),
    models: Optional[str] = typer.Option(
        None, "--models", "-m", help="Модели через запятую"
    ),
    format: Optional[str] = typer.Option(
        None, "--format", help="Формат: markdown|json"
    ),
    reasoning: Optional[str] = typer.Option(
        None, "--reasoning", "-r", help="Уровень reasoning: low|medium|high"
    ),
    background: bool = typer.Option(False, "--async", help="Запустить в фоне"),
):
    """Получить ответы от нескольких LLM (консилиум)."""
    cleanup_old_tasks()
    init_cache()

    # Собираем контекст
    final_context = context or ""

    # Из stdin
    stdin_data = read_stdin()
    if stdin_data:
        final_context = (
            stdin_data if not final_context else f"{final_context}\n\n{stdin_data}"
        )

    # Из файла
    if file:
        try:
            file_content = read_context_file(file)
            final_context = (
                file_content
                if not final_context
                else f"{final_context}\n\n{file_content}"
            )
        except (ValueError, FileNotFoundError) as e:
            print_output(str(e), error=True)
            raise typer.Exit(1)

    # Формат ответа
    response_format = ResponseFormat.MARKDOWN
    if format:
        if format.lower() == "json":
            response_format = ResponseFormat.JSON
        elif format.lower() != "markdown":
            print_output(
                f"Неизвестный формат: {format}. Используйте markdown или json",
                error=True,
            )
            raise typer.Exit(1)

    params = CompareExpertsInput(
        query=query,
        context=final_context,
        models=models or DEFAULT_MODELS_COMPARE,
        response_format=response_format,
        reasoning=reasoning,
    )

    if background:
        task_id = str(uuid.uuid4())[:8]
        # Запускаем в фоне через subprocess
        import subprocess

        cmd = [
            sys.executable,
            "-c",
            f"""
import asyncio
import json
from advisor_cli.core import CompareExpertsInput, ResponseFormat, compare_experts, init_cache

init_cache()
params = CompareExpertsInput(
    query={repr(query)},
    context={repr(final_context)},
    models={repr(models or DEFAULT_MODELS_COMPARE)},
    response_format=ResponseFormat.{response_format.name},
    reasoning={repr(reasoning)},
)
result = asyncio.run(compare_experts(params))

from pathlib import Path
import time
TASK_DIR = Path({repr(str(TASK_DIR))})
TASK_DIR.mkdir(exist_ok=True)
task_file = TASK_DIR / "{task_id}.json"
task_file.write_text(json.dumps({{"result": result, "created": time.time()}}, ensure_ascii=False))
""",
        ]
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        print_output(f"Task ID: {task_id}")
        print_output(f"Получить результат: advisor result {task_id}")
    else:
        result = asyncio.run(compare_experts(params))
        print_output(result)


@app.command()
def result(
    task_id: str = typer.Argument(..., help="ID задачи"),
    keep: bool = typer.Option(False, "--keep", help="Не удалять после прочтения"),
):
    """Получить результат фоновой задачи."""
    res = get_async_result(task_id, keep=keep)
    if res is None:
        print_output(f"Задача не найдена: {task_id}", error=True)
        raise typer.Exit(1)
    print_output(res)


@app.command()
def run():
    """Запустить MCP сервер (требует установки с [mcp])."""
    try:
        from .server import main as run_server

        run_server()
    except ImportError:
        print_output(
            "MCP не установлен. Установите: pip install advisor-cli[mcp]", error=True
        )
        raise typer.Exit(1)


@app.command()
def setup(
    yes: bool = typer.Option(
        False, "-y", help="Неинтерактивный режим (использовать env vars)"
    ),
    providers: Optional[str] = typer.Option(
        None, "-p", "--providers", help="Провайдеры через запятую"
    ),
    model: Optional[str] = typer.Option(
        None, "-m", "--model", help="Модель по умолчанию"
    ),
):
    """Интерактивная настройка конфигурации (требует установки с [wizard])."""
    try:
        from .setup_wizard import run_setup

        provider_list = None
        if providers:
            provider_list = [p.strip() for p in providers.split(",")]

        run_setup(
            non_interactive=yes,
            providers=provider_list,
            model=model,
        )
    except ImportError:
        print_output(
            "Wizard не установлен. Установите: pip install advisor-cli[wizard]",
            error=True,
        )
        raise typer.Exit(1)


@app.command()
def status():
    """Показать текущий статус конфигурации."""
    init_cache()
    from .core import CACHE_ACTIVE

    print_output("\nAdvisor CLI - Статус\n")

    if ENABLED_PROVIDERS or CUSTOM_PROVIDERS:
        print_output("Включённые провайдеры:")
        for provider in ENABLED_PROVIDERS:
            print_output(f"  - {provider}")
        for provider in CUSTOM_PROVIDERS:
            print_output(f"  - {provider} (custom)")
    else:
        print_output("Нет включённых провайдеров.")
        print_output("Запустите 'advisor setup' для настройки.")

    print_output(f"\nКэширование: {'включено' if CACHE_ACTIVE else 'выключено'}\n")


@app.command("models")
def models_cmd():
    """Показать настроенные модели и текущую конфигурацию."""
    print_output("\nТекущая конфигурация моделей\n")
    print_output(f"Single (ask): {DEFAULT_MODEL}")
    print_output(f"Compare (compare): {DEFAULT_MODELS_COMPARE}")

    print_output("\nДоступные модели по провайдерам:")

    try:
        from .setup_wizard import PROVIDER_INFO

        for provider in ENABLED_PROVIDERS:
            info = PROVIDER_INFO.get(provider, {})
            name = info.get("name", provider)
            models_list = info.get("models", [])
            print_output(f"\n  {name}:")
            for model in models_list:
                print_output(f"    - {model}")
    except ImportError:
        for provider in ENABLED_PROVIDERS:
            print_output(f"\n  {provider}:")
            print_output(f"    - {provider}/*")

    if CUSTOM_PROVIDERS:
        print_output("\n  Custom провайдеры:")
        for provider in CUSTOM_PROVIDERS:
            print_output(f"    - {provider}/*")

    print_output("")


@config_app.command("single")
def config_single(
    model: str = typer.Argument(..., help="Модель (например: gemini/gemini-2.5-pro)"),
    check: bool = typer.Option(
        True, "--check/--no-check", help="Проверить доступность модели"
    ),
):
    """Установить модель для ask (одиночный запрос)."""
    if "/" not in model:
        print_output("Ошибка: Формат модели: provider/model", error=True)
        raise typer.Exit(1)

    if check:
        print_output("Проверка модели...")
        try:
            from .setup_wizard import test_model

            success, msg = asyncio.run(test_model(model))
            if not success:
                print_output(f"Ошибка: {msg}", error=True)
                raise typer.Exit(1)
            print_output("OK - Модель доступна")
        except ImportError:
            print_output("Wizard не установлен, пропускаем проверку")

    try:
        from .setup_wizard import load_existing_env, save_env

        env = load_existing_env()
        env["ADVISOR_DEFAULT_MODEL"] = model
        save_env(env)
        print_output(f"Модель по умолчанию: {model}")
    except ImportError:
        print_output(
            "Wizard не установлен. Установите вручную ADVISOR_DEFAULT_MODEL в .env",
            error=True,
        )
        raise typer.Exit(1)


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
    """Установить модели для compare (консилиум)."""
    model_list = [m.strip() for m in models_str.split(",") if m.strip()]

    if not model_list:
        print_output("Ошибка: Список моделей пуст", error=True)
        raise typer.Exit(1)

    if check:
        try:
            from .setup_wizard import test_model

            all_ok = True
            for model in model_list:
                if "/" not in model:
                    print_output(f"  {model}: X Неверный формат", error=True)
                    all_ok = False
                    continue

                print_output(f"Проверка {model}...")
                success, msg = asyncio.run(test_model(model))

                if success:
                    print_output(f"  {model}: OK")
                else:
                    print_output(f"  {model}: X {msg}", error=True)
                    all_ok = False

            if not all_ok:
                print_output("\nНекоторые модели недоступны")
        except ImportError:
            print_output("Wizard не установлен, пропускаем проверку")

    try:
        from .setup_wizard import load_existing_env, save_env

        env = load_existing_env()
        env["ADVISOR_DEFAULT_MODELS_COMPARE"] = ",".join(model_list)
        save_env(env)
        print_output(f"\nМодели для сравнения: {', '.join(model_list)}")
    except ImportError:
        print_output(
            "Wizard не установлен. Установите вручную ADVISOR_DEFAULT_MODELS_COMPARE в .env",
            error=True,
        )
        raise typer.Exit(1)


@config_app.command("format")
def config_format(
    fmt: str = typer.Argument(..., help="Формат по умолчанию: markdown|json"),
):
    """Установить формат вывода по умолчанию."""
    if fmt.lower() not in ("markdown", "json"):
        print_output("Ошибка: Формат должен быть markdown или json", error=True)
        raise typer.Exit(1)

    try:
        from .setup_wizard import load_existing_env, save_env

        env = load_existing_env()
        env["ADVISOR_OUTPUT_FORMAT"] = fmt.lower()
        save_env(env)
        print_output(f"Формат по умолчанию: {fmt.lower()}")
    except ImportError:
        print_output(
            "Wizard не установлен. Установите вручную ADVISOR_OUTPUT_FORMAT в .env",
            error=True,
        )
        raise typer.Exit(1)


@mcp_app.command("install")
def mcp_install(
    scope: Optional[str] = typer.Option(
        None, "--scope", "-s", help="Scope: project или user"
    ),
    target: str = typer.Option(
        "all", "--target", "-t", help="Target: claude-code, desktop или all"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Перезаписать без вопросов"
    ),
    yes: bool = typer.Option(False, "-y", help="Неинтерактивный режим"),
):
    """Установить MCP интеграцию для Claude."""
    from .mcp_manager import (
        ConflictType,
        Scope,
        Target,
        check_conflicts,
        has_project_mcp_config,
        install_to_claude_code,
        install_to_desktop,
    )

    # Check if providers configured
    try:
        from .setup_wizard import load_existing_env

        env = load_existing_env()
    except ImportError:
        env = {}

    has_providers = any(
        env.get(key)
        for key in [
            "GEMINI_API_KEY",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "DEEPSEEK_API_KEY",
            "GROQ_API_KEY",
            "OPENROUTER_API_KEY",
        ]
    )

    if not has_providers:
        if yes:
            print_output(
                "Ошибка: Нет настроенных провайдеров. Установите API ключи.", error=True
            )
            raise typer.Exit(1)
        else:
            print_output("Нет настроенных провайдеров.")
            try:
                import questionary

                run_setup_q = questionary.confirm(
                    "Запустить настройку?", default=True
                ).ask()
                if run_setup_q:
                    from .setup_wizard import run_setup

                    run_setup()
                else:
                    raise typer.Exit(1)
            except ImportError:
                print_output("Запустите: advisor setup", error=True)
                raise typer.Exit(1)

    # Determine scope
    scope_enum: Scope
    if scope:
        scope_enum = Scope.PROJECT if scope == "project" else Scope.USER
    elif has_project_mcp_config():
        scope_enum = Scope.PROJECT
        if not yes:
            print_output("Обнаружен .mcp.json в текущем проекте.")
    elif yes:
        scope_enum = Scope.USER
    else:
        try:
            import questionary

            choice = questionary.select(
                "Куда установить advisor?",
                choices=[
                    questionary.Choice("В проект (.mcp.json)", value="project"),
                    questionary.Choice(
                        "Глобально (Claude Code + Claude Desktop)", value="user"
                    ),
                ],
            ).ask()
            scope_enum = Scope.PROJECT if choice == "project" else Scope.USER
        except ImportError:
            scope_enum = Scope.USER

    # Parse target
    target_enum = Target.ALL
    if target == "claude-code":
        target_enum = Target.CLAUDE_CODE
    elif target == "desktop":
        target_enum = Target.DESKTOP

    # Check conflicts
    conflicts = check_conflicts(scope_enum, target_enum)

    for conflict in conflicts:
        if conflict.type == ConflictType.OVERRIDE:
            print_output(f"⚠ {conflict.location}: {conflict.message}")
        elif conflict.type == ConflictType.OUTDATED:
            print_output(f"⚠ {conflict.location}: {conflict.message}")
            if not force and not yes:
                try:
                    import questionary

                    update = questionary.confirm("Обновить?", default=True).ask()
                    if not update:
                        continue
                except ImportError:
                    pass
        elif conflict.type == ConflictType.DUPLICATE:
            if not force:
                print_output(f"✓ {conflict.location}: {conflict.message}")
                continue
        elif conflict.type == ConflictType.NAME_COLLISION:
            print_output(f"✗ {conflict.location}: {conflict.message}", error=True)
            if not force:
                raise typer.Exit(1)

    # Install
    installed = []

    if target_enum in (Target.ALL, Target.CLAUDE_CODE):
        if install_to_claude_code(scope_enum):
            loc = ".mcp.json" if scope_enum == Scope.PROJECT else "~/.claude.json"
            installed.append(loc)

    if target_enum in (Target.ALL, Target.DESKTOP):
        if install_to_desktop():
            installed.append("Claude Desktop")

    if installed:
        for loc in installed:
            print_output(f"✓ Установлено в {loc}")
        print_output("\nПерезапустите Claude для применения изменений.")
    else:
        print_output("Ничего не установлено.", error=True)


@mcp_app.command("uninstall")
def mcp_uninstall(
    scope: Optional[str] = typer.Option(
        None, "--scope", "-s", help="Scope: project или user"
    ),
    all_scopes: bool = typer.Option(False, "--all", "-a", help="Удалить отовсюду"),
    yes: bool = typer.Option(False, "-y", help="Неинтерактивный режим"),
):
    """Удалить MCP интеграцию из Claude."""
    from .mcp_manager import (
        Scope,
        get_installation_status,
        uninstall_from_claude_code,
        uninstall_from_desktop,
    )

    removed = []

    if all_scopes:
        if uninstall_from_claude_code(Scope.PROJECT):
            removed.append(".mcp.json")
        if uninstall_from_claude_code(Scope.USER):
            removed.append("~/.claude.json")
        if uninstall_from_desktop():
            removed.append("Claude Desktop")
    elif scope:
        scope_enum = Scope.PROJECT if scope == "project" else Scope.USER
        if uninstall_from_claude_code(scope_enum):
            loc = ".mcp.json" if scope_enum == Scope.PROJECT else "~/.claude.json"
            removed.append(loc)
    else:
        # Interactive mode
        status = get_installation_status()
        locations: list[tuple[str, Scope | None]] = []

        if status.get("claude_code_project", {}).get("installed"):
            locations.append((".mcp.json", Scope.PROJECT))
        if status.get("claude_code_user", {}).get("installed"):
            locations.append(("~/.claude.json", Scope.USER))
        if status.get("claude_desktop", {}).get("installed"):
            locations.append(("Claude Desktop", None))

        if not locations:
            print_output("advisor_mcp не установлен нигде.")
            return

        if yes:
            # Remove from all found locations
            for loc, scope_val in locations:
                if scope_val:
                    if uninstall_from_claude_code(scope_val):
                        removed.append(loc)
                else:
                    if uninstall_from_desktop():
                        removed.append(loc)
        else:
            try:
                import questionary

                choices = [
                    questionary.Choice(loc, value=(loc, scope_val))
                    for loc, scope_val in locations
                ]
                selected = questionary.checkbox(
                    "Откуда удалить advisor_mcp?",
                    choices=choices,
                ).ask()

                for loc, scope_val in selected or []:
                    if scope_val:
                        if uninstall_from_claude_code(scope_val):
                            removed.append(loc)
                    else:
                        if uninstall_from_desktop():
                            removed.append(loc)
            except ImportError:
                print_output("Укажите --scope или --all", error=True)
                raise typer.Exit(1)

    if removed:
        for loc in removed:
            print_output(f"✓ Удалено из {loc}")
        print_output("\nПерезапустите Claude для применения изменений.")
    else:
        print_output("Ничего не удалено.")


@mcp_app.command("status")
def mcp_status():
    """Показать статус MCP интеграции."""
    from .mcp_manager import get_installation_status

    status = get_installation_status()

    print_output("\nMCP Integration Status\n")

    labels = {
        "claude_code_user": "Claude Code (user)",
        "claude_code_project": "Claude Code (project)",
        "claude_desktop": "Claude Desktop",
    }

    any_installed = False

    for key, label in labels.items():
        info = status.get(key, {})
        if info.get("installed"):
            any_installed = True
            if info.get("outdated"):
                print_output(f"  {label}: ⚠ установлен (устаревшая версия)")
            else:
                print_output(f"  {label}: ✓ установлен")
        else:
            print_output(f"  {label}: ✗ не установлен")

    if not any_installed:
        print_output("\nЗапустите: advisor mcp install")
    elif any(s.get("outdated") for s in status.values()):
        print_output("\nДля обновления: advisor mcp install --force")

    print_output("")


if __name__ == "__main__":
    app()
