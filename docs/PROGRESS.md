# GigRadar: Progress Log & Active State

This document tracks the current state, active decisions, carry-forward notes, and run instructions.
Historical phase reports (Phases 0 through 2.5a-fix) are archived in [docs/history/PROGRESS_ARCHIVE.md](file:///d:/github/GigRadar/docs/history/PROGRESS_ARCHIVE.md).

---

## Current Status Overview

- **Current Phase:** Phase 3: Stage 1 rules-based pre-filter (COMPLETED)
- **Next Phase:** Phase 4: Telegram alerting & human review (Master Prompt Section 7 & 9)
- **Overall System Health:** Green (185 offline tests passing with `-W error` via `pytest-socket`, strict mypy & ruff clean, Alembic migration 0003 applied, 89 real stored gigs classified with 88.8% noise drop)

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
- **Phase 4 (Telegram Alerts):** Human approval workflow via Telegram cards. On startup suppress alerts for gigs older than 60 minutes (configurable) so the first run does not flood Telegram.
- **Phase 5 (LLM Scoring):** Use `gemini-3.5-flash-lite` with Pydantic JSON schema output; enforce strict `LLM_MAX_RPM=10` and `LLM_DAILY_CALL_BUDGET=200`.
- **Phase 6 (Pitch Generator & Claim Validation):** Use `gemini-3.8-flash`; validate every factual claim against `config/claims_allowlist.yaml` and retrieved portfolio items via claim-based LLM judge rather than naive regex bans.
- **Phase 7 (Manual-Send & Outcomes):** Manual delivery package with copy-ready text, direct platform link, and outcome tracking.
- **Phase 8 (Hardening):** Layout-drift alerts, retries, 24h soak test, and fetch page 2 of Mostaql/Khamsat listings only when page 1 has no already-known gigs.
- **Phase 9 (Submission Safety):** Human approval is strictly mandatory before any submission (`AUTO_SUBMIT=false`).

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

## Checkpoint: Phase 3 (Stage 1 Rules-Based Pre-Filter)

- **What was built:**
  - **Housekeeping (H1, H2, H3):** Fixed `resolve_platform_thresholds` to propagate YAML/validation errors loudly; anchored default config directory to project root `PROJECT_ROOT / "config"` with `GIGRADAR_CONFIG_DIR` override; aligned phase numbering in `docs/PROGRESS.md`.
  - **Models & Schema:** Extended `RulesThresholds` and `ResolvedThresholds` with `min_hourly_rate_usd: float = 15.0`. Added `ambiguous_keywords` and `exclude_keywords` to `RulesConfig`. Created `Classification` SQLAlchemy model and Alembic migration `0003_add_classifications.py` with indexes on `gig_id`, `stage`, `passed`, `rules_version`, `created_at`.
  - **Normalization & Pattern Compiler:** Implemented [normalize.py](file:///d:/github/GigRadar/src/gigradar/classify/normalize.py) with full Arabic unicode normalization (tashkeel, tatweel, alef variants, ya/alef maqsura, ta marbuta, digits 0-9, lowercase, whitespace) and regex compilation supporting Arabic clitic prefixes (`و, ف, ب, ل, ك, ال, لل, وال, بال, كال, فال`) with root protection for 3-letter roots, alongside strict Latin ASCII boundaries.
  - **Deterministic Rules Filter:** Implemented [rules_filter.py](file:///d:/github/GigRadar/src/gigradar/classify/rules_filter.py) evaluating: Hard rejects -> Platform thresholds (age, bids, fixed vs hourly budget) -> Exclude keywords -> Include keywords & Ambiguous keywords -> Category deny-list (weak signal, never overrides include hit).
  - **DB Repositories & Pipeline Integration:** Added classification recording and querying methods to [gig_repo.py](file:///d:/github/GigRadar/src/gigradar/db/repositories/gig_repo.py), strictly protecting `stale` gigs from being altered. Wired `RulesFilter` into [orchestrator.py](file:///d:/github/GigRadar/src/gigradar/pipeline/orchestrator.py) to immediately classify gigs upon ingestion without holding write locks across network calls.
  - **CLI Commands:** Implemented `gigradar classify-stored [--platform X] [--limit N] [--reclassify]`, `gigradar rules-report`, and `gigradar explain-gig <platform> <external_id>`.
  - **Golden Test Suite:** Created [tests/golden/rules_cases.yaml](file:///d:/github/GigRadar/tests/golden/rules_cases.yaml) containing 44 test cases executed in a single test, plus 14 additional unit and integration tests in [tests/test_rules_filter.py](file:///d:/github/GigRadar/tests/test_rules_filter.py).

- **How to verify:**
  ```bash
  # 1. Run all 185 tests under strict error policy:
  uv run pytest -W error

  # 2. Run static analysis:
  uv run ruff check .
  uv run ruff format --check .
  uv run mypy src tests

  # 3. Classify stored database gigs:
  uv run gigradar classify-stored --reclassify

  # 4. View rules classification metrics and breakdown:
  uv run gigradar rules-report

  # 5. Explain classification for a specific gig:
  uv run gigradar explain-gig mostaql 1286695
  ```

- **Decisions made:**
  1. *Dual Normalization:* Both rules keyword configurations and gig text are run through the identical Arabic/Latin normalization pipeline.
  2. *Arabic Clitics vs. Root Protection:* Allowed prefixes `و, ف, ب, ل, ك, ال, لل, وال, بال, كال, فال` before keywords with word boundaries after. Implemented root guard so words with `< 5` characters (e.g. `آلي` -> `الي`) do not have `ال` stripped as a prefix, preserving 3-letter roots.
  3. *Academic Software Testing Guard:* Bare `اختبار` caused false academic rejections on software QA/testing gigs; refined hard reject pattern to `حل اختبار`, `اختبار جامعي`, and `اختبارات جامعية`.
  4. *Category as Weak Signal:* Category deny-list entries only reject when no include keywords match.
  5. *Historical Age Evaluation in Replay:* `classify-stored` uses `gig.first_seen_at` as the fallback reference time so historical stored gigs evaluate their freshness when collected rather than failing `age_exceeded`.

- **Rules Report Results on Real Stored Gigs (89 total):**
  - **Passed:** 10 (11.2%)
  - **Rejected:** 79 (88.8%) — noise reduction of ~89% before LLM scoring.
  - **Top Reject Reasons:**
    1. `no_include_keywords`: 37
    2. `hard_reject`: 19 (academic homework, CV writing, mobile repair)
    3. `exclude_keyword`: 17 (WordPress themes, video editing, social media marketing)
    4. `bids_exceeded`: 3
    5. `hourly_rate_below_min`: 2 (< $15/hr)
    6. `budget_below_min`: 1 (< $25 fixed)

- **Known issues / deferred work:**
  - None for Phase 3. Ready for Phase 4 (Telegram alerts).

- **Questions for the owner:**
  - Please inspect the 10 passed gigs and top reject reasons via `gigradar rules-report`. Does the noise reduction (~89%) align with your target, or should any keyword be tuned?

- **Proposed next phase:**
  - Phase 4: Telegram alerts & human review workflow (Master Prompt Section 7 & 9).

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

# 4. Rules pre-filter inspection:
uv run gigradar classify-stored
uv run gigradar rules-report
uv run gigradar explain-gig <platform> <external_id>

# 5. Scrape once / run daemon:
uv run gigradar scrape-once freelancer --limit 3
uv run gigradar run --once
```

