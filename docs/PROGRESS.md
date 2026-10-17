# GigRadar: Progress Log & Project Memory

This document is the single source of truth for the project's current state, decisions, known issues, and phase checkpoint reports.

---

## Current Status Overview

- **Current Phase:** Phase 0: Foundation (COMPLETED & REFINED)
- **Next Phase:** Phase 1: Platform discovery and parsers (Mostaql & Khamsat)
- **Overall System Health:** Green (All 18 unit tests passing, `ruff` clean, `mypy --strict` clean, 0 warnings, `gigradar doctor` operational)

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
