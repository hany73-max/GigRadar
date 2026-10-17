# GigRadar: Progress Log & Project Memory

This document is the single source of truth for the project's current state, decisions, known issues, and phase checkpoint reports.

---

## Current Status Overview

- **Current Phase:** Phase 0: Foundation (COMPLETED)
- **Next Phase:** Phase 1: Platform discovery and parsers (Mostaql & Khamsat)
- **Overall System Health:** Green (All 15 unit tests passing, `ruff` clean, `mypy --strict` clean, `gigradar doctor` operational)

---

## Phase History

### Phase 0: Foundation (Completed)

#### 1. What was built
- **Repository Scaffold & Tooling:**
  - `pyproject.toml`: Modern packaging with `uv`, pinning dependencies (`pydantic`, `pydantic-settings`, `pyyaml`, `typer`, `structlog`, `rich`, `google-genai`, `sqlalchemy`, `httpx`, `tenacity`) and strict dev tooling (`ruff`, `mypy`, `pytest`, `pytest-asyncio`).
  - `.gitignore` & `.env.example`: Comprehensive git ignore and documented environment configuration.
  - `README.md`: Quickstart instructions.
  - `scripts/check.ps1` & `scripts/check.sh`: One-command CI-style verification runner (`ruff` + `mypy` + `pytest`).
- **Configuration & Validation Layer:**
  - `config/profile.yaml`: Owner profile (Hany Elashry), skill tiers (A, B, C), and hard rejects.
  - `config/portfolio.yaml`: Seeded with 5 technical projects (Sky-Spy, Kessler-Shield, TicketSense, The ML Blueprint, FMCW Radar) tagged for retrieval.
  - `config/claims_allowlist.yaml`: Factual allowlist of skills and truthful wording for deep learning, plus regex patterns for forbidden exaggerations.
  - `config/rules.yaml`: Stage 1 deterministic rules (keyword families in Arabic & English, budget/bid/age thresholds, hard rejects, category lists).
  - `config/platforms.yaml`: Platform configurations for Mostaql, Khamsat, and Freelancer.com.
  - `src/gigradar/core/config_models.py`: Pydantic v2 schemas validating each YAML file.
  - `src/gigradar/core/config_loader.py`: Safe loaders and `validate_all_configs()`.
- **Core Architecture & Verifier:**
  - `src/gigradar/core/settings.py`: Pydantic `BaseSettings` reading environment and `.env`.
  - `src/gigradar/core/logging.py`: Structured logging (`structlog`) with console formatting and JSON capability.
  - `src/gigradar/core/gemini_verifier.py`: Verification utility testing live connectivity to Gemini API via `google-genai` SDK without exposing credentials.
- **CLI & Diagnostic System:**
  - `src/gigradar/cli.py`: Typer CLI entrypoint with `gigradar doctor` command inspecting configuration files, environment variables, database syntax, and live Gemini API connectivity.
- **Documentation & Research:**
  - `docs/LLM_NOTES.md`: Verified Gemini SDK (`google-genai`), model IDs (`gemini-2.5-flash`), rate limits, data-privacy boundaries, and native structured outputs.
- **Test Suite:**
  - `tests/test_config.py`: Validates all 5 YAML files and schema edge cases.
  - `tests/test_settings.py`: Tests default settings and environment variable overrides.
  - `tests/test_gemini_verifier.py`: Tests API key masking and connectivity validation with mocks.
  - `tests/test_cli.py`: Tests `--version` and `doctor --skip-live-llm` commands.

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
# (Add GEMINI_API_KEY to .env to verify live Gemini API connection)
```

#### 3. Test results
- **Pytest:** 15 passed in 0.95s.
- **Ruff:** All checks passed (clean lint and imports).
- **Mypy:** Success: no issues found in 12 source files (`--strict` mode).

#### 4. Decisions made and why
- **SDK Choice:** Selected official `google-genai` SDK (v0.8.0) as mandated by Master Prompt section 6.3b, deprecating older `google-generativeai`.
- **Default Scorer Model:** Defaulted `LLM_MODEL_SCORER` and `LLM_MODEL_PITCH` to `gemini-2.5-flash` in `.env.example` and `Settings` for high-speed, cost-effective processing, while keeping them configurable via environment variables.
- **CLI Framework:** Selected `typer` and `rich` for clean, user-friendly diagnostic tables during `gigradar doctor`.
- **Strict Typing:** Enforced `mypy --strict` across `src/` and `tests/` from day one to avoid latent type drift.

#### 5. Known issues / risks
- `google-genai` internally triggers an `ArbitraryTypeWarning` on pydantic schema generation due to upstream usage of `<built-in function any>`. This does not impact runtime functionality and is ignored by our strict typing.
- No live Gemini API key is currently configured in the environment; `gigradar doctor` successfully validates all configs and prompts the user to add the key to `.env` when ready for Phase 5.

#### 6. Questions for owner
- None at this stage.

#### 7. Proposed next phase and inputs needed
- **Phase 1: Platform discovery and parsers (Mostaql & Khamsat)**
- *Inputs needed:* A browser discovery pass on Mostaql (`https://mostaql.com/projects`) and Khamsat (`https://khamsat.com/community/requests`) to inspect real DOM structure, extract sample fixtures into `tests/fixtures/html/`, and record findings in `docs/PLATFORM_NOTES.md`.

#### 8. Handoff note
Phase 0 foundation is complete and verified with green tests and clean linting. The repository is scaffolded with `uv`, Pydantic v2 schemas for all 5 config YAMLs, Typer CLI with `gigradar doctor`, and `docs/LLM_NOTES.md`. Next session can proceed directly to Phase 1 (browser inspection and pure-function parsers for Mostaql and Khamsat).
