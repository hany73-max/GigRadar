# GigRadar: Progress Log & Project Memory

This document is the single source of truth for the project's current state, decisions, known issues, and phase checkpoint reports.

---

## Current Status Overview

- **Current Phase:** Phase 2.5a: Reliability hardening (COMPLETED)
- **Next Phase:** Phase 3: Rules filter
- **Overall System Health:** Green (All 152 unit tests passing, `ruff` clean, `mypy --strict` clean on 55 source files, 0 warnings with `-W error`, `scripts/check.ps1` passing, `gigradar doctor [--offline]`, `gigradar db upgrade`, `gigradar db stats`, `gigradar run [--once]` operational)

---

## Carry-Forward Notes

- **Phase 3 (Hourly & Fixed Range Thresholds):** The rules filter must compare hourly projects against a separate `min_hourly_rate_usd` (add to config), and use `budget_max_usd` for the minimum-budget check on fixed ranges.
- **Phase 3 (Freelancer Saturation Strategy):** Freelancer projects fill with bids rapidly, so the rules filter should prefer gigs with few bids and a recent `posted_at`.
- **Phases 3 & 5 (Khamsat Detail Level):** `detail_level` field (`full | title_only`) is now present on `Gig`/`gigs` table; make the rules filter and the scorer prompt aware that the description is missing for Khamsat.
- **Phase 6 (Pitch Validation):** Replace the vocabulary regex ban with claim-based validation (comparing pitch factual statements against `claims_allowlist.yaml` and retrieved portfolio items via LLM judge, rather than naive regex keyword matching).

---

## Phase History

### Phase 0: Foundation (Completed)

#### 1. What was built
- **Repository Scaffold & Tooling:**
  - `pyproject.toml`: Modern packaging with `uv`, pinning dependencies (`pydantic`, `pydantic-settings`, `pyyaml`, `typer`, `structlog`, `rich`, `google-genai>=0.1.1` [v2.31.0], `sqlalchemy`, `httpx`, `tenacity`) and strict dev tooling (`ruff`, `mypy`, `pytest`, `pytest-asyncio`).
  - `.gitignore` & `.env.example`: Comprehensive git ignore and documented environment configuration with placeholders. Defaults set to `LLM_MAX_RPM=10` and `LLM_DAILY_CALL_BUDGET=200`.
  - `README.md`: Quickstart instructions.
  - `scripts/check.ps1` & `scripts/check.sh`: One-command CI-style verification runner (`ruff` + `mypy` + `pytest`).
  - `scripts/test_structured_output.py`: Live structured output validation script.
- **Configuration & Validation Layer:**
  - `config/profile.yaml`: Owner profile (Hany Elashry), skill tiers (A, B, C describing work to ACCEPT), and hard rejects.
  - `config/portfolio.yaml`: Seeded with 5 technical projects (Sky-Spy, Kessler-Shield, TicketSense, The ML Blueprint, FMCW Radar) tagged for retrieval.
  - `config/claims_allowlist.yaml`: Strictly traces to Hany's CV only (what pitches may CLAIM). Web scraping phrased at coursework level (DEPI track), CFAR radar detection noted as in progress. Honest PyTorch/CNN line preserved.
  - `config/rules.yaml`: Stage 1 deterministic rules (keyword families in Arabic & English, budget/bid/age thresholds, hard rejects, category lists).
  - `config/platforms.yaml`: Platform configurations for Mostaql, Khamsat, and Freelancer.com.
  - `src/gigradar/core/config_models.py`: Pydantic v2 schemas validating each YAML file.
  - `src/gigradar/core/config_loader.py`: Safe loaders and `validate_all_configs()`.
- **Core Architecture & Verifier:**
  - `src/gigradar/core/settings.py`: Pydantic `BaseSettings` reading environment and `.env`. Conservative defaults: `LLM_MAX_RPM=10`, `LLM_DAILY_CALL_BUDGET=200`.
  - `src/gigradar/core/logging.py`: Structured logging (`structlog`) with console formatting and JSON capability.
  - `src/gigradar/core/gemini_verifier.py`: Verification utility testing live connectivity to Gemini API via `google-genai` SDK with credential masking and placeholder detection.
- **CLI & Diagnostic System:**
  - `src/gigradar/cli.py`: Typer CLI entrypoint with `gigradar doctor` command inspecting configuration files, environment variables, database syntax, placeholder detection, and live Gemini API connectivity.
- **Documentation & Research:**
  - `docs/LLM_NOTES.md`: Documents Gemini integration, SDK usage, and structured outputs. All unverified figures (10 RPM / 250 RPD free tier, pricing, etc.) marked explicitly as UNVERIFIED pending live confirmation via `client.models.list()`. Removed unverified 10-minute spend caps and unconfirmed model claims.
  - `docs/MASTER_PROMPT.md`: Canonical specification maintained in `docs/` (root duplicate deleted).
- **Test Suite:**
  - `tests/test_config.py`: Validates all 5 YAML files and schema edge cases.
  - `tests/test_settings.py`: Tests default settings (`LLM_MAX_RPM=10`, `LLM_DAILY_CALL_BUDGET=200`) and environment variable overrides.
  - `tests/test_gemini_verifier.py`: Tests API key masking, placeholder detection (`is_placeholder`), and connectivity validation.
  - `tests/test_cli.py`: Tests `--version`, `doctor --skip-live-llm`, and placeholder reporting.

#### 2. How to run / verify it
```bash
# 1. Run all code quality & test checks:
powershell -ExecutionPolicy Bypass -File scripts/check.ps1
# or individually:
uv run ruff check .
uv run mypy src tests
uv run pytest

# 2. Run system diagnostics:
uv run gigradar doctor

# 3. Test live structured outputs (when real GEMINI_API_KEY is configured in .env):
uv run python scripts/test_structured_output.py
```

#### 3. Test results
- **Pytest:** 18 passed in 1.83s (0 warnings).
- **Ruff:** All checks passed (clean lint and imports).
- **Mypy:** Success: no issues found in 12 source files (`--strict` mode).

#### 4. Decisions made and why
- **Conservative LLM Defaults:** Set `LLM_MAX_RPM=10` and `LLM_DAILY_CALL_BUDGET=200` as safe defaults until limits are confirmed with a live key.
- **Strict Claims Allowlist:** Phrased web scraping as coursework-level ("web scraping and ETL fundamentals from the DEPI data engineering track") and marked CFAR radar detection stage as in progress.
- **Unverified Stamps Cleanup:** Stripped unsubstantiated "VERIFIED" tags from `docs/LLM_NOTES.md`; clearly marked estimates as UNVERIFIED.

#### 5. Known issues / risks
- None. System is fully operational and green. Placeholders in `.env` are safely detected without crashing diagnostics.

#### 6. Questions for owner
- None at this stage.

#### 7. Proposed next phase and inputs needed
- **Phase 1: Platform discovery and parsers (Mostaql & Khamsat)**
- *Inputs needed:* A browser discovery pass on Mostaql (`https://mostaql.com/projects`) and Khamsat (`https://khamsat.com/community/requests`) to inspect real DOM structure, extract sample fixtures into `tests/fixtures/html/`, and record findings in `docs/PLATFORM_NOTES.md`.

#### 8. Handoff note
Phase 0 foundation is complete and refined. Defaults are set conservatively (`LLM_MAX_RPM=10`, `LLM_DAILY_CALL_BUDGET=200`), claims strictly match CV facts, `docs/LLM_NOTES.md` cleanly separates verified SDK mechanics from unverified quotas, and a carry-forward note is recorded for Phase 6. All 18 tests pass. Ready for **Phase 1**.

### Phase 1: Platform Discovery and Parsers — Mostaql & Khamsat (Completed)

#### 1. What was built
- **Platform Discovery & Documentation:**
  - `docs/PLATFORM_NOTES.md`: Comprehensive technical profile for both Mostaql and Khamsat including: robots.txt analysis, ToS findings, URL structures, pagination patterns, rendering model (SSR confirmed for both), anti-bot protections encountered, DOM selectors for listing and detail pages, and shared normalization requirements.
- **Core Domain Models:**
  - `src/gigradar/core/models.py`: `GigStub` (lightweight listing entry), `Gig` (full project with budget/client/tags/language), `HealthReport` (layout drift detection) — all Pydantic v2 `BaseModel` classes.
- **Platform Client Interface:**
  - `src/gigradar/platforms/base.py`: `PlatformClient` protocol (runtime-checkable) defining `list_new_gigs()`, `fetch_gig_detail()`, `health_check()`.
  - `src/gigradar/platforms/__init__.py`: Re-exports `PlatformClient`, `MostaqlClient`, `KhamsatClient`.
- **Shared Infrastructure:**
  - `src/gigradar/platforms/common/http_client.py`: `PoliteHttpClient` with per-platform `RateLimiter` (async lock + jitter), exponential backoff via `tenacity`, `Retry-After` header parsing (integer seconds + HTTP-date), retryable status code detection (429/500/502/503/504).
  - `src/gigradar/platforms/common/normalization.py`: Arabic-Indic → ASCII digit translation, relative Arabic time parsing (دقيقة/ساعة/يوم/شهر/سنة with dual/plural forms, compound expressions like "8 ساعات و5 دقائق"), machine-readable datetime parsing (Mostaql `YYYY-MM-DD HH:MM:SS` and Khamsat `DD/MM/YYYY HH:MM:SS GMT`), budget range extraction with currency detection (USD/SAR/EGP), bid count parsing (including "أضف أول عرض" = 0, "عرض واحد" = 1, "عرضين" = 2), language detection (Arabic/English/mixed by character ratio).
- **Mostaql Parser & Client:**
  - `src/gigradar/platforms/mostaql/parser.py`: `parse_mostaql_listing()` (table rows → `GigStub` list), `parse_mostaql_detail()` (detail page → `Gig` with budget, tags, client stats, deadline, category, description hash).
  - `src/gigradar/platforms/mostaql/client.py`: `MostaqlClient` implementing `PlatformClient` with paginated listing, detail fetching, health checks, configurable page limits, proper cleanup.
- **Khamsat Parser & Client:**
  - `src/gigradar/platforms/khamsat/parser.py`: `parse_khamsat_listing()` (table rows → `GigStub` list), `parse_khamsat_gig_from_stub()` (stub → `Gig` without detail fetch; detail-only fields remain `None`).
  - `src/gigradar/platforms/khamsat/client.py`: `KhamsatClient` implementing `PlatformClient` with paginated listing, stub-to-gig conversion (no detail fetch), health checks.
- **HTML Fixtures (sanitized):**
  - `tests/fixtures/html/mostaql_listing.html`: Real sanitized listing page (25 project rows).
  - `tests/fixtures/html/mostaql_detail.html`: Real sanitized detail page (project 1286262).
  - `tests/fixtures/html/khamsat_listing.html`: Real sanitized listing page (25 request rows).
- **CLI Extension:**
  - `src/gigradar/cli.py`: Added `gigradar scrape-once <mostaql|khamsat>` command with `--limit` and `--fetch-details/--no-details` flags, Rich table output. UTF-8 console reconfiguration for Arabic text on Windows.
- **Test Suite (75 new tests, 93 total):**
  - `tests/test_normalization.py`: 48 parametrized tests for digit normalization, relative Arabic time (seconds, minutes, hours, days, weeks, months, years, compound phrases, ValueError on unrecognized/empty text), machine-readable datetime fallback, budget ranges, bid counts, language detection.
  - `tests/test_parsers.py`: 4 tests against real HTML fixtures (Mostaql listing, Mostaql detail with category and skill tags assertion, Khamsat listing asserting bids_count is None, error handling).
  - `tests/test_http_client.py`: 6 tests for rate limiter (spacing, skipping jitter on first request and after idle period), retry-after parsing, mock HTTP success, 503 retry recovery.
  - `tests/test_platform_clients.py`: 4 tests for protocol conformance, mock listing+detail flow (Mostaql/Khamsat), health check failure handling.
  - `tests/test_cli.py`: 3 tests for `scrape-once` (unsupported platform, mocked successful scrape, rendering '-' for None bids_count).
- **Dependencies Added:**
  - `beautifulsoup4>=4.12.0` and `lxml>=5.2.0` in `pyproject.toml` (no Playwright).
  - `types-beautifulsoup4>=4.12.0` in dev dependencies for mypy.

#### 2. How to run / verify it
```bash
# Full verification:
uv run ruff check .
uv run mypy src tests
uv run pytest -v

# Live scraping (hits real platforms, be polite):
uv run gigradar scrape-once mostaql --limit 3
uv run gigradar scrape-once khamsat --limit 3

# Scraping without detail fetch (listing only):
uv run gigradar scrape-once mostaql --limit 5 --no-details
```

#### 3. Test results
- **Pytest:** 93 passed in 13.89s (0 warnings).
- **Ruff:** All checks passed (clean lint and imports).
- **Mypy:** Success: no issues found in 28 source files (`--strict` mode).

#### 4. Decisions made and why
- **No Playwright / No WAF bypass:** Khamsat detail pages return HTTP 202 with AWS WAF JS challenge. Per project safety rules and anti-bot policy, we do NOT use browser automation. Khamsat is parsed from listing pages only; detail-only fields (extended description, thread replies) stay `None`. This is documented in `docs/PLATFORM_NOTES.md` section 2.3.
- **Pure-function parsers:** All HTML parsing is in pure functions (`parse_mostaql_listing`, `parse_mostaql_detail`, `parse_khamsat_listing`) that take raw HTML strings and return typed Pydantic models. Zero network calls inside parsers — fully unit-testable against fixtures.
- **Dual timestamp strategy:** Both Mostaql (`<time datetime="...">`) and Khamsat (`<span title="DD/MM/YYYY HH:MM:SS GMT">`) provide machine-readable timestamps alongside Arabic relative text. The parser tries machine-readable first, falls back to relative Arabic parsing.
- **Strict Relative Time Parsing:** `parse_relative_arabic_time` supports seconds (`ثانية`/`ثواني`), minutes, hours, days, weeks (`أسبوع`/`أسبوعين`/`أسابيع`), months, years, and compound phrases. Unrecognized text or empty strings raise `ValueError` (never falling back to "now"). Callers like `parse_datetime_or_relative` catch `ValueError` and safely return `None`.
- **PoliteHttpClient & RateLimiter Idle Skip:** Rate limiter uses async lock for concurrency safety, jitter is configurable per-platform via `platforms.yaml`, retries use tenacity with exponential backoff, and `Retry-After` headers are honored. Crucially, the rate limiter does **not** inject jitter delay on the first request or requests made after an idle period (`elapsed >= idle_threshold`), while preserving the full minimum interval plus jitter between consecutive requests.
- **Khamsat bids_count as None:** Khamsat listing rows expose no offers/bids count, so `GigStub.bids_count` and `Gig.bids_count` are typed as `int | None = None` and parsed as `None` for Khamsat. The CLI table renders unknown bids count cleanly as `-`.
- **Sanitized fixtures:** All HTML fixtures have personal names (buyer, client, responder, bidder names) replaced with generic placeholders (`User A`, etc.), while preserving non-personal metadata (category names, skill tags, project titles) and DOM structure intact. Tag deduplication in the detail parser ensures clean unique tags.

#### 5. Known issues / risks
- **Khamsat detail pages inaccessible:** By design (AWS WAF). Budget, extended description, and tags from Khamsat are `None`. This is acceptable for Phase 1; if detail data becomes needed, a logged-in session cookie approach could be explored in a future phase.
- **Layout drift risk:** Both platforms could change their HTML structure at any time. The `health_check()` method on each client validates that the listing page still parses correctly, and the `gigradar doctor` can be extended to run these checks.

#### 6. Questions for owner
- None at this stage. Phase 1 acceptance criteria and refinements are met: both `scrape-once` commands work, parser tests pass against sanitized fixtures with category/skills assertions, rate limiter starts immediately on first/idle request, and `docs/PLATFORM_NOTES.md` documents all findings.

#### 7. Proposed next phase and inputs needed
- **Phase 1b: Freelancer.com via official API** (per section 6.1b and section 9 of master prompt).
- *Inputs needed:* Freelancer.com OAuth credentials (or decision to skip Phase 1b and proceed to Phase 2: Storage, dedupe, scheduling).

#### 8. Handoff note
Phase 1 is complete and refined. Mostaql listing+detail and Khamsat listing-only parsers work against real HTML, backed by 93 tests (all green). No Playwright in the project. `PoliteHttpClient` handles rate limiting, jitter, retries, and `Retry-After`, with zero delay on first/idle requests. The `PlatformClient` protocol is established and both `MostaqlClient` and `KhamsatClient` conform to it. Fixtures are fully sanitized of personal data while preserving categories and skills. Ready for **Phase 1b** (Freelancer.com API) or **Phase 2** (Storage & scheduling).

### Phase 1b: Freelancer.com via Official API (Completed)

#### 1. What was built
- **Official API Discovery & Documentation:**
  - `docs/PLATFORM_NOTES.md` (Section 4): Documented Freelancer official REST API (`https://www.freelancer.com/api/projects/0.1/`), active projects search endpoint (`/projects/0.1/projects/active/`), skills directory (`/projects/0.1/jobs/`), currencies directory (`/projects/0.1/currencies/`), rate limits (~100 req/min), auth model (unauthenticated active search verified), and terms of service. Cited official developer URLs (`https://developers.freelancer.com/`).
  - Discovered and cataloged verified skill IDs: Python (13), Machine Learning (292), Deep Learning (1601), Data Science (761), NLP (2833), Computer Vision (1558), Web Scraping (95), SQL (68), Data Processing (36), Data Mining (334).
- **Domain Model Extension:**
  - `src/gigradar/core/models.py`: Added `project_type: Literal["fixed", "hourly"] = "fixed"` to `Gig` domain model for clean handling of hourly project ranges without mixing with fixed prices.
- **Pure-Function Parser:**
  - `src/gigradar/platforms/freelancer/parser.py`: Pure functions `parse_freelancer_project()` (`json -> Gig`), `parse_freelancer_stub()` (`json -> GigStub`), `parse_freelancer_active_response()`, and `is_excluded_project()` checking safety/filtering rules (contests, NDA, local jobs, recruiter fee listings).
  - Native USD normalization: Computes `budget_usd_est` using live exchange rates directly exposed in each project's `currency.exchange_rate` object. Hourly projects stored as hourly ranges with unit-safe rate estimation.
- **Platform Client Implementation:**
  - `src/gigradar/platforms/freelancer/client.py`: `FreelancerClient` implementing `PlatformClient` protocol via `PoliteHttpClient` using only `httpx` (no browser automation). Server-side filtering by skill IDs, sorting newest first (`sort_field=time_updated`, `reverse_sort=true`), deduplication across queries by project ID, in-memory detail cache avoiding duplicate network requests, and health check validation.
  - `src/gigradar/platforms/freelancer/__init__.py` and `src/gigradar/platforms/__init__.py`: Exporting `FreelancerClient`.
- **Platform Configuration:**
  - `config/platforms.yaml`: Verified platform-specific thresholds: `max_existing_bids: 40`, `min_budget_usd: 30.0`, `max_gig_age_minutes: 360` (6h), and `poll_interval_seconds: 120`.
- **Sanitized JSON Fixtures:**
  - `tests/fixtures/json/freelancer_projects.json`: Sanitized real multi-project API envelope (8 projects) with client names, usernames, and emails stripped while preserving non-personal project titles, budgets, currencies, bid counts, timestamps, and safety upgrade flags.
  - `tests/fixtures/json/freelancer_single_project.json`: Sanitized single project detail fixture.
- **CLI Command Extension:**
  - `src/gigradar/cli.py`: Wired `gigradar scrape-once freelancer --limit N` rendering parsed projects with original budget, estimated USD amounts, UTC timestamps, bid counts, and language.
- **Test Suite (14 new tests, 107 total):**
  - `tests/test_freelancer_parser.py`: 5 tests validating single project parsing, stub parsing, active envelope parsing, hourly project handling, exclusion rules (NDA, local, recruiter, contests, closed), and error cases.
  - `tests/test_normalization.py`: Added 6 parametrized tests for `format_budget_display` handling fixed dual-currency ranges, hourly ranges, and missing budgets.
  - `tests/test_platform_clients.py`: Added 2 tests for protocol conformance, mock listing/detail flow, and health check failure handling.
  - `tests/test_cli.py`: Added 2 tests for `scrape-once freelancer` and `--all` flag.

#### 2. How to run / verify it
```bash
# Full verification:
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pytest -v

# Run the complete verification script:
powershell -ExecutionPolicy Bypass -File scripts/check.ps1

# Live scraping against Freelancer official API with default age filter (newest gigs within max_gig_age_minutes):
uv run gigradar scrape-once freelancer --limit 5

# Live scraping without age filter:
uv run gigradar scrape-once freelancer --limit 5 --all
```

#### 3. Test results
- **Pytest:** 107 passed in 4.93s (0 warnings).
- **Ruff:** All checks passed (clean lint and format).
- **Mypy:** Success: no issues found in 32 source files (`--strict` mode).

#### 4. Decisions made and why
- **Unauthenticated Active Project Search:** Discovery confirmed that `GET /projects/0.1/projects/active/` returns HTTP 200 without OAuth tokens. However, client details (`owner_id`, `owner_info`, buyer KYC, location) are hidden (`None`) by Freelancer unless authenticated. This satisfies Phase 1b read-only requirements cleanly without needing an OAuth app.
- **Freshness & Sorting Mechanics (`time_updated` + `from_time`):** Probing the API confirmed that `sort_field=submitdate` is an unaccepted parameter that falls back to default sorting. Furthermore, `reverse_sort=true` reverses `time_updated` from descending (newest first) to ascending (oldest first, e.g. 2022-2025 projects). Descending `time_updated` order combined with server-side `from_time = now - max_gig_age_minutes` returns verified fresh gigs posted within minutes/hours.
- **Status Filter on Active Projects:** Checked official Freelancer documentation; no query parameter exists for project status on the `/projects/0.1/projects/active/` endpoint. Local filtering of `status != "active"` is retained.
- **Dual-Currency Budget Normalization & Display:** Added `budget_min_usd` and `budget_max_usd` to `Gig`. For fixed projects, `budget_usd_est` is computed as the midpoint between min and max USD. For hourly projects, `budget_usd_est` is `None` (preserving hourly rate ranges). `format_budget_display()` renders both original and USD estimates (e.g. `GBP 250 - 750 (~$333-$1000)` and `$25-$50/hr`).
- **CLI Default Freshness:** `gigradar scrape-once freelancer` automatically filters by `max_gig_age_minutes` (passing `since` to `list_new_gigs`), reflecting production behavior. An `--all` flag disables this filter.
- **Server-Side + Local Exclusions:** The parser excludes listings flagged as `upgrades.NDA=True`, `local=True`, `upgrades.recruiter=True`, `assisted=True`, or `type="contest"`.
- **Zero-Extra-Network Detail Fetch:** Active project listing queries with `full_description=true` and `job_details=true` already return complete project records; `FreelancerClient` caches these parsed `Gig`s so `fetch_gig_detail(stub)` resolves instantly with zero extra HTTP requests.

#### 5. Known issues / risks
- **Client Metadata Hidden:** As discovered, client stats (ratings, hire rate, payment verification) are unavailable unauthenticated. When OAuth is added in Phase 9 for bidding, authenticated calls can enrich client profile details.
- **High Project Volume:** Freelancer projects receive dozens of bids within minutes. The platform-specific `max_existing_bids: 40` and shorter `max_gig_age_minutes: 360` correctly prevent chasing stale projects.

#### 6. Questions for owner
- None at this stage. All requirements and acceptance criteria for Phase 1b and its refinement fixes are satisfied.

#### 7. Proposed next phase and inputs needed
- **Phase 2: Storage, dedupe, scheduling** (SQLAlchemy models, Alembic migrations, repositories, idempotent upserts, bid-count snapshots, APScheduler background runner with jitter, and circuit breaker).
- *Inputs needed:* None. Can begin Phase 2.

#### 8. Handoff note
Phase 1b and all post-live-run fixes are complete. `FreelancerClient` queries the official Freelancer REST API using `PoliteHttpClient` with server-side skill filtering, verified `from_time` freshness filtering, and local deduplication. The pure-function parser normalizes multicurrency budgets to USD via live API exchange rates with dual-currency display formatting, midpoint estimates for fixed projects, and unit-safe handling of hourly rates. All 107 tests pass, linters and strict mypy are green, and `gigradar scrape-once freelancer --limit 5` surfaces fresh live gigs posted within minutes/hours. Ready for **Phase 2** (Storage, dedupe, scheduling).

### Phase 2: Storage, Deduplication, and Scheduling (Completed)

#### 1. What was built
- **Housekeeping & Configuration:**
  - `config/platforms.yaml`: Extracted Freelancer skill IDs from code into configurable list, removing Data Processing (ID 36). Preserved IDs: 13 (Python), 292 (Machine Learning), 1601 (Deep Learning), 761 (Data Science), 2833 (NLP), 1558 (Computer Vision), 95 (Web Scraping), 68 (SQL), 334 (Data Mining).
  - `src/gigradar/core/config_models.py`: Updated `PlatformSettings` with `skill_ids: list[int] = Field(default_factory=list)`.
  - `src/gigradar/platforms/freelancer/client.py`: Refactored `FreelancerClient` to consume configured `skill_ids`.
- **Database Infrastructure (SQLAlchemy 2.x async + Alembic):**
  - `src/gigradar/db/session.py`: Async engine factory supporting SQLite with WAL mode (`busy_timeout=5000`, `foreign_keys=ON`) and PostgreSQL readiness.
  - `src/gigradar/db/models.py`: Declarative models for `Platform` (scrape state, failure tracking, breaker status), `Gig` (idempotent upsert by `(platform_id, external_id)`, `detail_level`, `processing_state`), `GigSnapshot` (bid count history), and `ScrapeRun` (per-platform audit log). Uses `JSON(none_as_null=True)` for dialect-safe null handling.
  - `alembic.ini` & `src/gigradar/db/migrations/`: Complete async Alembic migration environment (`0001_initial_schema.py`) supporting clean upgrade and downgrade.
  - `src/gigradar/db/helpers.py`: Async utilities for programmatic `run_db_upgrade()`, `run_db_downgrade()`, and `check_db_connectivity_and_version()`.
- **Repositories (Data Access Layer):**
  - `src/gigradar/db/repositories/platform_repo.py`: `PlatformRepository` for registering platforms, tracking consecutive failures, cooldown tripping, and clearing breakers.
  - `src/gigradar/db/repositories/gig_repo.py`: `GigRepository` for idempotent upsert, updating `last_seen_at`, recording snapshots only when `bids_count` changes, and querying pending stubs.
  - `src/gigradar/db/repositories/scrape_run_repo.py`: `ScrapeRunRepository` for logging scrape execution, status, and summary metrics.
- **Pipeline Orchestration & Resilience:**
  - `src/gigradar/pipeline/circuit_breaker.py`: Per-platform circuit breaker tracking consecutive failures in DB (`max_consecutive_failures=3`), pausing platform for cooldown (`15m`), auto-recovering on cooldown expiry, and isolating platform failures.
  - `src/gigradar/pipeline/orchestrator.py`: `PipelineOrchestrator` implementing:
    - Platform deduplication against database.
    - Ingestion age limit: `posted_at` older than `max_gig_age_minutes` stored as stub with `processing_state="stale"`, avoiding detail fetch. Unknown `posted_at` treated as fresh.
    - Detail fetching restricted to new/fresh gigs (`processing_state="new"` -> `"detail_fetched"`).
    - Khamsat out-of-order listing handling (checks entire listing, never stops early on known ID).
    - Freelancer `since` threshold calculation: `max(now - max_gig_age_minutes, last_successful_run_time)`.
    - Crash safety: resumes pending stubs with `processing_state="new"` on subsequent ticks.
  - `src/gigradar/pipeline/scheduler.py`: `SchedulerRunner` with APScheduler `AsyncIOScheduler`, randomized jitter, `coalesce=True`, `max_instances=1`, graceful shutdown on Ctrl+C (SIGINT/SIGTERM), and `--once` execution mode.
- **CLI Commands:**
  - `gigradar db upgrade`: Applies pending Alembic migrations.
  - `gigradar db stats`: Prints summary tables for platforms, gig processing states, and recent scrape runs.
  - `gigradar run [--once]`: Runs the scheduler daemon or a single-tick test across all enabled platforms.
  - `gigradar doctor`: Added database connectivity check and Alembic migration status check (reported as non-fatal warning if migrations are pending).
- **Test Suite (14 new tests, 121 total):**
  - `tests/test_migrations.py`: Tests clean upgrade, downgrade, and re-upgrade of schema #1.
  - `tests/test_repositories.py`: Tests platform upsert, gig idempotent upsert, snapshot creation on bid change, and deduplication.
  - `tests/test_orchestrator.py`: Tests fresh vs stale age filtering (detail fetch only for fresh), deduplication on second run, Khamsat out-of-order handling, and crash safety stub recovery.
  - `tests/test_circuit_breaker.py`: Tests breaker tripping after 3 failures with cooldown, and failure isolation between platforms.
  - `tests/test_cli_db.py`: Tests `gigradar db upgrade`, `gigradar db stats`, and `gigradar doctor` database reporting.

#### 2. How to run / verify it
```bash
# 1. Run all code quality & test checks:
powershell -ExecutionPolicy Bypass -File scripts/check.ps1
# or individually:
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pytest

# 2. Check system diagnostics (database connection and migration status):
uv run gigradar doctor

# 3. Apply database migrations to create tables:
uv run gigradar db upgrade

# 4. View database statistics:
uv run gigradar db stats

# 5. Run a 10-minute live soak test (Ctrl+C to stop cleanly):
uv run gigradar run

# 6. Or run a single scrape cycle across all platforms:
uv run gigradar run --once
```

#### 3. Test results
- **Pytest:** 125 passed, 0 warnings (with `-W error`) in 7.44s.
- **Ruff:** All checks passed (0 lint issues, 58 files formatted).
- **Mypy:** Success: no issues found in 52 source files (`--strict` mode).
- **Verification Script (`scripts/check.ps1`):** All checks passed successfully.

#### 4. Decisions made and why
- **Short Database Transactions:** Commits are executed immediately after:
  1. `platform get_or_create`
  2. `scrape_run start_run`
  3. The batch of stub upserts for a listing
  4. EACH gig detail update (and detail failure recording / stale marking)
  5. `scrape_run finish_run` and circuit breaker updates.
  No write transaction is ever held open across network calls (`fetch_gig_detail`, `list_new_gigs`, or rate-limiter sleeps), eliminating SQLite write-lock contention across concurrent platform ticks.
- **Concurrent Platform Ticks Verified:** Tested on file-based SQLite in `tmp_path`: two platforms ticking concurrently with network delays produce no "database is locked" errors and both finish cleanly.
- **Mid-Tick Crash Safety:** An unhandled exception or kill during detail fetching retains all previously fetched gigs in `detail_fetched` state; the next tick completes remaining stubs without re-fetching already finished gigs.
- **Failure Policy & Migration #2:**
  - Added `detail_attempts: int` column to `gigs` table via Alembic migration #2 (`0002_add_detail_attempts.py`) with full upgrade and downgrade support.
  - Added `max_detail_attempts: int = 3` setting in `Settings`.
  - When detail fetch fails, `detail_attempts` is incremented. If `detail_attempts >= max_detail_attempts`, the gig is marked `processing_state="detail_failed"` and is no longer retried.
  - Circuit Breaker Failure Policy: An individual failed detail does NOT count as a platform failure. The circuit breaker only records a failure when listing fails, or when at least 2 detail fetches were attempted in the tick and ALL failed.
- **Leftover "New" Gigs Age Check:** Before fetching details for leftover "new" gigs from prior interrupted runs, the orchestrator applies the platform's `max_gig_age_minutes` check. If now older, the gig is transitioned to `stale` without making a network detail call.
- **SQLite NullPool & Connection Cleanup:** Fixed unclosed-connection SAWarning by properly scoping session usage within context managers in `cli.py` `db stats`, and configuring `NullPool` for SQLite file engines in `create_engine_from_url` to prevent abandoned connection fairies across event loops.

#### 5. Known issues / risks
- None. System is fully operational and green.

#### 6. Questions for owner
- None at this stage. All requirements and amendments for Phase 2 and Phase 2 fixes are implemented and tested.

#### 7. Proposed next phase and inputs needed
- **Phase 3: Rules-based pre-filter (section 6.2 of Master Prompt)**
- *Inputs needed:* Confirmation of `min_hourly_rate_usd` default (suggested $25/hr) to add to `rules.yaml` alongside fixed budget threshold.

#### 8. Handoff note
Phase 2 storage, deduplication, scheduling, and concurrency/transaction fixes are complete. The async SQLite/PostgreSQL schema with migrations #1 and #2, repositories, pipeline orchestrator with short transactions, age-limit stubbing (`stale`), failure policy with `detail_failed`, circuit breaker with failure isolation, APScheduler runner with jitter, and Typer CLI commands (`db upgrade`, `db stats`, `run [--once]`) are fully verified across 125 tests. Ready for **Phase 3** (Rules-based pre-filter).

### Phase 2 Fixes: Timezone Handling, Safe Ticks & Interrupted Run Tracking (Completed)

#### 1. What was built
- **UTCDateTime TypeDecorator (`src/gigradar/db/models.py`, `src/gigradar/db/__init__.py`):**
  - Implements custom `UTCDateTime(TypeDecorator[datetime])` wrapping `DateTime(timezone=True)`.
  - On write: requires/converts any incoming datetime into an aware UTC datetime (naive values treated as UTC).
  - On read: converts any stored datetime (including SQLite's naive strings) into an aware UTC datetime (`tzinfo=datetime.UTC`), preventing Python from interpreting naive database timestamps as local system time (e.g. UTC+3) when calling `.astimezone(UTC)`.
  - Applied to every datetime column across all models: `Platform.paused_until`, `Platform.created_at`, `Gig.posted_at`, `Gig.first_seen_at`, `Gig.last_seen_at`, `GigSnapshot.seen_at`, `ScrapeRun.started_at`, `ScrapeRun.finished_at`.
  - Configured in `Base.type_annotation_map` for `datetime`. Compatible with SQLite and PostgreSQL without needing schema data migrations.
- **Fail-Safe Tick Execution (`src/gigradar/pipeline/orchestrator.py`):**
  - Wrapped all execution in `_execute_tick` following `scrape_run` initialization inside a `try/except Exception` block.
  - On any unexpected exception: cleanly marks `scrape_run` finished with error details recorded in `errors_json`, records a failure in the circuit breaker, commits transaction, and returns a failed `TickResult` (never leaving orphaned unfinished runs in DB).
  - Propagates `asyncio.CancelledError` and `KeyboardInterrupt` without interference.
- **Startup Interrupted Run Cleanup (`src/gigradar/pipeline/scheduler.py`, `src/gigradar/db/repositories/scrape_run_repo.py`):**
  - Added `mark_interrupted_runs()` on `ScrapeRunRepository` and `cleanup_interrupted_runs()` on `SchedulerRunner`.
  - Automatically executed on `gigradar run` startup (`run_once()` and `run_forever()`): finds any `scrape_runs` where `finished_at IS NULL` and marks them finished with `errors_json` explaining that the run was interrupted (preventing them from looking healthy or being picked up by `get_last_successful_run`).
- **Enhanced Database Diagnostics (`src/gigradar/cli.py`, `src/gigradar/db/repositories/scrape_run_repo.py`):**
  - Added `get_last_finished_run()`, `count_failed_or_interrupted_runs_24h()`, and `get_latest_error_message()` on `ScrapeRunRepository`.
  - `gigradar db stats` updated to show per platform:
    - Last FINISHED run (timestamp, found, new, error count).
    - Count of failed or interrupted runs within the last 24 hours.
    - Last error message printed in table and displayed in full detail.
- **Regression Tests (`tests/test_phase2_fixes.py`):**
  - 5 comprehensive tests running on file-based SQLite in `tmp_path`:
    1. `test_freelancer_tick_after_previous_successful_run`: Verifies Freelancer second tick succeeds without naive vs aware datetime comparison error (`max(cutoff_aware, last_successful.started_at)`).
    2. `test_all_models_datetimes_are_aware_utc`: Verifies datetimes loaded from DB have `tzinfo == UTC` across all 4 models (`Platform`, `Gig`, `GigSnapshot`, `ScrapeRun`) and preserves wall time on `.astimezone(UTC)`.
    3. `test_unexpected_exception_finishes_run_and_trips_breaker`: Verifies unexpected tick exceptions mark the run finished, record error, and trip the breaker after N ticks.
    4. `test_interrupted_run_marking_at_startup`: Verifies startup marks unfinished runs as interrupted and excludes them from `get_last_successful_run`.
    5. `test_cli_db_stats_with_finished_and_failed_runs`: Verifies `gigradar db stats` outputs last finished run, 24h failure count, and last error message.

#### 2. Test results
- **Pytest:** 130 passed, 0 warnings (with `-W error`) in 68.36s.
- **Ruff:** All checks passed (0 lint issues, 59 files formatted).
- **Mypy:** Success: no issues found in 53 source files (`--strict` mode).

#### 3. Decisions made and why
- **UTCDateTime TypeDecorator:** SQLite returns naive strings that python's datetime parser turns into naive datetimes without tzinfo. By wrapping with `UTCDateTime`, both SQLite and PostgreSQL consistently return `datetime(..., tzinfo=datetime.UTC)`. This eliminates `TypeError: can't compare offset-naive and offset-aware datetimes` in `max(cutoff_aware, last_successful.started_at)` and prevents `.astimezone(UTC)` from shifting naive timestamps by system local offset.
- **Outer Tick Guard:** Mid-tick network or DB errors previously left `scrape_runs` rows with `finished_at NULL` and bypassed circuit breaker failure tracking. Wrapping after run start guarantees state cleanup and circuit breaker accounting.
- **Graceful Startup Recovery:** Marking orphaned runs on startup ensures clean audit trails without manual DB surgery after process crashes or restarts.

#### 4. Handoff note
Phase 2 fixes are complete and verified. The codebase is clean, typed (`mypy --strict`), formatted, and backed by 130 passing tests with `-W error`. Ready for **Phase 2.5a** (Reliability Hardening).

### Phase 2.5a: Reliability Hardening (Completed)

#### 1. What was built
- **WAF & Bot Protection Detection (`src/gigradar/platforms/common/exceptions.py`, `src/gigradar/platforms/common/http_client.py`):**
  - Created `BlockedByBotProtection(PlatformError)` exception.
  - In `PoliteHttpClient.get()`, detects HTTP 202 status code and `x-amzn-waf-action` response header, immediately raising `BlockedByBotProtection` before parsing.
  - Implemented `detect_html_bot_protection(html)` checking for Cloudflare challenges, AWS WAF challenges, CAPTCHAs, and maintenance pages.
  - Applied body markers strictly when an HTML listing yields 0 rows (in Mostaql and Khamsat client listings and Mostaql detail fetch), ensuring legitimate gigs whose title or description contains "challenge", "captcha", or maintenance keywords never trigger false alarms.
  - Excluded Freelancer JSON API from HTML body marker scans.
- **Suspicious Empty Listing Detection & Breaker Accounting (`src/gigradar/pipeline/orchestrator.py`, `src/gigradar/core/config_models.py`, `config/platforms.yaml`):**
  - Added `min_expected_listing_rows: int = 5` to `PlatformThresholds` in `config/platforms.yaml` for Mostaql and Khamsat (Freelancer remains at default 0).
  - In `PlatformOrchestrator._execute_tick()`, catches `BlockedByBotProtection` and records a platform failure on the circuit breaker.
  - If a scrape tick yields 0 gigs on an HTML platform where `min_expected_listing_rows > 0`, treats it as `suspicious_empty_listing`, recording a platform breaker failure and finishing the run with error state.
- **Startup Platform Health Checks (`src/gigradar/pipeline/scheduler.py`, `src/gigradar/cli.py`):**
  - Added `startup_health_checks()` to `SchedulerRunner`. Runs a single live polite health check per enabled platform before entering polling loops.
  - Non-crashing isolation: failures log errors and record breaker failures, but never crash `gigradar run`.
  - Added `--offline` flag to `gigradar doctor` (skipping live HTTP requests to platforms and Gemini API).
  - Added Section 5 "Platform Health Checks" table to `gigradar doctor` CLI diagnostics.
- **HTTP Client Resource Management & Concurrency Guards (`src/gigradar/pipeline/orchestrator.py`, `src/gigradar/platforms/base.py`):**
  - Added `async def close(self) -> None:` to `PlatformClient` protocol.
  - Implemented lazy client reuse in `PlatformOrchestrator.get_client()` across ticks, eliminating client connection and file descriptor leaks.
  - Added `close_clients()` called on scheduler shutdown (`SchedulerRunner.shutdown()`).
  - Implemented per-platform concurrency lock via `get_platform_lock()` in `PlatformOrchestrator`, preventing overlapping ticks on the same platform even if an external caller or tight timer triggers simultaneously.
- **Secret Redaction & Third-Party Logging Sanitization (`src/gigradar/core/logging.py`):**
  - Implemented `redact_secrets()` sanitizing Telegram bot tokens (`bot<digits>:<token>`) and sensitive query parameters (`token=...`, `key=...`).
  - Added `RedactingFilter` for Python stdlib logging and `structlog_redaction_processor` / `RedactingProcessorFormatter` for structlog, ensuring secrets are sanitized across log messages and exception tracebacks.
  - Set noisy HTTP and migration loggers (`httpx`, `httpcore`, `alembic`) to `logging.WARNING`.
- **Scheduler Startup Staggering (`src/gigradar/pipeline/scheduler.py`):**
  - Removed manual `run_once()` invocation inside `run_forever()`.
  - Staggered initial `next_run_time` across platforms (0s, 20s, 40s + jitter) so platforms do not spike the network or database at the same instant on startup.
- **Reliability Hardening Test Suite (`tests/test_reliability_hardening.py`):**
  - 21 comprehensive new unit tests covering:
    - HTTP 202 and `x-amzn-waf-action` header detection.
    - Cloudflare, AWS WAF, CAPTCHA, and maintenance body marker detection on 0-stub HTML responses.
    - Neutrality of legitimate gigs containing "challenge" or "captcha" in title/body (no false positives).
    - Exemption of Freelancer JSON API from HTML marker scans.
    - Breaker failure recording on `BlockedByBotProtection` and `suspicious_empty_listing`.
    - Client reuse across ticks and clean shutdown via `close_clients()`.
    - Per-platform `asyncio.Lock` preventing concurrent ticks.
    - Secret redaction in structlog, stdlib logging, and exception tracebacks.
    - Non-crashing startup health checks recording breaker failures.
    - Initial job staggering (0s, 20s, 40s + jitter).
    - Clean cancellation in `run_forever()` shielding `shutdown()`.

#### 2. How to run / verify it
```bash
# 1. Run all tests with strict zero-warning policy:
uv run pytest -W error

# 2. Run static typing and linting checks:
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests

# 3. Run doctor diagnostics in offline mode:
uv run gigradar doctor --offline

# 4. Run doctor diagnostics with live platform health checks:
uv run gigradar doctor

# 5. Run single polling tick:
uv run gigradar run --once
```

#### 3. Test results
- **Pytest:** 152 passed, 0 warnings (with `-W error`) in 23.51s.
- **Ruff:** All checks passed (0 lint issues, 61 files formatted).
- **Mypy:** Success: no issues found in 55 source files (`--strict` mode).

#### 4. Decisions made and why
- **Two-Condition Body Marker Trigger:** Body markers ("Just a moment", "challenge", "captcha", maintenance) only trigger when parsed listings yield 0 rows. Legitimate Arabic and English gig postings often use the word "challenge" (تحدي / challenge) or describe CAPTCHA integrations; triggering on text alone caused false positives.
- **Client Reuse Across Ticks:** Instantiating new HTTP clients on every tick leaked async transports and background connections under long-running daemon execution. Reusing one lazily initialized client per platform and closing all on `shutdown()` guarantees predictable socket life cycles.
- **Non-Crashing Startup Health Checks:** A platform experiencing temporary maintenance or WAF blocks at startup must not prevent the daemon from running or other healthy platforms from being polled. Recording a breaker failure on the failing platform and proceeding ensures resilient continuous operation.
- **Explicit Redaction of Formatted Logs & Tracebacks:** Both `structlog` and stdlib `logging` formatters were equipped with regex redaction filters so that neither unhandled exceptions printing URLs with query tokens nor debug logs can ever leak credentials into log aggregation or terminal outputs.

#### 5. Config changes made
- Modified `config/platforms.yaml`: added `min_expected_listing_rows: 5` under `mostaql.thresholds` and `khamsat.thresholds`. Freelancer remains exempt (default 0) as it uses a structured JSON API. No other config changes were made.

#### 6. Known issues / risks
- None. System is fully operational, clean, and green.

#### 7. Questions for owner
- None at this stage.

#### 8. Proposed next phase and inputs needed
- **Phase 3: Rules-based pre-filter (section 6.2 of Master Prompt)**
- *Inputs needed:* Owner confirmation to proceed with Phase 3.

#### 9. Handoff note
Phase 2.5a reliability hardening is complete and verified. All silent-failure risks identified in the review have been resolved. All 152 unit tests pass with zero warnings, lint and mypy strict pass with zero issues. Ready for Phase 3 upon user "go".
