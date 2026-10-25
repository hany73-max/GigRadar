import sys
from datetime import UTC, datetime
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
from gigradar.core.config_loader import resolve_platform_thresholds, validate_all_configs
from gigradar.core.gemini_verifier import is_placeholder, mask_key, verify_gemini_key
from gigradar.core.logging import setup_logging
from gigradar.core.settings import get_settings, reload_settings

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
    offline: bool = typer.Option(
        False,
        "--offline",
        help="Skip all live network checks (Gemini and platform health checks).",
    ),
) -> None:
    """Run diagnostics on environment, configurations, database URL, and live LLM key."""
    settings = reload_settings()
    setup_logging(log_level=settings.log_level, log_format="console")

    console.print(
        f"\n[bold cyan]=== GigRadar Doctor (v{__version__}) ===[/bold cyan]\n",
    )

    all_passed = True
    has_placeholder = False
    has_pending_migration = False

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

    # 3. Database & Migrations Check
    import asyncio

    from gigradar.db.helpers import check_db_connectivity_and_version

    db_table = Table(title="Database & Migrations", show_header=True, header_style="bold magenta")
    db_table.add_column("Component", style="cyan", width=25)
    db_table.add_column("Status", width=15)
    db_table.add_column("Details", style="dim")

    try:
        is_healthy, db_msg, current_rev, head_rev = asyncio.run(
            check_db_connectivity_and_version(database_url=settings.database_url)
        )
        if is_healthy:
            db_table.add_row("Connection", "[green]PASS[/green]", "Connected successfully")
            if current_rev == head_rev and current_rev is not None:
                db_table.add_row(
                    "Migrations", "[green]UP TO DATE[/green]", f"Revision: {current_rev}"
                )
            elif current_rev is None:
                has_pending_migration = True
                db_table.add_row(
                    "Migrations", "[yellow]PENDING[/yellow]", "Run 'gigradar db upgrade'"
                )
            else:
                has_pending_migration = True
                db_table.add_row(
                    "Migrations",
                    "[yellow]PENDING[/yellow]",
                    f"Current: {current_rev}, Head: {head_rev} (run 'gigradar db upgrade')",
                )
        else:
            all_passed = False
            db_table.add_row("Connection", "[red]FAIL[/red]", db_msg)
            db_table.add_row("Migrations", "[yellow]SKIPPED[/yellow]", "No DB connection")
    except Exception as exc:
        all_passed = False
        db_table.add_row("Connection", "[red]FAIL[/red]", str(exc))
        db_table.add_row("Migrations", "[yellow]SKIPPED[/yellow]", "Error during check")

    console.print(db_table)
    console.print()

    # 3. Gemini API Live Key & Model Verification
    llm_table = Table(
        title="Google Gemini API Verification", show_header=True, header_style="bold magenta"
    )
    llm_table.add_column("Check / Model", style="cyan", width=28)
    llm_table.add_column("Status", width=15)
    llm_table.add_column("Details", style="dim")

    raw_key = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else None
    models_to_test = [
        ("Scorer", settings.llm_model_scorer),
        ("Pitch", settings.llm_model_pitch),
    ]

    if not raw_key:
        llm_table.add_row(
            "GEMINI_API_KEY", "[yellow]NOT SET[/yellow]", "Set GEMINI_API_KEY in .env"
        )
        for role, model in models_to_test:
            llm_table.add_row(f"{role} ({model})", "[yellow]SKIPPED[/yellow]", "No key provided")
    elif is_placeholder(raw_key):
        has_placeholder = True
        llm_table.add_row(
            "GEMINI_API_KEY", "[yellow]PLACEHOLDER[/yellow]", f"'{raw_key}' from .env.example"
        )
        for role, model in models_to_test:
            llm_table.add_row(
                f"{role} ({model})",
                "[yellow]SKIPPED[/yellow]",
                "Placeholder key; add real key in .env",
            )
    elif offline:
        masked_gemini = mask_key(raw_key)
        llm_table.add_row(
            "GEMINI_API_KEY", f"[green]FOUND[/green] ({masked_gemini})", "Key present"
        )
        for role, model in models_to_test:
            llm_table.add_row(f"{role} ({model})", "[cyan]SKIPPED[/cyan]", "--offline passed")
    elif skip_live_llm:
        masked_gemini = mask_key(raw_key)
        llm_table.add_row(
            "GEMINI_API_KEY", f"[green]FOUND[/green] ({masked_gemini})", "Key present"
        )
        for role, model in models_to_test:
            llm_table.add_row(f"{role} ({model})", "[cyan]SKIPPED[/cyan]", "--skip-live-llm passed")
    else:
        masked_gemini = mask_key(raw_key)
        llm_table.add_row(
            "GEMINI_API_KEY", f"[green]FOUND[/green] ({masked_gemini})", "Key present"
        )
        for role, model in models_to_test:
            with console.status(
                f"[bold green]Testing 1-token generation for {role} ({model})...[/bold green]"
            ):
                is_valid, msg = verify_gemini_key(raw_key, model_id=model)
            if is_valid:
                llm_table.add_row(f"{role} ({model})", "[green]PASS[/green]", msg)
            else:
                all_passed = False
                llm_table.add_row(f"{role} ({model})", "[red]FAIL[/red]", msg)

    console.print(llm_table)
    console.print()

    # 5. Platform Health Checks
    plat_health_table = Table(
        title="Platform Health Checks", show_header=True, header_style="bold magenta"
    )
    plat_health_table.add_column("Platform", style="cyan", width=25)
    plat_health_table.add_column("Status", width=15)
    plat_health_table.add_column("Details", style="dim")

    if offline:
        plat_health_table.add_row(
            "All Platforms",
            "[cyan]SKIPPED[/cyan]",
            "--offline passed",
        )
    else:
        from gigradar.core.config_loader import load_platforms_config
        from gigradar.pipeline.orchestrator import PlatformOrchestrator

        platforms_cfg = load_platforms_config()
        orchestrator = PlatformOrchestrator()

        async def run_platform_checks() -> list[tuple[str, bool, str]]:
            checks: list[tuple[str, bool, str]] = []
            for name, p_settings in platforms_cfg.platforms.items():
                if not p_settings.enabled:
                    checks.append((name, True, "Disabled in platforms.yaml (skipped)"))
                    continue
                client = orchestrator.get_client(name)
                try:
                    rep = await client.health_check()
                    checks.append((name, rep.is_healthy, rep.message))
                except Exception as exc:
                    checks.append((name, False, f"Exception: {exc}"))
            await orchestrator.close_clients()
            return checks

        with console.status("[bold green]Checking platform health...[/bold green]"):
            health_reports = asyncio.run(run_platform_checks())

        for p_name, p_ok, p_msg in health_reports:
            if not p_ok:
                all_passed = False
                plat_health_table.add_row(p_name, "[red]FAIL[/red]", p_msg)
            else:
                plat_health_table.add_row(p_name, "[green]PASS[/green]", p_msg)

    console.print(plat_health_table)
    console.print()

    # Summary
    if all_passed and not has_placeholder and not has_pending_migration and raw_key:
        console.print(
            "[bold green]Doctor check complete: System is healthy and fully configured![/bold green]\n"
        )
    elif all_passed and has_pending_migration:
        console.print(
            "[bold yellow]Doctor check complete: Configurations valid. Run 'gigradar db upgrade' to apply pending migrations.[/bold yellow]\n",
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
    from datetime import datetime, timedelta

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
                max_age_min = resolve_platform_thresholds("freelancer").max_gig_age_minutes
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


# ------------------------------------------------------------------------------
# Database Subcommands: gigradar db upgrade, gigradar db stats
# ------------------------------------------------------------------------------
db_app = typer.Typer(
    name="db",
    help="Database maintenance and migration operations.",
    no_args_is_help=True,
)
app.add_typer(db_app, name="db")


@db_app.command(name="upgrade")
def db_upgrade(
    revision: str = typer.Option(
        "head", "--revision", "-r", help="Target revision (default: head)."
    ),
) -> None:
    """Run Alembic database migrations up to head."""
    from gigradar.core.settings import reload_settings
    from gigradar.db.helpers import run_db_upgrade

    settings = reload_settings()
    console.print(f"[bold cyan]Running database upgrade to '{revision}'...[/bold cyan]")
    try:
        run_db_upgrade(revision, database_url=settings.database_url)
        console.print("[bold green]Database upgrade successful![/bold green]")
    except Exception as exc:
        console.print(f"[bold red]Database upgrade failed:[/bold red] {exc}")
        raise typer.Exit(code=1) from None


@db_app.command(name="stats")
def db_stats() -> None:
    """Display stored gigs per platform, total, last run, and paused platforms."""
    import asyncio

    from gigradar.core.settings import reload_settings
    from gigradar.db.repositories.gig_repo import GigRepository
    from gigradar.db.repositories.platform_repo import PlatformRepository
    from gigradar.db.repositories.scrape_run_repo import ScrapeRunRepository
    from gigradar.db.session import create_engine_from_url, get_async_session

    settings = reload_settings()

    async def fetch_stats() -> tuple[dict[str, Any], list[dict[str, Any]]]:
        engine = create_engine_from_url(settings.database_url)
        try:
            async with get_async_session(engine=engine) as session:
                gig_repo = GigRepository(session)
                platform_repo = PlatformRepository(session)
                scrape_run_repo = ScrapeRunRepository(session)

                stats = await gig_repo.get_stats()
                platforms = await platform_repo.list_all()
                details: list[dict[str, Any]] = []
                for plat in platforms:
                    last_finished = await scrape_run_repo.get_last_finished_run(plat.id)
                    failed_24h = await scrape_run_repo.count_failed_or_interrupted_runs_24h(plat.id)
                    last_error_info = await scrape_run_repo.get_latest_error_info(plat.id)
                    last_err_msg = last_error_info[0] if last_error_info else None
                    last_err_time = last_error_info[1] if last_error_info else None
                    if isinstance(last_err_time, datetime):
                        err_time_str = last_err_time.strftime("%Y-%m-%d %H:%M:%S")
                    elif isinstance(last_err_time, str):
                        err_time_str = last_err_time[:19].replace("T", " ")
                    else:
                        err_time_str = None

                    details.append(
                        {
                            "name": plat.name,
                            "is_paused": plat.is_paused,
                            "paused_until": plat.paused_until,
                            "pause_reason": plat.pause_reason,
                            "last_finished_run": last_finished,
                            "failed_24h": failed_24h,
                            "last_error": last_err_msg,
                            "last_error_time": err_time_str,
                        }
                    )
                return stats, details
        finally:
            await engine.dispose()

    try:
        stats, details = asyncio.run(fetch_stats())
    except Exception as exc:
        console.print(f"[bold red]Failed fetching database stats:[/bold red] {exc}")
        raise typer.Exit(code=1) from None

    console.print("\n[bold cyan]=== GigRadar Database Stats ===[/bold cyan]\n")

    summary_table = Table(title="Storage Summary", show_header=True, header_style="bold magenta")
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="bold")

    summary_table.add_row("Total Stored Gigs", str(stats.get("total_gigs", 0)))
    for state, count in stats.get("by_state", {}).items():
        summary_table.add_row(f"State: {state}", str(count))
    console.print(summary_table)
    console.print()

    plat_table = Table(
        title="Platform Status & Last Scrape", show_header=True, header_style="bold magenta"
    )
    plat_table.add_column("Platform", style="cyan")
    plat_table.add_column("Stored Gigs", justify="right")
    plat_table.add_column("Status", style="bold")
    plat_table.add_column("Last Finished (UTC)")
    plat_table.add_column("Last Found", justify="right")
    plat_table.add_column("Last New", justify="right")
    plat_table.add_column("Errors")
    plat_table.add_column("Failed (24h)", justify="right")
    plat_table.add_column("Last Error", max_width=40, overflow="fold")

    by_plat = stats.get("by_platform", {})
    for item in details:
        p_name = item["name"]
        gig_count = str(by_plat.get(p_name, 0))
        status = "[red]PAUSED[/red]" if item["is_paused"] else "[green]ACTIVE[/green]"
        if item["is_paused"] and item["paused_until"]:
            status += f" (until {item['paused_until'].strftime('%H:%M:%S')})"

        lr = item["last_finished_run"]
        if lr:
            lr_finished = lr.finished_at.strftime("%Y-%m-%d %H:%M:%S") if lr.finished_at else "-"
            lr_found = str(lr.gigs_found)
            lr_new = str(lr.gigs_new)
            lr_err = (
                f"[red]{len(lr.errors_json)} errs[/red]"
                if lr.errors_json
                else "[green]None[/green]"
            )
        else:
            lr_finished = "-"
            lr_found = "-"
            lr_new = "-"
            lr_err = "-"

        failed_24h_str = (
            f"[red]{item['failed_24h']}[/red]" if item["failed_24h"] > 0 else "[green]0[/green]"
        )
        if item.get("last_error"):
            time_suffix = (
                f" [dim]({item['last_error_time']})[/dim]" if item.get("last_error_time") else ""
            )
            last_error_str = f"[red]{item['last_error']}[/red]{time_suffix}"
        else:
            last_error_str = "[green]None[/green]"

        plat_table.add_row(
            p_name,
            gig_count,
            status,
            lr_finished,
            lr_found,
            lr_new,
            lr_err,
            failed_24h_str,
            last_error_str,
        )

    console.print(plat_table)
    console.print()

    platforms_with_errors = [item for item in details if item.get("last_error")]
    if platforms_with_errors:
        console.print("[bold yellow]Last Platform Errors:[/bold yellow]")
        for item in platforms_with_errors:
            time_tag = f" at {item['last_error_time']}" if item.get("last_error_time") else ""
            console.print(
                f"  • [cyan]{item['name']}[/cyan]{time_tag}: [red]{item['last_error']}[/red]"
            )
        console.print()


# ------------------------------------------------------------------------------
# Scheduler Command: gigradar run [--once]
# ------------------------------------------------------------------------------
@app.command(name="run")
def run_cmd(
    once: bool = typer.Option(
        False,
        "--once",
        help="Run a single polling tick across all enabled platforms and exit.",
    ),
) -> None:
    """Run the GigRadar background scheduler or execute a single tick (--once)."""
    import asyncio

    from gigradar.pipeline.scheduler import SchedulerRunner

    settings = get_settings()
    setup_logging(log_level=settings.log_level, log_format=settings.log_format)

    runner = SchedulerRunner()

    if once:
        console.print(
            "\n[bold cyan]Executing single polling tick for all enabled platforms...[/bold cyan]\n"
        )
        try:
            results = asyncio.run(runner.run_once())
        except Exception as exc:
            console.print(f"[bold red]Tick execution failed:[/bold red] {exc}")
            raise typer.Exit(code=1) from None

        table = Table(title="Polling Tick Summary", show_header=True, header_style="bold magenta")
        table.add_column("Platform", style="cyan")
        table.add_column("Status", style="bold")
        table.add_column("Found", justify="right")
        table.add_column("New Gigs", justify="right")
        table.add_column("Details")

        for plat, res in results.items():
            if res.paused:
                status_str = "[yellow]PAUSED[/yellow]"
                details_text = res.error or "In cooldown"
            elif res.success:
                status_str = "[green]SUCCESS[/green]"
                details_text = "Completed normally"
            else:
                status_str = "[red]FAILED[/red]"
                details_text = res.error or "Error during tick"

            table.add_row(plat, status_str, str(res.gigs_found), str(res.gigs_new), details_text)

        console.print(table)
        console.print()
        return

    console.print(
        "\n[bold green]Starting GigRadar scheduler in foreground. Press Ctrl+C to stop.[/bold green]\n"
    )
    try:
        asyncio.run(runner.run_forever())
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutdown requested by user (Ctrl+C). Exiting cleanly.[/yellow]\n")


# ------------------------------------------------------------------------------
# Phase 3: Stage 1 Rules Classification & Reporting CLI
# ------------------------------------------------------------------------------
@app.command(name="classify-stored")
def classify_stored(
    platform: str | None = typer.Option(
        None,
        "--platform",
        "-p",
        help="Filter stored gigs by platform name (mostaql, khamsat, freelancer).",
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        "-l",
        help="Maximum number of stored gigs to classify.",
    ),
    reclassify: bool = typer.Option(
        False,
        "--reclassify",
        help="Reclassify previously classified gigs (appends new classification, stale gigs skipped).",
    ),
) -> None:
    """Replay Stage 1 rules filter over stored gigs and print pass/reject with reasons."""
    import asyncio

    from gigradar.classify.rules_filter import RulesFilter
    from gigradar.db.repositories.gig_repo import GigRepository
    from gigradar.db.repositories.platform_repo import PlatformRepository
    from gigradar.db.session import get_async_session

    async def _run() -> None:
        rules_filter = RulesFilter()
        console.print(
            f"\n[bold cyan]Stage 1 Rules Classifier[/bold cyan] (rules_version=[green]{rules_filter.rules_version}[/green])\n"
        )

        async with get_async_session() as session:
            gig_repo = GigRepository(session)
            platform_repo = PlatformRepository(session)

            plat_id: int | None = None
            if platform:
                norm_plat = platform.strip().lower()
                plat_obj = await platform_repo.get_by_name(norm_plat)
                if plat_obj is None:
                    console.print(
                        f"[bold red]Platform '{platform}' not found in database.[/bold red]"
                    )
                    raise typer.Exit(code=1)
                plat_id = plat_obj.id

            gigs = await gig_repo.get_gigs_for_rules_classification(
                platform_id=plat_id,
                limit=limit,
                reclassify=reclassify,
            )

            if not gigs:
                console.print(
                    "[yellow]No gigs found matching criteria. Use --reclassify to replay all non-stale gigs.[/yellow]\n"
                )
                return

            console.print(f"Evaluating [bold]{len(gigs)}[/bold] stored gig(s)...\n")

            passed_count = 0
            rejected_count = 0

            for gig in gigs:
                plat_name = gig.platform.name if gig.platform else "default"
                res = rules_filter.evaluate(gig, platform_name=plat_name)

                await gig_repo.record_classification(
                    gig_id=gig.id,
                    stage="rules",
                    passed=res.passed,
                    rule_hits=res.hits,
                    reject_reason=res.reject_reason,
                    flags=res.flags,
                    rules_version=rules_filter.rules_version,
                )

                title_snippet = (gig.title[:60] + "...") if len(gig.title) > 60 else gig.title
                if res.passed:
                    passed_count += 1
                    status_badge = "[bold green]PASS[/bold green]"
                    details = ", ".join(res.hits[:3])
                else:
                    rejected_count += 1
                    status_badge = "[bold red]REJECT[/bold red]"
                    details = res.reject_reason or "unknown"

                console.print(
                    f"{status_badge} [{plat_name}] [cyan]#{gig.external_id}[/cyan] {title_snippet} -> [dim]{details}[/dim]"
                )

            await session.commit()

            console.print(
                f"\n[bold]Classification Complete:[/bold] Total: {len(gigs)} | "
                f"[green]Passed: {passed_count}[/green] | "
                f"[red]Rejected: {rejected_count}[/red]\n"
            )

    asyncio.run(_run())


@app.command(name="rules-report")
def rules_report() -> None:
    """Print counts by reject reason per platform, pass rate, passes/24h estimate, sample of 30 rejected titles, and ALL passed titles."""
    import asyncio
    import random
    from collections import Counter

    from gigradar.db.repositories.gig_repo import GigRepository
    from gigradar.db.session import get_async_session

    async def _run() -> None:
        async with get_async_session() as session:
            gig_repo = GigRepository(session)
            classified_pairs = await gig_repo.get_all_classified_gigs()

        if not classified_pairs:
            console.print(
                "\n[yellow]No classified gigs found. Run 'gigradar classify-stored --reclassify' first.[/yellow]\n"
            )
            return

        total_gigs = len(classified_pairs)
        passed_pairs = [(g, c) for g, c in classified_pairs if c.passed]
        rejected_pairs = [(g, c) for g, c in classified_pairs if not c.passed]

        # Per platform stats
        platform_counts: dict[str, dict[str, int]] = {}
        reject_reasons_per_platform: dict[str, Counter[str]] = {}
        all_reject_reasons: Counter[str] = Counter()

        earliest_time: datetime | None = None
        latest_time: datetime | None = None

        for gig, classification in classified_pairs:
            p_name = gig.platform.name if gig.platform else "default"
            if p_name not in platform_counts:
                platform_counts[p_name] = {"total": 0, "passed": 0, "rejected": 0}
                reject_reasons_per_platform[p_name] = Counter()

            platform_counts[p_name]["total"] += 1
            if classification.passed:
                platform_counts[p_name]["passed"] += 1
            else:
                platform_counts[p_name]["rejected"] += 1
                reason = classification.reject_reason or "unknown"
                reject_reasons_per_platform[p_name][reason] += 1
                all_reject_reasons[reason] += 1

            # Time span calculation
            time_ref = gig.posted_at or gig.first_seen_at
            if time_ref is not None:
                if earliest_time is None or time_ref < earliest_time:
                    earliest_time = time_ref
                if latest_time is None or time_ref > latest_time:
                    latest_time = time_ref

        # Time span & passes per 24 hours estimate
        hours_span = 24.0
        if earliest_time and latest_time:
            delta_seconds = max(60.0, (latest_time - earliest_time).total_seconds())
            hours_span = max(1.0, delta_seconds / 3600.0)

        passes_per_24h = (len(passed_pairs) / hours_span) * 24.0

        console.print("\n[bold cyan]=== Stage 1 Rules Classification Report ===[/bold cyan]\n")
        console.print(
            f"Total stored classified gigs: [bold]{total_gigs}[/bold] "
            f"(Passed: [bold green]{len(passed_pairs)}[/bold green], "
            f"Rejected: [bold red]{len(rejected_pairs)}[/bold red], "
            f"Pass Rate: [bold cyan]{(len(passed_pairs) / total_gigs * 100):.1f}%[/bold cyan])"
        )
        console.print(
            f"Time span covered: [bold]{hours_span:.1f} hours[/bold] | "
            f"Estimated passes / 24h: [bold green]{passes_per_24h:.1f}[/bold green]\n"
        )

        # Platform summary table
        plat_table = Table(
            title="Platform Pass / Reject Rates", show_header=True, header_style="bold magenta"
        )
        plat_table.add_column("Platform", style="cyan")
        plat_table.add_column("Total Gigs", justify="right")
        plat_table.add_column("Passed", justify="right", style="green")
        plat_table.add_column("Rejected", justify="right", style="red")
        plat_table.add_column("Pass Rate", justify="right", style="bold")

        for p_name, counts in sorted(platform_counts.items()):
            rate = (counts["passed"] / counts["total"] * 100) if counts["total"] > 0 else 0.0
            plat_table.add_row(
                p_name,
                str(counts["total"]),
                str(counts["passed"]),
                str(counts["rejected"]),
                f"{rate:.1f}%",
            )
        console.print(plat_table)
        console.print()

        # Top 10 Reject Reasons Overall
        top_reject_table = Table(
            title="Top 10 Reject Reasons Overall", show_header=True, header_style="bold magenta"
        )
        top_reject_table.add_column("Reject Reason", style="yellow")
        top_reject_table.add_column("Count", justify="right")
        top_reject_table.add_column("% of Rejects", justify="right")

        for reason, count in all_reject_reasons.most_common(10):
            pct = (count / len(rejected_pairs) * 100) if rejected_pairs else 0.0
            top_reject_table.add_row(reason, str(count), f"{pct:.1f}%")
        console.print(top_reject_table)
        console.print()

        # Sample of up to 30 random rejected titles
        sample_size = min(30, len(rejected_pairs))
        sampled_rejected = (
            random.sample(rejected_pairs, sample_size)
            if len(rejected_pairs) > sample_size
            else rejected_pairs
        )
        sample_table = Table(
            title=f"Sample of {sample_size} Rejected Gigs",
            show_header=True,
            header_style="bold magenta",
        )
        sample_table.add_column("Platform", style="cyan", width=12)
        sample_table.add_column("Title", style="white", width=55)
        sample_table.add_column("Main Reject Reason", style="red")

        for gig, classification in sampled_rejected:
            p_name = gig.platform.name if gig.platform else "default"
            t_short = (gig.title[:52] + "...") if len(gig.title) > 52 else gig.title
            sample_table.add_row(p_name, t_short, classification.reject_reason or "unknown")
        console.print(sample_table)
        console.print()

        # ALL Passed Titles
        passed_table = Table(
            title=f"ALL Passed Gigs ({len(passed_pairs)} total)",
            show_header=True,
            header_style="bold magenta",
        )
        passed_table.add_column("Platform", style="cyan", width=12)
        passed_table.add_column("Budget", style="yellow", width=14)
        passed_table.add_column("Title", style="green", width=50)
        passed_table.add_column("Key Hits", style="dim")

        for gig, classification in passed_pairs:
            p_name = gig.platform.name if gig.platform else "default"
            b_str = (
                f"${gig.budget_max_usd:.0f}"
                if gig.budget_max_usd is not None
                else (f"${gig.budget_usd_est:.0f}" if gig.budget_usd_est is not None else "N/A")
            )
            t_short = (gig.title[:47] + "...") if len(gig.title) > 47 else gig.title
            hits = classification.rule_hits_json or []
            # filter for informative include hits
            inc_hits = [h for h in hits if h.startswith("include:") or h.startswith("ambiguous:")]
            inc_text = ", ".join(inc_hits[:3]) if inc_hits else ", ".join(hits[:2])
            passed_table.add_row(p_name, b_str, t_short, inc_text)
        console.print(passed_table)
        console.print()

    asyncio.run(_run())


@app.command(name="explain-gig")
def explain_gig(
    platform: str = typer.Argument(..., help="Platform name (mostaql, khamsat, freelancer)."),
    external_id: str = typer.Argument(..., help="External ID of the gig."),
) -> None:
    """Print complete rules filter evaluation and explanation for a single stored gig."""
    import asyncio

    from gigradar.classify.rules_filter import RulesFilter
    from gigradar.db.repositories.gig_repo import GigRepository
    from gigradar.db.repositories.platform_repo import PlatformRepository
    from gigradar.db.session import get_async_session

    async def _run() -> None:
        rules_filter = RulesFilter()
        async with get_async_session() as session:
            gig_repo = GigRepository(session)
            platform_repo = PlatformRepository(session)

            norm_plat = platform.strip().lower()
            plat_obj = await platform_repo.get_by_name(norm_plat)
            if plat_obj is None:
                console.print(f"[bold red]Platform '{platform}' not found in database.[/bold red]")
                raise typer.Exit(code=1)

            gig = await gig_repo.get_by_external_id(plat_obj.id, external_id.strip())
            if gig is None:
                console.print(
                    f"[bold red]Gig with external_id '{external_id}' not found on platform '{platform}'.[/bold red]"
                )
                raise typer.Exit(code=1)

            latest_cls = await gig_repo.get_latest_classification(gig.id, stage="rules")

            # Run deterministic evaluation
            res = rules_filter.evaluate(gig, platform_name=norm_plat)

        console.print("\n[bold cyan]=== Gig Rules Explanation ===[/bold cyan]\n")
        console.print(
            f"[bold]Platform:[/bold] {norm_plat} | [bold]External ID:[/bold] {gig.external_id}"
        )
        console.print(f"[bold]Title:[/bold] {gig.title}")
        console.print(f"[bold]URL:[/bold] {gig.url}")
        console.print(
            f"[bold]Detail Level:[/bold] {gig.detail_level} | [bold]Processing State:[/bold] {gig.processing_state}"
        )

        # Budget info
        b_max = gig.budget_max_usd or gig.budget_usd_est
        b_str = f"${b_max:.2f}" if b_max is not None else "Unknown"
        console.print(
            f"[bold]Project Type:[/bold] {gig.project_type} | [bold]Budget Max USD:[/bold] {b_str} "
            f"(Raw: {gig.budget_min}-{gig.budget_max} {gig.currency or ''})"
        )
        console.print(
            f"[bold]Bids Count:[/bold] {gig.bids_count} | [bold]Posted At:[/bold] {gig.posted_at}"
        )
        console.print(f"[bold]Category:[/bold] {gig.category_raw or 'None'}")
        if gig.tags_raw_json:
            console.print(f"[bold]Tags:[/bold] {', '.join(gig.tags_raw_json)}")

        console.print("\n[bold]Current Evaluation Result:[/bold]")
        if res.passed:
            console.print("[bold green]✔ PASSED Stage 1 Rules Filter[/bold green]")
        else:
            console.print(
                f"[bold red]✘ REJECTED[/bold red] - Reason: [yellow]{res.reject_reason}[/yellow]"
            )

        if res.flags:
            console.print(
                f"[bold cyan]Flags / Hints for Stage 2:[/bold cyan] {', '.join(res.flags)}"
            )

        console.print("\n[bold]Recorded Rule Hits:[/bold]")
        for h in res.hits:
            if h.startswith("hard_reject:"):
                console.print(f"  • [red]{h}[/red]")
            elif h.startswith("include:"):
                console.print(f"  • [green]{h}[/green]")
            elif h.startswith("ambiguous:"):
                console.print(f"  • [yellow]{h}[/yellow]")
            elif "ok" in h:
                console.print(f"  • [cyan]{h}[/cyan]")
            else:
                console.print(f"  • {h}")

        if latest_cls is not None:
            console.print("\n[bold]Latest Database Classification Record:[/bold]")
            console.print(
                f"  Stage: {latest_cls.stage} | Passed: {latest_cls.passed} | "
                f"Rules Version: {latest_cls.rules_version} | "
                f"Classified At: {latest_cls.created_at}"
            )
        console.print()

    asyncio.run(_run())


if __name__ == "__main__":
    app()
