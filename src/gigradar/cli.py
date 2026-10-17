"""Command Line Interface for GigRadar."""

import typer
from rich.console import Console
from rich.table import Table

from gigradar import __version__
from gigradar.core.config_loader import validate_all_configs
from gigradar.core.gemini_verifier import mask_key, verify_gemini_key
from gigradar.core.logging import setup_logging
from gigradar.core.settings import get_settings

app = typer.Typer(
    name="gigradar",
    help="GigRadar: Multi-layer freelancing automation system.",
    no_args_is_help=True,
)
console = Console()


def version_callback(value: bool) -> None:
    if value:
        console.print(f"[bold green]GigRadar[/bold green] version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        help="Show GigRadar version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """GigRadar main entry point."""


@app.command(name="doctor")
def doctor(
    skip_live_llm: bool = typer.Option(
        False,
        "--skip-live-llm",
        help="Skip live network check to Gemini API.",
    ),
) -> None:
    """Run diagnostics on environment, configurations, database URL, and live LLM key."""
    settings = get_settings()
    setup_logging(log_level=settings.log_level, log_format="console")

    console.print(
        f"\n[bold cyan]=== GigRadar Doctor (v{__version__}) ===[/bold cyan]\n",
    )

    all_passed = True

    # 1. Configuration Files
    config_table = Table(title="Configuration Files (YAML)", show_header=True, header_style="bold magenta")
    config_table.add_column("Config File", style="cyan", width=25)
    config_table.add_column("Status", width=15)
    config_table.add_column("Details", style="dim")

    config_results = validate_all_configs(settings.config_dir)
    for filename, status in config_results.items():
        if status == "OK":
            config_table.add_row(filename, "[green]OK[/green]", "Valid schema & data")
        else:
            all_passed = False
            config_table.add_row(filename, "[red]FAIL[/red]", status)
    console.print(config_table)
    console.print()

    # 2. Environment & Settings
    env_table = Table(title="Environment & Settings", show_header=True, header_style="bold magenta")
    env_table.add_column("Setting", style="cyan", width=28)
    env_table.add_column("Value / Status", width=25)
    env_table.add_column("Notes", style="dim")

    # DB Check
    env_table.add_row("DATABASE_URL", settings.database_url, "SQLite/Postgres ready")

    # Telegram Checks
    if settings.telegram_bot_token:
        masked_tg = mask_key(settings.telegram_bot_token.get_secret_value())
        env_table.add_row("TELEGRAM_BOT_TOKEN", f"[green]Configured[/green] ({masked_tg})", "Ready")
    else:
        env_table.add_row("TELEGRAM_BOT_TOKEN", "[yellow]Not Set[/yellow]", "Needed for Phase 4")

    if settings.telegram_allowed_chat_id:
        env_table.add_row("TELEGRAM_ALLOWED_CHAT_ID", str(settings.telegram_allowed_chat_id), "Whitelisted user")
    else:
        env_table.add_row("TELEGRAM_ALLOWED_CHAT_ID", "[yellow]Not Set[/yellow]", "Needed for Phase 4")

    # Pipeline params
    env_table.add_row("SCORE_THRESHOLD", str(settings.score_threshold), "Min score for notification")
    env_table.add_row("AUTO_SUBMIT", str(settings.auto_submit), "Safe default: False")
    env_table.add_row("LLM_MODEL_SCORER", settings.llm_model_scorer, "Flash-class scorer")
    env_table.add_row("LLM_MODEL_PITCH", settings.llm_model_pitch, "Pitch generator")

    console.print(env_table)
    console.print()

    # 3. Gemini API Live Key Verification
    llm_table = Table(title="Google Gemini API Verification", show_header=True, header_style="bold magenta")
    llm_table.add_column("Check", style="cyan", width=25)
    llm_table.add_column("Status", width=15)
    llm_table.add_column("Details", style="dim")

    raw_key = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else None
    masked_gemini = mask_key(raw_key)

    if not raw_key:
        llm_table.add_row("GEMINI_API_KEY", "[yellow]NOT SET[/yellow]", "Set GEMINI_API_KEY in .env")
        llm_table.add_row("Live Connectivity", "[yellow]SKIPPED[/yellow]", "No key provided")
    elif skip_live_llm:
        llm_table.add_row("GEMINI_API_KEY", f"[green]FOUND[/green] ({masked_gemini})", "Key present")
        llm_table.add_row("Live Connectivity", "[cyan]SKIPPED[/cyan]", "--skip-live-llm passed")
    else:
        llm_table.add_row("GEMINI_API_KEY", f"[green]FOUND[/green] ({masked_gemini})", "Key present")
        with console.status("[bold green]Contacting Gemini API...[/bold green]"):
            is_valid, msg = verify_gemini_key(raw_key, model_id=settings.llm_model_scorer)
        if is_valid:
            llm_table.add_row("Live Connectivity", "[green]PASS[/green]", msg)
        else:
            all_passed = False
            llm_table.add_row("Live Connectivity", "[red]FAIL[/red]", msg)

    console.print(llm_table)
    console.print()

    # Summary
    if all_passed and raw_key:
        console.print("[bold green]Doctor check complete: System is healthy and ready![/bold green]\n")
    elif all_passed and not raw_key:
        console.print(
            "[bold yellow]Doctor check complete: Configurations valid. Set GEMINI_API_KEY in .env when ready for live LLM tests.[/bold yellow]\n",
        )
    else:
        console.print(
            "[bold red]Doctor check found issues. Review table errors above before proceeding.[/bold red]\n",
        )
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
