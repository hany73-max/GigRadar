# GigRadar: Progress Log & Active State

This document tracks the current state, active decisions, carry-forward notes, and run instructions.
Historical phase reports (Phases 0 through 2.5a-fix) are archived in [docs/history/PROGRESS_ARCHIVE.md](file:///d:/github/GigRadar/docs/history/PROGRESS_ARCHIVE.md).

---

## Current Status Overview

- **Current Phase:** Phase 2.5b: Config single source of truth, HTTP polish, LLM defaults & docs cleanup (COMPLETED)
- **Next Phase:** Phase 3: Rules-based pre-filter (Master Prompt Section 6.2)
- **Overall System Health:** Green (Offline test suite passing with `-W error` via `pytest-socket`, strict mypy & ruff clean, `scheduler.py` 99% coverage, `gigradar.db` untouched, live doctor probing Gemini 3.x models)

---

## Protected Configuration Invariants

The following configuration files define the owner's personal identity, verified skills, and source of truth. **The agent must NEVER edit or fabricate claims/skills in these files without explicit owner instruction:**
1. `config/profile.yaml`: Owner profile, skill tiers (work to accept), and hard rejects.
2. `config/portfolio.yaml`: Verified technical projects and repository links.
3. `config/claims_allowlist.yaml`: Allowed pitch claims tracing strictly to CV/portfolio facts.

---

## Carry-Forward Notes

- **Phase 3 (Hourly & Fixed Range Thresholds):** Compare hourly projects against a separate `min_hourly_rate_usd` in `rules.yaml`, and use `budget_max_usd` for minimum-budget checks on fixed ranges.
- **Phase 3 (Freelancer Saturation Strategy):** Freelancer projects accumulate bids within minutes; filter should prefer low `bids_count` and recent `posted_at`.
- **Phase 3 & 5 (Khamsat Detail Level):** `detail_level` (`full | title_only`) indicates description is absent for Khamsat; filter and scorer must score based on title/stub without penalty for missing description.
- **Phase 4 (Scorer LLM Structured Output):** Use `gemini-3.5-flash-lite` with Pydantic JSON schema output; enforce strict `LLM_MAX_RPM=10` and `LLM_DAILY_CALL_BUDGET=200`.
- **Phase 5 (Pitch Generator):** Use `gemini-3.8-flash`; validate every factual claim against `config/claims_allowlist.yaml` and retrieved portfolio items.
- **Phase 6 (Claim Validation):** Use claim-based validation (evaluating pitch statements against `claims_allowlist.yaml` facts via LLM judge rather than naive regex bans).
- **Phase 8 (Telegram Approval Workflow):** Human approval is strictly mandatory before any submission (`AUTO_SUBMIT=false`).

---

## Key Decisions & Architecture Log

1. **Config Single Source of Truth:** Platform polling intervals are exclusively owned by `platforms.yaml`. Dead `POLL_INTERVAL_SECONDS_*` env variables removed.
2. **Inherited Thresholds Resolver:** `PlatformThresholds` fields (`max_existing_bids`, `min_budget_usd`, `max_gig_age_minutes`) are `Optional`. Single resolver `resolve_platform_thresholds(name)` inherits unset fields from `rules.yaml`.
3. **Strict Config Validation:** All YAML models enforce `extra="forbid"` via `ConfigBaseModel` so typos fail loudly.
4. **WAF & Rate Limiting:** `PoliteHttpClient` enforces jitter, rate limiting, and caps `Retry-After` at `max_retry_after_seconds=120`. `RateLimiter` uses `None` sentinel. Freelancer sends `Accept: application/json`.
5. **Circuit Breakers:** `circuit_breaker_failures` and `circuit_breaker_cooldown_minutes` in `platforms.yaml` wire directly into `CircuitBreaker`.
6. **Gemini 3.x Defaults:** Migrated default scorer to `gemini-3.5-flash-lite` and pitch to `gemini-3.8-flash` (2.5-flash deprecated/404 for new users). `doctor` performs real 1-token generation per model (skipped with `--offline`). Key masking displays only last 4 chars.
7. **Database Isolation in Tests:** Autouse session template copy in `conftest.py` protects real `gigradar.db`. `pytest-socket` blocks external networking.
8. **Short Transactions & Concurrency:** Commits after each detail fetch; no write locks across network calls; per-platform `asyncio.Lock` prevents concurrent ticks.

---

## Known Issues / Risks

- **Per-Model Quotas:** Specific RPM/RPD limits for Gemini 3.x models are only visible in Google AI Studio console (marked UNVERIFIED in docs). Conservative client-side limits (`LLM_MAX_RPM=10`, `LLM_DAILY_CALL_BUDGET=200`) prevent exhaustion.
- **Khamsat AWS WAF:** Khamsat detail pages challenge with HTTP 202; parsed from listing only by design.

---

## How to Run & Verify

```bash
# 1. Run offline test suite with strict error policy:
uv run pytest -W error

# 2. Run static analysis:
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests

# 3. System diagnostics:
uv run gigradar doctor --offline
uv run gigradar db stats

# 4. Scrape once / run daemon:
uv run gigradar scrape-once freelancer --limit 3
uv run gigradar run --once
```
