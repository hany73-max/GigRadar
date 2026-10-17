import sys
from typing import Any

# Ensure UTF-8 output on Windows consoles to support Arabic text
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import typer
from rich.console import Console
from rich.table import Table

from gigradar import __version__
from gigradar.core.config_loader import validate_all_configs
from gigradar.core.gemini_verifier import is_placeholder, mask_key, verify_gemini_key
from gigradar.core.logging import setup_logging
from gigradar.core.settings import get_settings

app = typer.Typer(
    name="gigradar",
    help="GigRadar: Multi-layer freelancing automation system.",
    no_args_is_help=True,
)
console = Console(legacy_windows=False)


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
    has_placeholder = False

    # 1. Configuration Files
    config_table = Table(
        title="Configuration Files (YAML)", show_header=True, header_style="bold magenta"
    )
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
        raw_tg = settings.telegram_bot_token.get_secret_value()
        if is_placeholder(raw_tg):
            has_placeholder = True
            env_table.add_row(
                "TELEGRAM_BOT_TOKEN",
                "[yellow]PLACEHOLDER[/yellow]",
                "Example token from .env.example",
            )
        else:
            masked_tg = mask_key(raw_tg)
            env_table.add_row(
                "TELEGRAM_BOT_TOKEN", f"[green]Configured[/green] ({masked_tg})", "Ready"
            )
    else:
        env_table.add_row("TELEGRAM_BOT_TOKEN", "[yellow]Not Set[/yellow]", "Needed for Phase 4")

    if settings.telegram_allowed_chat_id is not None:
        if is_placeholder(settings.telegram_allowed_chat_id):
            has_placeholder = True
            env_table.add_row(
                "TELEGRAM_ALLOWED_CHAT_ID",
                "[yellow]PLACEHOLDER[/yellow]",
                "Example chat ID from .env.example",
            )
        else:
            env_table.add_row(
                "TELEGRAM_ALLOWED_CHAT_ID",
                str(settings.telegram_allowed_chat_id),
                "Whitelisted user",
            )
    else:
        env_table.add_row(
            "TELEGRAM_ALLOWED_CHAT_ID", "[yellow]Not Set[/yellow]", "Needed for Phase 4"
        )

    # Pipeline params
    env_table.add_row(
        "SCORE_THRESHOLD", str(settings.score_threshold), "Min score for notification"
    )
    env_table.add_row("AUTO_SUBMIT", str(settings.auto_submit), "Safe default: False")
    env_table.add_row("LLM_MODEL_SCORER", settings.llm_model_scorer, "Flash-class scorer")
    env_table.add_row("LLM_MODEL_PITCH", settings.llm_model_pitch, "Pitch generator")

    console.print(env_table)
    console.print()

    # 3. Gemini API Live Key Verification
    llm_table = Table(
        title="Google Gemini API Verification", show_header=True, header_style="bold magenta"
    )
    llm_table.add_column("Check", style="cyan", width=25)
    llm_table.add_column("Status", width=15)
    llm_table.add_column("Details", style="dim")

    raw_key = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else None

    if not raw_key:
        llm_table.add_row(
            "GEMINI_API_KEY", "[yellow]NOT SET[/yellow]", "Set GEMINI_API_KEY in .env"
        )
        llm_table.add_row("Live Connectivity", "[yellow]SKIPPED[/yellow]", "No key provided")
    elif is_placeholder(raw_key):
        has_placeholder = True
        llm_table.add_row(
            "GEMINI_API_KEY", "[yellow]PLACEHOLDER[/yellow]", f"'{raw_key}' from .env.example"
        )
        llm_table.add_row(
            "Live Connectivity", "[yellow]SKIPPED[/yellow]", "Placeholder key; add real key in .env"
        )
    elif skip_live_llm:
        masked_gemini = mask_key(raw_key)
        llm_table.add_row(
            "GEMINI_API_KEY", f"[green]FOUND[/green] ({masked_gemini})", "Key present"
        )
        llm_table.add_row("Live Connectivity", "[cyan]SKIPPED[/cyan]", "--skip-live-llm passed")
    else:
        masked_gemini = mask_key(raw_key)
        llm_table.add_row(
            "GEMINI_API_KEY", f"[green]FOUND[/green] ({masked_gemini})", "Key present"
        )
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
    if all_passed and not has_placeholder and raw_key:
        console.print(
            "[bold green]Doctor check complete: System is healthy and fully configured![/bold green]\n"
        )
    elif all_passed and has_placeholder:
        console.print(
            "[bold yellow]Doctor check complete: Configurations valid. Replace PLACEHOLDER values in .env with your real credentials when ready.[/bold yellow]\n",
        )
    elif all_passed and not raw_key:
        console.print(
            "[bold yellow]Doctor check complete: Configurations valid. Set GEMINI_API_KEY in .env when ready for live LLM tests.[/bold yellow]\n",
        )
    else:
        console.print(
            "[bold red]Doctor check found issues. Review table errors above before proceeding.[/bold red]\n",
        )
        raise typer.Exit(code=1)


async def _run_scrape_once(
    platform_name: str,
    limit: int,
    fetch_details: bool,
    all_gigs: bool = False,
) -> list[Any]:
    from datetime import UTC, datetime, timedelta

    from gigradar.platforms.freelancer.client import FreelancerClient
    from gigradar.platforms.khamsat.client import KhamsatClient
    from gigradar.platforms.mostaql.client import MostaqlClient

    platform_lower = platform_name.lower().strip()
    if platform_lower == "mostaql":
        async with MostaqlClient() as client:
            client.config.max_pages_per_run = 1
            stubs = await client.list_new_gigs()
            gigs = []
            for stub in stubs[:limit]:
                if fetch_details:
                    gig = await client.fetch_gig_detail(stub)
                else:
                    from gigradar.platforms.mostaql.parser import parse_mostaql_detail

                    gig = parse_mostaql_detail(
                        f"<html><head><link rel='canonical' href='{stub.url}'></head><body><h1 class='heada__title'>{stub.title}</h1><div id='projectDetailsTab'><div class='text-wrapper-div'>{stub.brief_description or stub.title}</div></div></body></html>",
                        stub=stub,
                    )
                gigs.append(gig)
            return gigs

    elif platform_lower == "khamsat":
        async with KhamsatClient() as client:
            client.config.max_pages_per_run = 1
            stubs = await client.list_new_gigs()
            gigs = []
            for stub in stubs[:limit]:
                gig = await client.fetch_gig_detail(stub)
                gigs.append(gig)
            return gigs

    elif platform_lower == "freelancer":
        async with FreelancerClient() as client:
            client.config.max_pages_per_run = 1
            since: datetime | None = None
            if not all_gigs:
                max_age_min = client.config.thresholds.max_gig_age_minutes
                since = datetime.now(UTC) - timedelta(minutes=max_age_min)
            stubs = await client.list_new_gigs(since=since)
            gigs = []
            for stub in stubs[:limit]:
                gig = await client.fetch_gig_detail(stub)
                gigs.append(gig)
            return gigs

    else:
        raise ValueError(
            f"Unknown platform '{platform_name}'. Supported platforms: mostaql, khamsat, freelancer"
        )


@app.command(name="scrape-once")
def scrape_once(
    platform: str = typer.Argument(
        ...,
        help="Target platform to scrape: 'mostaql', 'khamsat', or 'freelancer'.",
    ),
    limit: int = typer.Option(
        5,
        "--limit",
        "-n",
        help="Maximum number of gigs to fetch and display.",
    ),
    fetch_details: bool = typer.Option(
        True,
        "--fetch-details/--no-details",
        help="Fetch full details for stubs (Mostaql only).",
    ),
    all_gigs: bool = typer.Option(
        False,
        "--all",
        help="Disable max_gig_age_minutes age filter and fetch all available gigs.",
    ),
) -> None:
    """Scrape and print real parsed gigs from a platform in a readable table."""
    import asyncio

    from gigradar.platforms.common.normalization import format_budget_display

    platform_lower = platform.lower().strip()
    if platform_lower not in {"mostaql", "khamsat", "freelancer"}:
        console.print(
            f"[bold red]Error:[/bold red] Unsupported platform '{platform}'. Choose 'mostaql', 'khamsat', or 'freelancer'."
        )
        raise typer.Exit(code=1)

    console.print(
        f"\n[bold cyan]Scraping once from [green]{platform_lower}[/green] (limit: {limit})...[/bold cyan]\n"
    )

    try:
        gigs = asyncio.run(
            _run_scrape_once(
                platform_lower, limit=limit, fetch_details=fetch_details, all_gigs=all_gigs
            )
        )
    except Exception as exc:  # noqa: BLE001
        console.print(f"[bold red]Scraping failed:[/bold red] {exc}")
        raise typer.Exit(code=1) from None

    table = Table(
        title=f"Parsed Gigs from {platform_lower.capitalize()} ({len(gigs)} items)",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="bold")
    table.add_column("Budget")
    table.add_column("Bids", justify="right")
    table.add_column("Posted (UTC)")
    table.add_column("Client")
    table.add_column("Lang")

    for gig in gigs:
        budget_str = format_budget_display(gig=gig)
        posted_str = gig.posted_at.strftime("%Y-%m-%d %H:%M") if gig.posted_at else "-"
        client_str = gig.client_name or "-"
        bids_str = str(gig.bids_count) if gig.bids_count is not None else "-"

        table.add_row(
            gig.external_id,
            gig.title[:35],
            budget_str,
            bids_str,
            posted_str,
            client_str[:13],
            gig.language,
        )

    console.print(table)
    console.print()


if __name__ == "__main__":
    app()
