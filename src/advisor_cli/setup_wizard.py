#!/usr/bin/env python3
"""Интерактивный wizard для настройки mcp-advisor."""

import os

import questionary
from questionary import Style
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from .config import PROVIDER_INFO, load_config, save_config
from .utils import run_async

console = Console()

# Кастомный стиль для questionary (минималистичный, без цветного фона)
WIZARD_STYLE = Style(
    [
        ("qmark", "fg:cyan bold"),
        ("question", "bold"),
        ("answer", "fg:cyan"),
        ("pointer", "fg:cyan bold"),
        ("highlighted", "fg:cyan bold noreverse"),
        ("selected", "fg:cyan noreverse"),
        ("separator", "fg:cyan"),
        ("instruction", "fg:gray"),
        ("checkbox-selected", "fg:cyan"),
    ]
)


def parse_litellm_error(e: Exception) -> str:
    """Парсит ошибки litellm в понятные сообщения.

    Deprecated: используйте core.format_error() напрямую.
    Эта функция сохранена для обратной совместимости.
    """
    from .core import format_error

    return format_error(e, include_prefix=False)


async def test_connection(provider: str, api_key: str) -> tuple[bool, str]:
    """Тестирует подключение к провайдеру."""
    from litellm import acompletion

    info = PROVIDER_INFO.get(provider, {})
    test_model = info.get("test_model")

    if not test_model:
        return False, "Неизвестный провайдер"

    # Устанавливаем переменную окружения для теста
    env_key = info["env_key"]
    os.environ[env_key] = api_key

    # Дополнительные переменные окружения
    if "extra_env" in info:
        for k, v in info["extra_env"].items():
            os.environ[k] = v

    try:
        kwargs = {"model": test_model, "max_tokens": 5}

        # Ollama Cloud требует особой настройки
        if provider == "ollama-cloud":
            kwargs["model"] = test_model.replace("ollama-cloud/", "openai/")
            kwargs["api_base"] = os.getenv(
                "OLLAMA_CLOUD_BASE_URL", "https://ollama.com/v1"
            )
            kwargs["api_key"] = api_key

        await acompletion(messages=[{"role": "user", "content": "Hi"}], **kwargs)
        return True, "OK"
    except Exception as e:  # LiteLLM can raise various provider-specific exceptions
        return False, parse_litellm_error(e)


async def test_model(model: str) -> tuple[bool, str]:
    """Тестирует доступность конкретной модели."""
    from litellm import acompletion

    if "/" not in model:
        return False, "Формат: provider/model"

    provider = model.split("/")[0]

    # Ollama Cloud требует особой настройки
    try:
        kwargs = {"model": model, "max_tokens": 5}

        if provider == "ollama-cloud":
            kwargs["model"] = model.replace("ollama-cloud/", "openai/")
            kwargs["api_base"] = os.getenv(
                "OLLAMA_CLOUD_BASE_URL", "https://ollama.com/v1"
            )
            kwargs["api_key"] = os.getenv("OLLAMA_API_KEY")

        await acompletion(messages=[{"role": "user", "content": "Hi"}], **kwargs)
        return True, "OK"
    except Exception as e:  # LiteLLM can raise various provider-specific exceptions
        return False, parse_litellm_error(e)


def get_custom_providers() -> list[str]:
    """Получает список custom провайдеров из .env."""
    env = load_config()
    custom = env.get("ADVISOR_CUSTOM_PROVIDERS", "")
    return [p.strip() for p in custom.split(",") if p.strip()]


def setup_from_env() -> bool:
    """Setup from environment variables (non-interactive mode)."""
    env_vars: dict[str, str] = {}
    enabled_providers = []

    # Check for API keys in environment
    for provider_id, info in PROVIDER_INFO.items():
        env_key = info["env_key"]
        value = os.environ.get(env_key)
        if value:
            env_vars[env_key] = value
            enabled_providers.append(provider_id)

    if not enabled_providers:
        return False

    # Set defaults
    first_provider = enabled_providers[0]
    default_model = PROVIDER_INFO[first_provider]["models"][0]
    env_vars["ADVISOR_DEFAULT_MODEL"] = default_model

    # Compare models: one from each provider
    compare_models = []
    for provider_id in enabled_providers[:3]:  # Max 3 for compare
        compare_models.append(PROVIDER_INFO[provider_id]["models"][0])
    env_vars["ADVISOR_DEFAULT_MODELS_COMPARE"] = ",".join(compare_models)

    # Default options
    env_vars["ADVISOR_CACHE_ENABLED"] = "true"
    env_vars["ADVISOR_CACHE_TTL"] = "3600"
    env_vars["ADVISOR_VERBOSE"] = "false"

    # Merge with existing
    existing = load_config()
    existing.update(env_vars)
    save_config(existing)

    return True


def input_custom_model(enabled_providers: list[str]) -> str | None:
    """Ввод и проверка произвольной модели."""
    console.print(
        "\n[dim]Примеры: gemini/gemini-2.5-pro, openai/gpt-4-turbo, groq/llama-3.3-70b[/dim]"
    )

    model = questionary.text(
        "Введите модель (provider/model):",
        style=WIZARD_STYLE,
        validate=lambda x: "/" in x or "Формат: provider/model",
    ).ask()

    if not model:
        return None

    # Проверка провайдера
    provider = model.split("/")[0]
    custom_providers = get_custom_providers()
    all_providers = enabled_providers + custom_providers

    if provider not in all_providers and provider not in PROVIDER_INFO:
        console.print(
            f"[yellow]Провайдер '{provider}' не настроен.[/yellow]\n"
            f"[dim]Настроенные: {', '.join(all_providers)}[/dim]"
        )
        proceed = questionary.confirm(
            "Продолжить?",
            default=False,
            style=WIZARD_STYLE,
        ).ask()
        if not proceed:
            return None

    # Тест модели
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task(description="Проверка модели...", total=None)
        success, msg = run_async(test_model(model))

    if success:
        console.print(f"[green]✓ Модель {model} доступна[/green]")
        return model
    else:
        console.print(f"[red]✗ {msg}[/red]")
        retry = questionary.confirm(
            "Сохранить без проверки?",
            default=False,
            style=WIZARD_STYLE,
        ).ask()
        return model if retry else None


def select_providers(existing_env: dict[str, str]) -> list[str]:
    """Выбор провайдеров через checkbox."""
    choices = []
    for provider_id, info in PROVIDER_INFO.items():
        is_configured = bool(existing_env.get(info["env_key"]))
        label = info["name"]
        if is_configured:
            label += " (настроен)"
        choices.append(questionary.Choice(title=label, value=provider_id))

    selected = questionary.checkbox(
        "Выберите провайдеров для настройки:",
        choices=choices,
        style=WIZARD_STYLE,
        instruction="(Space - выбрать, Enter - подтвердить)",
    ).ask()

    return selected or []


def collect_api_key(provider: str, existing_value: str = "") -> str:
    """Собирает API ключ для провайдера."""
    info = PROVIDER_INFO[provider]
    console.print(f"\n[bold cyan]{info['name']}[/bold cyan]")
    console.print(f"[dim]Получить ключ: {info['url']}[/dim]")

    if existing_value:
        masked = (
            existing_value[:4] + "*" * (len(existing_value) - 8) + existing_value[-4:]
        )
        console.print(f"[dim]Текущий ключ: {masked}[/dim]")

    default = info.get("default_value", "")
    prompt_text = f"API ключ{' (Enter для текущего)' if existing_value else ''}: "

    key = questionary.password(
        prompt_text,
        style=WIZARD_STYLE,
    ).ask()

    if not key and existing_value:
        return existing_value
    if not key and default:
        return default

    return key or ""


CUSTOM_MODEL_OPTION = "[+ Другая модель...]"


def select_default_model(enabled_providers: list[str]) -> str:
    """Выбор модели по умолчанию."""
    choices = []
    for provider_id in enabled_providers:
        info = PROVIDER_INFO.get(provider_id, {})
        for model in info.get("models", []):
            choices.append(model)

    # Добавляем опцию ввода произвольной модели
    choices.append(CUSTOM_MODEL_OPTION)

    if len(choices) == 1:
        # Только опция "Ввести свою модель"
        return input_custom_model(enabled_providers) or "gemini/gemini-2.0-flash"

    selected = questionary.select(
        "Модель по умолчанию:",
        choices=choices,
        style=WIZARD_STYLE,
    ).ask()

    if selected == CUSTOM_MODEL_OPTION:
        custom = input_custom_model(enabled_providers)
        return custom or choices[0]

    return selected or choices[0]


def get_configured_providers(env: dict[str, str]) -> list[str]:
    """Возвращает список провайдеров с настроенными ключами."""
    configured = []
    for provider_id, info in PROVIDER_INFO.items():
        if env.get(info["env_key"]):
            configured.append(provider_id)
    return configured


def select_compare_models(
    enabled_providers: list[str], default_model: str, existing_env: dict[str, str]
) -> str:
    """Выбор моделей для сравнения."""
    # Показываем модели всех настроенных провайдеров (не только новых)
    all_configured = set(enabled_providers) | set(
        get_configured_providers(existing_env)
    )

    choices = []
    for provider_id in PROVIDER_INFO:
        if provider_id not in all_configured:
            continue
        info = PROVIDER_INFO.get(provider_id, {})
        for model in info.get("models", []):
            choices.append(
                questionary.Choice(
                    title=model,
                    value=model,
                    checked=(model != default_model),
                )
            )

    # Добавляем опцию ввода произвольной модели
    choices.append(
        questionary.Choice(title=CUSTOM_MODEL_OPTION, value=CUSTOM_MODEL_OPTION)
    )

    if len(choices) == 1:
        return default_model

    selected = questionary.checkbox(
        "Модели для сравнения (advisor_compare_experts):",
        choices=choices,
        style=WIZARD_STYLE,
        instruction="(Space - выбрать, Enter - подтвердить)",
    ).ask()

    if not selected:
        return default_model

    # Обработка выбора произвольной модели
    result_models = []
    for model in selected:
        if model == CUSTOM_MODEL_OPTION:
            custom = input_custom_model(enabled_providers)
            if custom:
                result_models.append(custom)
        else:
            result_models.append(model)

    return ",".join(result_models) if result_models else default_model


def configure_options(existing_env: dict[str, str]) -> dict[str, str]:
    """Настройка дополнительных опций."""
    options = {}

    # Кэширование
    cache_enabled = questionary.confirm(
        "Включить кэширование ответов?",
        default=existing_env.get("ADVISOR_CACHE_ENABLED", "true").lower() == "true",
        style=WIZARD_STYLE,
    ).ask()

    options["ADVISOR_CACHE_ENABLED"] = "true" if cache_enabled else "false"

    if cache_enabled:
        cache_ttl = questionary.text(
            "TTL кэша в секундах:",
            default=existing_env.get("ADVISOR_CACHE_TTL", "3600"),
            style=WIZARD_STYLE,
        ).ask()
        options["ADVISOR_CACHE_TTL"] = cache_ttl or "3600"

    # Verbose логирование
    verbose = questionary.confirm(
        "Включить подробное логирование?",
        default=existing_env.get("ADVISOR_VERBOSE", "false").lower() == "true",
        style=WIZARD_STYLE,
    ).ask()

    options["ADVISOR_VERBOSE"] = "true" if verbose else "false"

    return options


# ===== Action-based Menu Functions =====


def action_add_provider() -> None:
    """Добавить нового провайдера."""
    env = load_config()
    configured = get_configured_providers(env)

    # Показываем только ненастроенные провайдеры
    choices = []
    for provider_id, info in PROVIDER_INFO.items():
        if provider_id in configured:
            continue
        choices.append(questionary.Choice(title=info["name"], value=provider_id))

    if not choices:
        console.print("[yellow]Все провайдеры уже настроены.[/yellow]")
        return

    selected = questionary.select(
        "Выберите провайдера:",
        choices=choices,
        style=WIZARD_STYLE,
    ).ask()

    if not selected:
        return

    info = PROVIDER_INFO[selected]
    api_key = collect_api_key(selected)

    if not api_key:
        console.print("[yellow]Отменено.[/yellow]")
        return

    # Тестируем подключение
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task(description="Проверка подключения...", total=None)
        success, message = run_async(test_connection(selected, api_key))

    if success:
        console.print(f"[green]✓ {info['name']} подключён успешно[/green]")
        env[info["env_key"]] = api_key

        # Дополнительные переменные окружения
        if "extra_env" in info:
            for k, v in info["extra_env"].items():
                env[k] = v

        save_config(env)
    else:
        console.print(f"[red]✗ Ошибка: {message}[/red]")
        retry = questionary.confirm(
            "Сохранить ключ без проверки?",
            default=False,
            style=WIZARD_STYLE,
        ).ask()

        if retry:
            env[info["env_key"]] = api_key
            save_config(env)
            console.print(f"[green]✓ {info['name']} добавлен (без проверки)[/green]")


def action_remove_provider() -> None:
    """Удалить провайдера."""
    env = load_config()
    configured = get_configured_providers(env)

    if not configured:
        console.print("[yellow]Нет настроенных провайдеров.[/yellow]")
        return

    choices = []
    for provider_id in configured:
        info = PROVIDER_INFO[provider_id]
        choices.append(questionary.Choice(title=info["name"], value=provider_id))

    selected = questionary.select(
        "Выберите провайдера для удаления:",
        choices=choices,
        style=WIZARD_STYLE,
    ).ask()

    if not selected:
        return

    info = PROVIDER_INFO[selected]
    confirm = questionary.confirm(
        f"Удалить {info['name']}?",
        default=False,
        style=WIZARD_STYLE,
    ).ask()

    if confirm:
        del env[info["env_key"]]
        save_config(env)
        console.print(f"[green]✓ {info['name']} удалён[/green]")


def action_change_model() -> None:
    """Сменить модель по умолчанию (ask)."""
    env = load_config()
    configured = get_configured_providers(env)

    if not configured:
        console.print("[yellow]Сначала добавьте провайдера.[/yellow]")
        return

    current = env.get("ADVISOR_DEFAULT_MODEL", "не задана")
    console.print(f"[dim]Текущая модель: {current}[/dim]\n")

    new_model = select_default_model(configured)
    env["ADVISOR_DEFAULT_MODEL"] = new_model
    save_config(env)

    console.print(f"[green]✓ Модель по умолчанию: {new_model}[/green]")


def action_configure_compare() -> None:
    """Настроить модели для консилиума (compare)."""
    env = load_config()
    configured = get_configured_providers(env)

    if not configured:
        console.print("[yellow]Сначала добавьте провайдера.[/yellow]")
        return

    current = env.get("ADVISOR_DEFAULT_MODELS_COMPARE", "не заданы")
    console.print(f"[dim]Текущие модели: {current}[/dim]\n")

    default_model = env.get("ADVISOR_DEFAULT_MODEL", "")
    new_models = select_compare_models(configured, default_model, env)
    env["ADVISOR_DEFAULT_MODELS_COMPARE"] = new_models
    save_config(env)

    console.print(f"[green]✓ Модели для сравнения: {new_models}[/green]")


def action_show_settings() -> None:
    """Показать текущие настройки."""
    from rich.table import Table

    from .config import CACHE_DIR, CONFIG_FILE, mask_api_key

    env = load_config()

    console.print(f"\n[bold]Расположение конфигурации:[/bold] {CONFIG_FILE}")
    console.print(f"[bold]Директория кэша:[/bold] {CACHE_DIR}\n")

    # Таблица провайдеров
    table = Table(title="Провайдеры")
    table.add_column("Провайдер", style="cyan")
    table.add_column("Статус")
    table.add_column("API ключ")

    for provider_id, info in PROVIDER_INFO.items():
        key = env.get(info["env_key"], "")
        if key:
            status = "[green]настроен[/green]"
            masked = mask_api_key(key)
        else:
            status = "[dim]не настроен[/dim]"
            masked = "-"
        table.add_row(info["name"], status, masked)

    console.print(table)

    # Модели
    console.print(
        f"\n[bold]Модель по умолчанию (ask):[/bold] {env.get('ADVISOR_DEFAULT_MODEL', 'не задана')}"
    )
    console.print(
        f"[bold]Модели для сравнения (compare):[/bold] {env.get('ADVISOR_DEFAULT_MODELS_COMPARE', 'не заданы')}"
    )

    # Опции
    cache = env.get("ADVISOR_CACHE_ENABLED", "true")
    cache_ttl = env.get("ADVISOR_CACHE_TTL", "3600")
    verbose = env.get("ADVISOR_VERBOSE", "false")

    console.print(
        f"\n[bold]Кэширование:[/bold] {'включено' if cache == 'true' else 'выключено'} (TTL: {cache_ttl}s)"
    )
    console.print(
        f"[bold]Подробное логирование:[/bold] {'включено' if verbose == 'true' else 'выключено'}"
    )
    console.print("")


def action_purge_data() -> None:
    """Очистить все данные."""
    from .config import purge_all

    confirm = questionary.confirm(
        "Удалить ВСЕ данные (конфигурацию и кэш)?",
        default=False,
        style=WIZARD_STYLE,
    ).ask()

    if not confirm:
        console.print("[yellow]Отменено.[/yellow]")
        return

    config_removed, cache_removed = purge_all()

    if config_removed:
        console.print("[green]✓ Конфигурация удалена[/green]")
    if cache_removed:
        console.print("[green]✓ Кэш удалён[/green]")

    if not config_removed and not cache_removed:
        console.print("[yellow]Нечего удалять.[/yellow]")


# ===== Menu Actions =====

MENU_ACTIONS = {
    "add_provider": ("Добавить провайдера", action_add_provider),
    "remove_provider": ("Удалить провайдера", action_remove_provider),
    "change_model": ("Сменить модель (ask)", action_change_model),
    "configure_compare": ("Настроить консилиум (compare)", action_configure_compare),
    "show_settings": ("Показать настройки", action_show_settings),
    "purge_data": ("Очистить все данные", action_purge_data),
    "exit": ("Выход", None),
}


def run_setup(
    non_interactive: bool = False,
    providers: list[str] | None = None,
    model: str | None = None,
):
    """Главная функция wizard'а с action-based меню.

    Args:
        non_interactive: If True, use defaults and env vars without prompts
        providers: List of provider IDs to configure (for -y mode)
        model: Default model to set (for -y mode)
    """
    if non_interactive:
        success = setup_from_env()
        if success:
            console.print(
                "[green]✓ Конфигурация создана из переменных окружения[/green]"
            )
        else:
            console.print("[red]✗ Не найдены API ключи в окружении[/red]")
            console.print("[dim]Установите GEMINI_API_KEY, OPENAI_API_KEY и т.д.[/dim]")
        return

    console.print(
        Panel(
            "[bold cyan]MCP Advisor — Настройка[/bold cyan]",
            border_style="cyan",
        )
    )

    # Проверяем наличие legacy конфигурации и предлагаем миграцию
    from .config import migrate_legacy_config

    if migrate_legacy_config(interactive=True):
        console.print(
            "[green]✓ Конфигурация мигрирована в новое расположение[/green]\n"
        )

    # Главный цикл меню
    while True:
        # Формируем выборы для меню
        choices = []
        for action_id, (label, _) in MENU_ACTIONS.items():
            choices.append(questionary.Choice(title=label, value=action_id))

        selected = questionary.select(
            "Что хотите сделать?",
            choices=choices,
            style=WIZARD_STYLE,
        ).ask()

        if not selected or selected == "exit":
            console.print("[dim]До свидания![/dim]")
            break

        # Выполняем выбранное действие
        _, action_func = MENU_ACTIONS[selected]
        if action_func:
            console.print("")
            action_func()
            console.print("")


if __name__ == "__main__":
    run_setup()
