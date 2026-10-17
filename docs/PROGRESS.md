# GigRadar: Progress Log & Project Memory

This document is the single source of truth for the project's current state, decisions, known issues, and phase checkpoint reports.

---

## Current Status Overview

- **Current Phase:** Phase 1: Platform discovery and parsers (COMPLETED)
- **Next Phase:** Phase 1b: Freelancer.com via official API
- **Overall System Health:** Green (All 73 unit tests passing, `ruff` clean, `mypy --strict` clean on 28 source files, 0 warnings, `gigradar doctor` operational, `gigradar scrape-once mostaql` and `gigradar scrape-once khamsat` functional)

---

## Carry-Forward Notes

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
- **Test Suite (55 new tests, 73 total):**
  - `tests/test_normalization.py`: 30 parametrized tests for digit normalization, relative Arabic time, datetime parsing, budget ranges, bid counts, language detection.
  - `tests/test_parsers.py`: 4 tests against real HTML fixtures (Mostaql listing, Mostaql detail, Khamsat listing, error handling).
  - `tests/test_http_client.py`: 5 tests for rate limiter, retry-after parsing, mock HTTP success, 503 retry recovery.
  - `tests/test_platform_clients.py`: 4 tests for protocol conformance, mock listing+detail flow (Mostaql/Khamsat), health check failure handling.
  - `tests/test_cli.py`: 2 new tests for `scrape-once` (unsupported platform, mocked successful scrape).
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
- **Pytest:** 73 passed in 3.64s (0 warnings).
- **Ruff:** All checks passed (clean lint and imports).
- **Mypy:** Success: no issues found in 28 source files (`--strict` mode).

#### 4. Decisions made and why
- **No Playwright / No WAF bypass:** Khamsat detail pages return HTTP 202 with AWS WAF JS challenge. Per project safety rules and anti-bot policy, we do NOT use browser automation. Khamsat is parsed from listing pages only; detail-only fields (extended description, thread replies) stay `None`. This is documented in `docs/PLATFORM_NOTES.md` section 2.3.
- **Pure-function parsers:** All HTML parsing is in pure functions (`parse_mostaql_listing`, `parse_mostaql_detail`, `parse_khamsat_listing`) that take raw HTML strings and return typed Pydantic models. Zero network calls inside parsers — fully unit-testable against fixtures.
- **Dual timestamp strategy:** Both Mostaql (`<time datetime="...">`) and Khamsat (`<span title="DD/MM/YYYY HH:MM:SS GMT">`) provide machine-readable timestamps alongside Arabic relative text. The parser tries machine-readable first, falls back to relative Arabic parsing.
- **PoliteHttpClient design:** Rate limiter uses async lock for concurrency safety, jitter is configurable per-platform via `platforms.yaml`, retries use tenacity with exponential backoff, and `Retry-After` headers are honored for both integer-seconds and HTTP-date formats.
- **Sanitized fixtures:** All HTML fixtures had personal names, emails, and profile photos replaced with placeholders before committing, while preserving the DOM structure needed for parser validation.

#### 5. Known issues / risks
- **Khamsat detail pages inaccessible:** By design (AWS WAF). Budget, extended description, and tags from Khamsat are `None`. This is acceptable for Phase 1; if detail data becomes needed, a logged-in session cookie approach could be explored in a future phase.
- **Layout drift risk:** Both platforms could change their HTML structure at any time. The `health_check()` method on each client validates that the listing page still parses correctly, and the `gigradar doctor` can be extended to run these checks.

#### 6. Questions for owner
- None at this stage. Phase 1 acceptance criteria are met: both `scrape-once` commands work, parser tests pass against fixtures, and `docs/PLATFORM_NOTES.md` documents all findings.

#### 7. Proposed next phase and inputs needed
- **Phase 1b: Freelancer.com via official API** (per section 6.1b and section 9 of master prompt).
- *Inputs needed:* Freelancer.com OAuth credentials (or decision to skip Phase 1b and proceed to Phase 2: Storage, dedupe, scheduling).

#### 8. Handoff note
Phase 1 is complete. Mostaql listing+detail and Khamsat listing-only parsers work against real HTML, backed by 73 tests (all green). No Playwright in the project. `PoliteHttpClient` handles rate limiting, jitter, retries, and `Retry-After`. The `PlatformClient` protocol is established and both `MostaqlClient` and `KhamsatClient` conform to it. `docs/PLATFORM_NOTES.md` has full technical profiles. Ready for **Phase 1b** (Freelancer.com API) or **Phase 2** (Storage & scheduling).
