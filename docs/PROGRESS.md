# GigRadar: Progress Log & Project Memory

This document is the single source of truth for the project's current state, decisions, known issues, and phase checkpoint reports.

---

## Current Status Overview

- **Current Phase:** Phase 1b: Freelancer.com via official API (COMPLETED)
- **Next Phase:** Phase 2: Storage, dedupe, scheduling
- **Overall System Health:** Green (All 101 unit tests passing, `ruff` clean, `mypy --strict` clean on 32 source files, 0 warnings, `gigradar doctor` operational, `gigradar scrape-once mostaql`, `khamsat`, and `freelancer` functional)

---

## Carry-Forward Notes

- **Phase 2 (Khamsat New-Gig Detection):** Khamsat listings are ordered by last activity, not posting time, so new-gig detection must use `external_id` plus a `posted_at` age check, never an early exit on a known ID.
- **Phases 3 & 5 (Khamsat Detail Level):** Add a `detail_level` field (`full | title_only`) to `Gig`, set it to `title_only` for Khamsat, and make the rules filter and the scorer prompt aware that the description is missing.
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
- **Test Suite (8 new tests, 101 total):**
  - `tests/test_freelancer_parser.py`: 5 tests validating single project parsing, stub parsing, active envelope parsing, hourly project handling, exclusion rules (NDA, local, recruiter, contests, closed), and error cases.
  - `tests/test_platform_clients.py`: Added 2 tests for protocol conformance, mock listing/detail flow, and health check failure handling.
  - `tests/test_cli.py`: Added test for `scrape-once freelancer`.

#### 2. How to run / verify it
```bash
# Full verification:
uv run ruff check .
uv run mypy src tests
uv run pytest -v

# Run the complete verification script:
powershell -ExecutionPolicy Bypass -File scripts/check.ps1

# Live scraping against Freelancer official API (unauthenticated):
uv run gigradar scrape-once freelancer --limit 5
```

#### 3. Test results
- **Pytest:** 101 passed in 6.03s (0 warnings).
- **Ruff:** All checks passed.
- **Mypy:** Success: no issues found in 32 source files (`--strict` mode).

#### 4. Decisions made and why
- **Unauthenticated Active Project Search:** Discovery confirmed that `GET /projects/0.1/projects/active/` returns HTTP 200 without OAuth tokens. However, client details (`owner_id`, `owner_info`, buyer KYC, location) are hidden (`None`) by Freelancer unless authenticated. This satisfies Phase 1b read-only requirements cleanly without needing an OAuth app.
- **Native Exchange Rate Utilization:** The Freelancer API provides live currency `exchange_rate` directly inside each project's `currency` dictionary (`1.0` for USD, `1.3328` for GBP, `0.010531` for INR, etc.). `budget_usd_est` is computed directly as `round(budget_min * exchange_rate, 2)`, avoiding external FX lookups.
- **Discrete `project_type` Model Field:** Added `project_type: Literal["fixed", "hourly"] = "fixed"` to `Gig` so hourly project ranges are strictly preserved without corrupting fixed-price calculations.
- **Server-Side + Local Exclusions:** The parser excludes listings flagged as `upgrades.NDA=True`, `local=True`, `upgrades.recruiter=True`, `assisted=True`, or `type="contest"`.
- **Zero-Extra-Network Detail Fetch:** Active project listing queries with `full_description=true` and `job_details=true` already return complete project records; `FreelancerClient` caches these parsed `Gig`s so `fetch_gig_detail(stub)` resolves instantly with zero extra HTTP requests.

#### 5. Known issues / risks
- **Client Metadata Hidden:** As discovered, client stats (ratings, hire rate, payment verification) are unavailable unauthenticated. When OAuth is added in Phase 9 for bidding, authenticated calls can enrich client profile details.
- **High Project Volume:** Freelancer projects receive dozens of bids within minutes. The platform-specific `max_existing_bids: 40` and shorter `max_gig_age_minutes: 360` correctly prevent chasing stale projects.

#### 6. Questions for owner
- None at this stage. All requirements and acceptance criteria for Phase 1b are satisfied.

#### 7. Proposed next phase and inputs needed
- **Phase 2: Storage, dedupe, scheduling** (SQLAlchemy models, Alembic migrations, repositories, idempotent upserts, bid-count snapshots, APScheduler background runner with jitter, and circuit breaker).
- *Inputs needed:* None. Can begin Phase 2.

#### 8. Handoff note
Phase 1b is complete. `FreelancerClient` queries the official Freelancer REST API using `PoliteHttpClient` with server-side skill filtering and deduplication. The pure-function parser correctly normalizes multicurrency budgets to USD via live API exchange rates and handles hourly projects cleanly. All 101 tests pass, linters and strict mypy are green, and `gigradar scrape-once freelancer --limit 5` works live. Ready for **Phase 2** (Storage, dedupe, scheduling).

