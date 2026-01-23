"""Configuration commands for advisor CLI.

This module provides configuration management commands:
- config_single: Set default model for ask command
- config_compare: Set models for compare command
- config_format: Set default output format
- config_show: Show current configuration
- config_purge: Remove configuration file

The config_app typer application is designed to be added as a subcommand
group to the main CLI application.
"""

import typer

from .cli_output import print_output
from .utils import run_async

config_app = typer.Typer(help="Manage configuration")


@config_app.command("single")
def config_single(
    model: str = typer.Argument(..., help="Model (e.g.: gemini/gemini-2.5-pro)"),
    check: bool = typer.Option(
        True, "--check/--no-check", help="Check model availability"
    ),
) -> None:
    """Set default model for ask (single query)."""
    if "/" not in model:
        print_output("Error: Model format: provider/model", error=True)
        raise typer.Exit(1)

    if check:
        print_output("Checking model...")
        try:
            from .setup_wizard import test_model

            success, msg = run_async(test_model(model))
            if not success:
                print_output(f"Error: {msg}", error=True)
                raise typer.Exit(1)
            print_output("OK - Model available")
        except ImportError:
            print_output("Wizard not installed, skipping check")

    from .config import update_config

    update_config("ADVISOR_DEFAULT_MODEL", model)
    print_output(f"Default model: {model}")


@config_app.command("compare")
def config_compare(
    models_str: str = typer.Argument(
        ...,
        help="Models comma-separated (e.g.: gemini/gemini-2.0-flash,openai/gpt-4o)",
    ),
    check: bool = typer.Option(
        True, "--check/--no-check", help="Check models availability"
    ),
) -> None:
    """Set models for compare (council)."""
    model_list = [m.strip() for m in models_str.split(",") if m.strip()]

    if not model_list:
        print_output("Error: Models list is empty", error=True)
        raise typer.Exit(1)

    if check:
        try:
            from .setup_wizard import test_model

            all_ok = True
            for model in model_list:
                if "/" not in model:
                    print_output(f"  {model}: X Invalid format", error=True)
                    all_ok = False
                    continue

                print_output(f"Checking {model}...")
                success, msg = run_async(test_model(model))

                if success:
                    print_output(f"  {model}: OK")
                else:
                    print_output(f"  {model}: X {msg}", error=True)
                    all_ok = False

            if not all_ok:
                print_output("\nSome models are unavailable")
        except ImportError:
            print_output("Wizard not installed, skipping check")

    from .config import update_config

    update_config("ADVISOR_DEFAULT_MODELS_COMPARE", ",".join(model_list))
    print_output(f"\nModels for compare: {', '.join(model_list)}")


@config_app.command("format")
def config_format(
    fmt: str = typer.Argument(..., help="Default format: markdown|json"),
) -> None:
    """Set default output format."""
    if fmt.lower() not in ("markdown", "json"):
        print_output("Error: Format must be markdown or json", error=True)
        raise typer.Exit(1)

    from .config import update_config

    update_config("ADVISOR_OUTPUT_FORMAT", fmt.lower())
    print_output(f"Default format: {fmt.lower()}")


@config_app.command("show")
def config_show() -> None:
    """Show current configuration and file locations."""
    from .config import CACHE_DIR, CONFIG_FILE, load_config, mask_api_key

    print_output("\n=== Advisor CLI Configuration ===\n")
    print_output(f"Config file: {CONFIG_FILE}")
    print_output(f"Cache dir:   {CACHE_DIR}")
    print_output(f"Config exists: {CONFIG_FILE.exists()}")
    print_output(f"Cache exists:  {CACHE_DIR.exists()}")

    if not CONFIG_FILE.exists():
        print_output("\nConfiguration not found. Run: advisor setup")
        return

    env = load_config()

    print_output("\n--- API Keys ---")
    api_keys = [
        ("GEMINI_API_KEY", "Gemini"),
        ("OPENAI_API_KEY", "OpenAI"),
        ("ANTHROPIC_API_KEY", "Anthropic"),
        ("DEEPSEEK_API_KEY", "DeepSeek"),
        ("GROQ_API_KEY", "Groq"),
        ("OPENROUTER_API_KEY", "OpenRouter"),
        ("OLLAMA_HOST", "Ollama"),
        ("OLLAMA_API_KEY", "Ollama Cloud"),
    ]

    for key, name in api_keys:
        value = env.get(key, "")
        if value:
            print_output(f"  {name}: {mask_api_key(value)}")

    print_output("\n--- Models ---")
    print_output(f"  Default (ask):     {env.get('ADVISOR_DEFAULT_MODEL', 'not set')}")
    print_output(
        f"  Compare (compare): {env.get('ADVISOR_DEFAULT_MODELS_COMPARE', 'not set')}"
    )

    print_output("\n--- Options ---")
    cache = env.get("ADVISOR_CACHE_ENABLED", "true")
    ttl = env.get("ADVISOR_CACHE_TTL", "3600")
    verbose = env.get("ADVISOR_VERBOSE", "false")
    print_output(
        f"  Cache: {'enabled' if cache == 'true' else 'disabled'} (TTL: {ttl}s)"
    )
    print_output(f"  Verbose: {'enabled' if verbose == 'true' else 'disabled'}")
    print_output("")


@config_app.command("purge")
def config_purge(
    force: bool = typer.Option(False, "--force", "-f", help="Without confirmation"),
) -> None:
    """Remove configuration file (API keys)."""
    from .config import CONFIG_FILE, purge_config

    if not CONFIG_FILE.exists():
        print_output("Configuration not found.")
        return

    if not force:
        print_output(f"Will be deleted: {CONFIG_FILE}")
        try:
            import questionary

            confirm = questionary.confirm(
                "Delete configuration (API keys)?",
                default=False,
            ).ask()
            if not confirm:
                print_output("Cancelled.")
                return
        except ImportError:
            print_output("Use --force to confirm", error=True)
            raise typer.Exit(1)

    if purge_config():
        print_output("Configuration deleted")
    else:
        print_output("Nothing deleted")


@config_app.command("cache-clear")
def config_cache_clear() -> None:
    """Clear reasoning model cache.

    This forces re-detection of reasoning capabilities for all models.
    Useful if a model's capabilities have changed or cache is corrupted.
    """
    from .core import get_cache_manager

    count = get_cache_manager().clear_reasoning_cache()
    print_output(f"Reasoning cache cleared ({count} entries removed)")
