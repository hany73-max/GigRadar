# GigRadar: Progress Log & Project Memory

This document is the single source of truth for the project's current state, decisions, known issues, and phase checkpoint reports.

---

## Current Status Overview

- **Current Phase:** Phase 0: Foundation (COMPLETED & REFINED)
- **Next Phase:** Phase 1: Platform discovery and parsers (Mostaql & Khamsat)
- **Overall System Health:** Green (All 18 unit tests passing, `ruff` clean, `mypy --strict` clean, 0 warnings, `gigradar doctor` detects placeholders accurately)

---

## Phase History

### Phase 0: Foundation (Completed)

#### 1. What was built
- **Repository Scaffold & Tooling:**
  - `pyproject.toml`: Modern packaging with `uv`, pinning dependencies (`pydantic`, `pydantic-settings`, `pyyaml`, `typer`, `structlog`, `rich`, `google-genai>=0.1.1` [v2.31.0], `sqlalchemy`, `httpx`, `tenacity`) and strict dev tooling (`ruff`, `mypy`, `pytest`, `pytest-asyncio`).
  - `.gitignore` & `.env.example`: Comprehensive git ignore and documented environment configuration with placeholders.
  - `README.md`: Quickstart instructions.
  - `scripts/check.ps1` & `scripts/check.sh`: One-command CI-style verification runner (`ruff` + `mypy` + `pytest`).
  - `scripts/test_structured_output.py`: Live structured output validation script.
- **Configuration & Validation Layer:**
  - `config/profile.yaml`: Owner profile (Hany Elashry), skill tiers (A, B, C describing work to ACCEPT), and hard rejects.
  - `config/portfolio.yaml`: Seeded with 5 technical projects (Sky-Spy, Kessler-Shield, TicketSense, The ML Blueprint, FMCW Radar) tagged for retrieval.
  - `config/claims_allowlist.yaml`: Strictly traces to Hany's CV only (what pitches may CLAIM). Honest PyTorch/CNN line preserved. Removed: ResNet/EfficientNet/YOLO, HuggingFace transformers, MySQL/MongoDB.
  - `config/rules.yaml`: Stage 1 deterministic rules (keyword families in Arabic & English, budget/bid/age thresholds, hard rejects, category lists).
  - `config/platforms.yaml`: Platform configurations for Mostaql, Khamsat, and Freelancer.com.
  - `src/gigradar/core/config_models.py`: Pydantic v2 schemas validating each YAML file.
  - `src/gigradar/core/config_loader.py`: Safe loaders and `validate_all_configs()`.
- **Core Architecture & Verifier:**
  - `src/gigradar/core/settings.py`: Pydantic `BaseSettings` reading environment and `.env`.
  - `src/gigradar/core/logging.py`: Structured logging (`structlog`) with console formatting and JSON capability.
  - `src/gigradar/core/gemini_verifier.py`: Verification utility testing live connectivity to Gemini API via `google-genai` SDK with credential masking and placeholder detection.
- **CLI & Diagnostic System:**
  - `src/gigradar/cli.py`: Typer CLI entrypoint with `gigradar doctor` command inspecting configuration files, environment variables, database syntax, placeholder detection, and live Gemini API connectivity.
- **Documentation & Research:**
  - `docs/LLM_NOTES.md`: Verified against official Google documentation (`ai.google.dev`, 2026-10-17) with source URLs and verification dates. Documents SDK (`google-genai`), model IDs (`gemini-2.5-flash`), rate limits (15 RPM free, 1,000 RPM Tier 1), spend caps, data-privacy boundaries, and native structured outputs.
  - `docs/MASTER_PROMPT.md`: Master specification maintained in `docs/` (root duplicate deleted).
- **Test Suite:**
  - `tests/test_config.py`: Validates all 5 YAML files and schema edge cases.
  - `tests/test_settings.py`: Tests default settings and environment variable overrides.
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
- **Pytest:** 18 passed in 1.61s (0 warnings, `ArbitraryTypeWarning` fully resolved).
- **Ruff:** All checks passed (clean lint and imports).
- **Mypy:** Success: no issues found in 12 source files (`--strict` mode).

#### 4. Decisions made and why
- **SDK Upgrade:** Upgraded `google-genai` to `v2.31.0` (removed `<1.0.0` cap). This completely resolved the internal `ArbitraryTypeWarning` on Pydantic schema generation.
- **Placeholder Detection:** Updated `gigradar doctor` to intercept example/template tokens (`your_gemini_api_key_here`, dummy chat IDs) and display `PLACEHOLDER` rather than attempting invalid network calls.
- **CV Alignment for Claims:** Confined `config/claims_allowlist.yaml` strictly to verified CV facts (PostgreSQL/SQLAlchemy, NumPy fundamentals, XGBoost/imbalanced data, and honest PyTorch beginner wording), removing unverified tools.
- **Spec Organization:** Deleted redundant root `MASTER_PROMPT.md` to keep `docs/MASTER_PROMPT.md` as the single canonical specification.

#### 5. Known issues / risks
- None. System is fully operational and green. Placeholders in `.env` are safely detected without crashing diagnostics.

#### 6. Questions for owner
- None at this stage.

#### 7. Proposed next phase and inputs needed
- **Phase 1: Platform discovery and parsers (Mostaql & Khamsat)**
- *Inputs needed:* A browser discovery pass on Mostaql (`https://mostaql.com/projects`) and Khamsat (`https://khamsat.com/community/requests`) to inspect real DOM structure, extract sample fixtures into `tests/fixtures/html/`, and record findings in `docs/PLATFORM_NOTES.md`.

#### 8. Handoff note
Phase 0 foundation and refinements are fully complete. `pyproject.toml` uses `google-genai v2.31.0` with 0 warnings, `claims_allowlist.yaml` is strictly aligned with the owner's CV, `docs/LLM_NOTES.md` is cited with `ai.google.dev` links and dates, and `gigradar doctor` cleanly identifies placeholders. All 18 tests are green. Ready for **Phase 1**.
