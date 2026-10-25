# GigRadar

GigRadar is an intelligent freelance project monitoring, filtering, and proposal assistant designed for engineers. It continuously discovers new projects across multiple freelancing platforms, validates and filters listings deterministically, evaluates fit via Google Gemini LLM structured outputs, and generates tailored proposals grounded in the owner's verified portfolio and CV.

---

## Safety & Operating Rules

GigRadar is built strictly around a **Human-in-the-Loop** safety architecture:
1. **Zero Automated Bidding (`AUTO_SUBMIT=false`):** GigRadar never submits bids or proposals autonomously. All generated pitches are staged for human review.
2. **Human Approval Required:** Every proposal must be explicitly inspected, verified, and approved by the owner before submission on any freelance platform.
3. **No Platform Abuse:** Scraping is performed politely with rate limiting, randomized jitter, exponential backoff, and circuit breakers. Gigs are inspected via public listings or official developer APIs (e.g., Freelancer REST API).
4. **Data Privacy Guardrails:** No private data (credentials, Telegram tokens, chat IDs, database connection strings) is ever sent to LLMs. Only public project text is sent to Google Gemini.

---

## Quickstart Setup

Clone the repository and install dependencies using [uv](https://github.com/astral-sh/uv):

```bash
# 1. Install dependencies
uv sync --all-extras

# 2. Configure environment
cp .env.example .env
# Edit .env and supply your GEMINI_API_KEY

# 3. Initialize or upgrade database schema
uv run gigradar db upgrade

# 4. Run system diagnostics
uv run gigradar doctor --offline
```

---

## CLI Command Reference

GigRadar provides a unified CLI via `typer` and `rich`:

| Command | Arguments / Flags | Description |
| :--- | :--- | :--- |
| `gigradar doctor` | `[--offline] [--skip-live-llm]` | Inspects environment variables, database connectivity, Alembic migration status, configuration YAML schemas, and tests 1-token live generation for configured LLM models. |
| `gigradar db upgrade` | `[-r / --revision REVISION]` | Runs Alembic database migrations up to `head` (or specified revision). |
| `gigradar db stats` | *None* | Displays database metrics, counts per status, per-platform last scrape status, 24h failures, and timestamp of the last recorded error. |
| `gigradar scrape-once` | `<platform> [--limit N] [--all]` | Executes a standalone scrape pass on a single platform (`mostaql`, `khamsat`, or `freelancer`) without writing to the database. |
| `gigradar run` | `[--once]` | Runs the background multi-platform scheduler daemon (or single polling pass across all platforms with `--once`). |

---

## Architecture Overview

```
                      +-----------------------------+
                      |   Platforms (Polite Fetch)  |
                      | Mostaql | Khamsat | Freelancer |
                      +--------------+--------------+
                                     |
                                     v
                      +-----------------------------+
                      |  Stage 1: Deterministic     |
                      |  Rules Filter (rules.yaml)  |
                      +--------------+--------------+
                                     |
                                     v
                      +-----------------------------+
                      |  Stage 2: LLM Scoring       |
                      |  (gemini-3.5-flash-lite)    |
                      +--------------+--------------+
                                     |
                                     v
                      +-----------------------------+
                      |  Stage 3: Pitch Generation  |
                      |  (gemini-3.8-flash)         |
                      +--------------+--------------+
                                     |
                                     v
                      +-----------------------------+
                      |  Human Telegram Approval    |
                      |  (AUTO_SUBMIT = False)      |
                      +-----------------------------+
```

---

## Code Quality & Verification

Run the test suite and quality linters:

```bash
# Run all unit tests with strict error policy (offline, sockets blocked):
uv run pytest -W error

# Linting & Formatting:
uv run ruff check .
uv run ruff format --check .

# Strict typechecking:
uv run mypy src tests
```
