# GigRadar: Master Build Prompt

> **Do not paste this whole file into chat.** Save it in the repo as `docs/MASTER_PROMPT.md` and start each Antigravity session with the short bootstrap prompt (`gigradar_bootstrap_prompt.md`), which tells the agent to read this file. This saves AI quota, because the agent reads the file once instead of the text being re-sent every session.

---

## 0. How you (the agent) must work

You are building **GigRadar**, a multi-layer automation system, from scratch, in this empty repository.

1. **In the very first session, produce a short implementation plan** (one screen) that maps to the phases in section 9. In every later session, write a plan of at most ~10 lines for the current phase only. Do not write code before the plan is shown.
2. **Work one phase at a time.** At the end of each phase: run the tests, update `docs/PROGRESS.md`, commit, then **stop and wait for me to say "continue"**. Do not start the next phase on your own.
3. Maintain `docs/PROGRESS.md` continuously: phase status, decisions made and why, open questions, known issues, how to run what exists so far. A reviewer reading only this file should understand the state of the project.
4. Make small, descriptive commits (`feat(ingest): ...`, `test(filter): ...`).
5. If something is ambiguous, pick the simplest reasonable option, record it in `docs/PROGRESS.md` under "Decisions", and continue. Only stop to ask when it blocks progress or involves credentials, money, or account risk.
6. **Never guess website structure.** Before writing any selector, open the real page, inspect the real HTML, and save sample pages as test fixtures (section 6.1).
7. **Work economically (my AI quota is limited).** One phase per session. Read `docs/PROGRESS.md` instead of re-reading the whole repo. Open only the files you need. Keep files small and focused. Run the tests for the code you touched, and the full suite once at the end of the phase. Use the browser tool only for platform discovery (Phases 1 and 1b). Never paste huge outputs into the chat; summarize them. Do not generate large amounts of speculative code beyond the current phase.
8. **Always leave a clean handoff.** If you sense you are running out of quota or context, stop at a safe point: commit, and write a "Handoff" section in `docs/PROGRESS.md` (what is done, what is half-done, exact next steps), so a fresh session can resume with no loss.

---

## 1. Mission

A background system that, for freelancing platforms (first **Mostaql** and **Khamsat** via scrapers, then **Freelancer.com** via its official API, later others):

1. **Watches** new projects/requests in near real time.
2. **Extracts** structured data from each gig.
3. **Classifies** whether the gig fits the owner (cheap rules first, then LLM scoring).
4. **Reports** matching gigs instantly to the owner on Telegram with Approve / Skip buttons.
5. On approval, **generates a tailored pitch** for that exact gig.
6. Sends the pitch back for human verification (Send / Edit / Regenerate / Cancel).
7. On confirmation, **submits the bid** (or, if auto-submit is disabled, delivers a copy-ready package plus the direct link).
8. **Logs everything** (gig, score, decision, pitch, outcome) so the system can be tuned and later learn from the owner's decisions.

**The only human actions are:** verifying the gig (Approve/Skip) and verifying the pitch (Send/Edit). Everything else runs unattended.

### Non-negotiables

- **Truthfulness:** pitches may only claim skills and projects listed in `config/claims_allowlist.yaml`. The system must never invent experience, clients, results, or certifications. This is enforced by a validator (section 6.6), not just by prompt wording.
- **Human-in-the-loop:** nothing is ever sent to a platform without an explicit tap from the owner.
- **Polite scraping:** respect rate limits, use jitter, back off on errors, identify nothing as a bot-farm, no parallel hammering. Check each site's `robots.txt` and terms and record findings in `docs/PLATFORM_NOTES.md`.
- **Account safety first:** auto-submit via browser automation is **OFF by default** behind a feature flag (`AUTO_SUBMIT=false`). Build it last (Phase 9) and clearly document the ToS/ban risk in the README.
- **No secrets in git.** `.env`, session cookies, and the SQLite DB are git-ignored.

---

## 2. Owner profile (source of truth for classification and pitches)

**Hany Elashry**, ML engineer based in Egypt, junior level, B.Sc. student (Navigation & Space Technology), Arabic native, English C1. Works on Mostaql and Khamsat (Arabic clients, many mixed Arabic/English briefs).

### Skill tiers (drive the classifier's feasibility rating)

**Tier A: core strengths (accept confidently):**
- Python (advanced), NumPy (expert), Pandas, SQL
- Classical/tabular ML: scikit-learn, XGBoost, feature engineering, imbalanced classification, threshold tuning, hyperparameter search
- Data engineering: ETL pipelines, PostgreSQL/MySQL/MongoDB, SQLAlchemy ORM, schema design, data cleaning, deduplication
- Web scraping and data collection pipelines
- Model deployment: FastAPI REST APIs, Streamlit dashboards, Railway / Streamlit Cloud, environment-based config
- Dashboards and visualization: Matplotlib, Plotly, Streamlit
- From-scratch ML in NumPy (forward/backward pass derivations)
- Signal processing / DSP / FMCW radar simulation, MATLAB

**Tier B: actively growing, accept when scope is standard (PyTorch/DL):**
- PyTorch fundamentals, CNNs, custom `Dataset`/`DataLoader` training pipelines
- Computer vision: image classification, transfer learning/fine-tuning pretrained models (ResNet, EfficientNet, etc.), basic object detection (e.g. YOLO usage/fine-tuning), OCR integration
- NLP: text classification, sentiment analysis, embeddings, using pretrained transformers (HuggingFace) for fine-tuning or inference, Arabic NLP basics
- LLM application work: RAG, prompt pipelines, API integration (acceptable but flag as `llm_wrapper`, often low-paying)

**Tier C: out of reach for now (reject or mark `stretch_risky`):**
- Novel research, training large models from scratch, large-scale distributed training
- Production MLOps at scale, Kubernetes, enterprise deployments
- Mobile/edge deployment, real-time video at scale, reinforcement learning projects
- Anything needing skills not in Tiers A/B (pure web dev, mobile apps, design, writing, WordPress, etc.)

### Hard rejects (auto-skip, never shown)
- Homework / assignment / thesis / exam solving ("do my project for my university")
- Unpaid trials, "test task first", or "free sample"
- Pure web development / WordPress / Shopify / mobile apps with no ML or data component
- Budgets below the minimum (configurable, default **$25**) unless scope is trivially tiny
- Gigs requiring guaranteed accuracy ("99% guaranteed") with no dataset
- Gigs asking to bypass platform rules, fake reviews, spam bots, account farming, scraping personal data illegally, cracking, etc.

All of this lives in editable files, not hard-coded:
`config/profile.yaml`, `config/rules.yaml`, `config/claims_allowlist.yaml`, `config/portfolio.yaml`.

### `config/portfolio.yaml` (seed it with exactly these, tagged for retrieval)

```yaml
projects:
  - id: sky_spy
    title: "Sky-Spy: Exoplanet classification (NASA Space Apps, 3rd place)"
    tags: [tabular_ml, xgboost, classification, fastapi, streamlit, deployment, hackathon, team_lead]
    one_liner: "Led a team to 3rd place building a tuned XGBoost exoplanet classifier from Kepler data, deployed as a FastAPI backend plus Streamlit dashboard."
  - id: kessler_shield
    title: "Kessler-Shield: orbital collision early-warning"
    tags: [tabular_ml, xgboost, imbalanced_data, threshold_tuning, fastapi, streamlit, deployment, mlops_debugging]
    one_liner: "XGBoost pipeline handling ~1:1300 class imbalance without oversampling via precision-recall threshold tuning; deployed as two independent cloud services and debugged a train/serve library-version mismatch."
  - id: ticketsense
    title: "TicketSense: ETL pipeline for support tickets"
    tags: [data_engineering, etl, postgresql, sqlalchemy, data_cleaning, schema_design]
    one_liner: "Normalized a flat dataset into a relational schema, fixed 441 duplicate customers and unresolved template placeholders, and built a modular ETL pipeline with SQLAlchemy."
  - id: ml_blueprint
    title: "The ML Blueprint: from-scratch ML in NumPy"
    tags: [ml_fundamentals, numpy, neural_network, math]
    one_liner: "Derived core ML algorithms from first principles, including a neural network with manual forward and backward passes."
  - id: fmcw_radar
    title: "FMCW Radar Simulation Engine (ongoing)"
    tags: [signal_processing, dsp, radar, cfar, cnn, simulation]
    one_liner: "Leading the DSP pipeline of a 4-person team; completed range-velocity-angle data cube extraction, now working on CFAR detection and CNN-based target classification."
```

### `config/claims_allowlist.yaml`
Seed with the facts above. Include **honest wording** for deep learning, e.g.:
> "I work with PyTorch and have built CNN training pipelines with custom datasets; I'm currently deepening my deep-learning skills."
Do **not** allow phrases like "years of deep learning experience", "production DL systems", "worked with clients", "senior", or any number of years or clients unless I add them myself.

---

## 3. Architecture

```
 ┌────────────┐   ┌───────────┐   ┌──────────┐   ┌──────────────┐
 │ Platform   │──▶│ Dedupe +  │──▶│ Stage 1  │──▶│ Stage 2 LLM  │
 │ scrapers   │   │ Storage   │   │ rules    │   │ scorer       │
 │ (plugins)  │   │ (SQLAlch.)│   │ filter   │   │ (structured) │
 └────────────┘   └───────────┘   └──────────┘   └──────┬───────┘
      ▲ scheduler                                        │ score ≥ threshold
      │ (APScheduler)                                    ▼
 ┌────┴───────────────────────────┐              ┌──────────────┐
 │ Outcome tracking / analytics   │◀─────────────│ Telegram bot │ Approve/Skip
 └────────────────────────────────┘              └──────┬───────┘
                                                        │ Approve
                                                        ▼
                                  ┌──────────────┐  ┌──────────────┐
                                  │ Submitter    │◀─│ Pitch gen +  │ Send/Edit
                                  │ (flagged)    │  │ validator    │
                                  └──────────────┘  └──────────────┘
```

### Repo layout

```
gigradar/
├─ config/                 # profile.yaml, rules.yaml, portfolio.yaml, claims_allowlist.yaml, platforms.yaml
├─ docs/                   # MASTER_PROMPT.md, PROGRESS.md, PLATFORM_NOTES.md, ARCHITECTURE.md
├─ src/gigradar/
│  ├─ core/                # settings (pydantic-settings), logging, models (pydantic), exceptions
│  ├─ db/                  # SQLAlchemy models, session, repositories, alembic migrations
│  ├─ platforms/           # base.py (interface) + mostaql/, khamsat/, freelancer/ (each: client, parser, submitter)
│  ├─ pipeline/            # orchestrator, dedupe, scheduler jobs
│  ├─ classify/            # rules_filter.py, llm_scorer.py, schemas.py, prompts/
│  ├─ pitch/               # generator.py, retrieval.py, validator.py, prompts/
│  ├─ bot/                 # telegram app, handlers, keyboards, message formatting
│  ├─ submit/              # playwright submitters (flagged), dry-run mode
│  ├─ analytics/           # stats, outcome tracking, export for future ML
│  └─ cli.py               # typer CLI: run, scrape-once, classify-file, doctor, stats
├─ tests/                  # unit + fixtures/html/*.html + golden LLM cases
├─ scripts/
├─ .env.example
├─ pyproject.toml          # use uv or pip-tools; pin versions
├─ Dockerfile, docker-compose.yml
└─ README.md
```

### Tech stack
Python 3.11+, `httpx` (async), `selectolax` or BeautifulSoup+lxml, Playwright (only where needed), SQLAlchemy 2.x + Alembic (SQLite by default, **PostgreSQL-ready via `DATABASE_URL`**), Pydantic v2, APScheduler (async), `python-telegram-bot` v20+ (async), the official `google-genai` SDK (Gemini API) for LLM calls, `tenacity` for retries, `structlog` or stdlib logging (JSON option), `typer`, `pytest` + `pytest-asyncio` + `respx`, `ruff` + `mypy`. The LLM provider must sit behind an interface (`LLMClient`) with Gemini as the default implementation, so another provider can be added later without touching the pipeline.

---

## 4. Data model (SQLAlchemy, normalized)

- **platforms**(id, name, base_url)
- **gigs**(id, platform_id FK, external_id, url, title, description, budget_min, budget_max, currency, budget_usd_est, bids_count, posted_at, deadline_text, client_name, client_stats_json (hire rate, rating, projects posted if visible), category_raw, tags_raw_json, language (ar/en/mixed), raw_html_hash, first_seen_at, last_seen_at) with **UNIQUE(platform_id, external_id)**
- **gig_snapshots**(id, gig_id FK, bids_count, seen_at): track bid-count changes over time
- **classifications**(id, gig_id FK, stage ('rules'|'llm'), passed bool, rule_hits_json, match_score, domain, work_type, tier, feasibility, red_flags_json, missing_info_json, suggested_price_usd, est_hours, reasoning, model, prompt_version, tokens_in, tokens_out, created_at)
- **decisions**(id, gig_id FK, decision ('approved'|'skipped'|'expired'), decided_at, skip_reason nullable)
- **pitches**(id, gig_id FK, version, language, body, bid_price, delivery_days, questions_json, projects_used_json, validator_report_json, status ('draft'|'approved'|'sent'|'cancelled'), model, prompt_version, created_at)
- **submissions**(id, pitch_id FK, method ('manual'|'auto'), status, error, submitted_at)
- **outcomes**(id, gig_id FK, status ('no_reply'|'replied'|'interview'|'won'|'lost'), updated_at, notes)
- **scrape_runs**(id, platform_id, started_at, finished_at, gigs_found, gigs_new, errors_json)

Use repository classes. Every write path must be idempotent. Alembic migration from day one.

---

## 5. Configuration (`.env.example` + yaml)

`.env`: `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_CHAT_ID` (bot ignores everyone else), `DATABASE_URL`, `LLM_MODEL_SCORER` (a fast, cheap Flash-class model), `LLM_MODEL_PITCH` (a stronger model, set after testing), `LLM_DAILY_CALL_BUDGET`, `LLM_MAX_RPM`, `AUTO_SUBMIT=false`, `SCORE_THRESHOLD=65`, `POLL_INTERVAL_SECONDS_MOSTAQL=120`, `POLL_INTERVAL_SECONDS_KHAMSAT=180`, `POLL_INTERVAL_SECONDS_FREELANCER=120`, `FREELANCER_OAUTH_TOKEN` (optional, only needed for authenticated endpoints or API bidding), `FREELANCER_MONTHLY_BID_LIMIT` (optional, for the bid-quota counter), `LOG_LEVEL`.

`config/platforms.yaml`: per-platform enabled flag, listing URLs, poll interval, jitter range, max pages per run, user-agent, timeout.

`config/rules.yaml`: include keywords (Arabic + English, with normalization for Arabic: strip tashkeel, normalize alef/ya/ta marbuta), exclude keywords, min budget, max existing bids, max gig age in minutes, hard-reject patterns, category allow/deny lists. Every rule match must be recorded in `rule_hits_json` so I can see *why* something passed or failed.

Include-keyword families to seed (extend them yourself, both languages):
- ML/DL: machine learning, deep learning, تعلم آلي, تعلم الة, تعلم عميق, ذكاء اصطناعي, نموذج, تدريب نموذج, model training, neural network, شبكة عصبية, PyTorch, TensorFlow, Keras, scikit-learn, XGBoost, fine-tune, تحسين نموذج, classification, تصنيف, regression, prediction, تنبؤ, forecasting, time series, anomaly detection
- CV: computer vision, رؤية حاسوبية, image classification, تصنيف صور, object detection, كشف الكائنات, YOLO, OCR, segmentation, face recognition (flag for ethics review), CNN
- NLP: NLP, معالجة اللغة الطبيعية, sentiment, تحليل المشاعر, text classification, تصنيف نصوص, transformers, BERT, embeddings, Arabic NLP, chatbot (flag as likely llm_wrapper), RAG, LLM, summarization
- Data: ETL, data pipeline, data cleaning, تنظيف بيانات, scraping, سحب بيانات, web scraping, PostgreSQL, SQL, pandas, dashboard, لوحة تحكم, Streamlit, Power BI (only if with ML/Python), data analysis, تحليل بيانات
- Backend/deploy: FastAPI, REST API, deploy model, نشر نموذج, Docker

---

## 6. Module specifications

### 6.1 Platform plugins (`src/gigradar/platforms/`)

Common interface:

```python
class PlatformClient(Protocol):
    name: str
    async def list_new_gigs(self, since: datetime | None) -> list[GigStub]: ...
    async def fetch_gig_detail(self, stub: GigStub) -> Gig: ...
    async def health_check(self) -> HealthReport: ...   # detects layout drift
```

Requirements:
- **Discovery step first (Phase 1):** use a browser/fetch tool to open the real listing and detail pages of Mostaql (projects listing) and Khamsat (buyer requests / community requests). Document in `docs/PLATFORM_NOTES.md`: URLs, pagination, whether login is needed, whether content is server-rendered or JS-rendered, how IDs appear in URLs, how budgets/bid counts/time are displayed (Arabic digits, relative dates like "منذ 5 دقائق"), robots.txt/ToS notes. **Save real HTML samples into `tests/fixtures/html/`** (strip personal data).
- Parsers must be **pure functions** (`html -> Gig`) tested against fixtures, so layout changes are caught by tests, not production.
- Normalize Arabic-Indic digits to ASCII, parse relative Arabic timestamps to UTC datetimes, parse budget ranges and currency, detect gig language.
- Fetch list pages first; fetch detail pages **only for gigs not already in the DB**.
- Polite behavior: per-platform async rate limiter, jittered intervals, exponential backoff with `tenacity`, honor 429/503 `Retry-After`, circuit breaker that pauses a platform for N minutes after repeated failures and alerts me on Telegram.
- `health_check` runs a parse on a known page shape and alerts if required fields come back empty (layout drift detection).
- Use Playwright **only** if pages require JS or login; reuse a persisted browser context; never store credentials in code.

### 6.1b Freelancer.com plugin (official API, Phase 1b)

**Why this platform:** it has an official, documented REST API, so there is no HTML scraping and the lowest ban risk of any platform here. It has high project volume (mostly English, many in USD), which makes it a good source of first reviews. Platform order is: Mostaql → Khamsat → Freelancer.com.

**Facts found in preliminary research. Re-verify every one against the official developer docs before coding:**
- The REST API root is reported as `https://www.freelancer.com/api/projects/0.1/`, and searching *active* projects reportedly works **without** an OAuth token.
- Only active projects are reachable without login. Paging reportedly stops at an offset of roughly 4,990, so poll newest-first with small pages and never page deep.
- Bid lists and some client details require authentication.
- Thousands of projects are posted per day, so **server-side filtering is mandatory**, not optional.

**Requirements:**
1. **Discovery first.** Read the official Freelancer developer documentation and record in `docs/PLATFORM_NOTES.md`: endpoints, query parameters (keyword, skill/job IDs, price range, language, sort order), response fields, rate limits, auth model, and API terms of use. Save real JSON responses (personal data stripped) into `tests/fixtures/json/`. Never hard-code field names from memory; use the ones you verify.
2. **Implementation:** `FreelancerClient` implements the same `PlatformClient` interface using `httpx` only (no Playwright). The parser is a pure function `json -> Gig`, tested against the saved fixtures. Map: project id → `external_id`, project URL, title, description, budget min/max, currency, fixed vs hourly, bid count, posted time (convert from the API's timestamp to UTC), and client info (country, payment-verified, rating) when the API provides it.
3. **Currency normalization:** budgets arrive in many currencies. Store the original amount and currency, and compute `budget_usd_est` using exchange-rate data from the API if it exposes it, otherwise `config/fx.yaml` refreshed daily. Hourly projects must be stored as hourly ranges, and the scorer prompt must handle hourly vs fixed pricing.
4. **Server-side filtering (cuts volume before anything is fetched or scored):** query using the English keyword families from `config/rules.yaml` and the matching Freelancer skills/categories (discover the exact IDs: e.g. Python, Machine Learning, Deep Learning, Data Science, NLP, Computer Vision, Web Scraping, SQL, Data Processing/ETL), sorted newest first. Merge results from multiple queries and dedupe by project id. Exclude contests, NDA-only, "local job" and recruiter-style listings.
5. **Platform-specific thresholds** in `config/platforms.yaml` (override the global defaults): `max_existing_bids` default **40** (projects here fill with bids very quickly), a shorter `max_gig_age_minutes`, a higher `min_budget_usd`, and use "client payment verified" as a quality signal in the scorer when available.
6. **Pitch rules for this platform:** English only, concise (find the real bid-text length limit and store it in `platforms.yaml`), same structure and honesty rules as section 6.5. A bid consists of amount, delivery period in days, and proposal text, which the pitch generator already outputs.
7. **Bid quota awareness:** Freelancer accounts have limited bids per period (verify the rules for my membership). Add a bid counter (`/bids`) using the API if it exposes remaining bids, otherwise `FREELANCER_MONTHLY_BID_LIMIT` plus local counting. The Telegram gig card shows a warning when the quota is low so I can be more selective.
8. **Submission:** default is the manual-send package plus direct link, same as other platforms. If auto-submit is ever enabled (Phase 9, flag OFF by default), Freelancer bids go through the **official API with OAuth** (verify the bid endpoint and scopes in the docs), never through browser automation. The token lives in `.env`, is never logged, and uses the minimum scopes.
9. **Done when:** `gigradar scrape-once freelancer` prints real parsed gigs with USD budget estimates, parser tests pass against the JSON fixtures, and `docs/PLATFORM_NOTES.md` documents the verified API behavior, limits, and terms.

### 6.2 Stage 1: rules filter (`classify/rules_filter.py`)
Deterministic, fast, fully explainable. Output `RuleResult(passed, hits, reject_reason)`. Order: hard rejects → age/bids/budget limits → keyword families → category lists. Must have table-driven unit tests with Arabic and English cases, including tricky ones ("نموذج" meaning a form/template vs. ML model, "تدريب" meaning a training course). Ambiguous cases pass through to Stage 2 rather than being dropped.

### 6.3 Stage 2: LLM scorer (`classify/llm_scorer.py`)
Input: gig fields + owner profile (tiers, refusals, rate hints). Output validated against a Pydantic schema (retry once on invalid JSON, then mark `scoring_failed` and alert):

```json
{
  "match_score": 0,
  "domain": "tabular_ml | deep_learning | computer_vision | nlp | llm_app | data_engineering | scraping | deployment_backend | signal_processing | dashboard_viz | other",
  "work_type": "real_ml | llm_wrapper | fake_ai | academic | data_task | other",
  "tier": "A | B | C",
  "feasibility": "easy | doable | stretch | out_of_reach",
  "language": "ar | en | mixed",
  "red_flags": ["no_dataset", "guaranteed_accuracy", "vague_metric", "scope_creep_risk", "budget_unrealistic", "needs_gpu_budget", "client_unverified", "free_trial_request", "academic_cheating"],
  "missing_info": ["dataset size?", "deployment target?"],
  "suggested_price_usd": 0,
  "est_hours": 0,
  "reasoning": "2-3 sentences, in English",
  "one_line_summary_ar": "ملخص قصير بالعربية"
}
```

Scoring rubric (put it in the prompt, versioned in `classify/prompts/scorer_v1.md`):
- Tier A skill fit 40 pts, Tier B fit 25 pts (cap if scope is non-standard), clarity of brief 15, budget vs estimated effort 15, client quality signals 5, minus red-flag penalties.
- Hard caps: `academic` → score ≤ 10; `fake_ai` → ≤ 25; Tier C → ≤ 30; `needs dataset that doesn't exist` → −20 and flag.
- The scorer must be **conservative on Tier B**: standard fine-tuning, classification, and inference-style CV/NLP work is OK; research or "train from scratch on millions of images" is not.
- Suggested price must account for the owner being junior (competitive but not underpriced), with the formula and assumptions shown in `reasoning`.

Cost and quota control for all LLM calls is specified in section 6.3b.

### 6.3b LLM provider, budget, and graceful degradation (Gemini)

**Decision:** the runtime LLM is the **Gemini API** (`google-genai` SDK), because I have a Google AI Pro subscription and no separate paid LLM account. A Flash-class model scores gigs (high volume, cheap) and a stronger model writes pitches (low volume, quality matters). Exact model IDs are config values, never hard-coded.

**Verify before relying on anything (record results in `docs/LLM_NOTES.md` during Phase 0):** the current model IDs, per-model rate limits (requests/minute, requests/day) on the key type I actually have, pricing if billing applies, structured-output (JSON schema) support, and the data-use terms of the tier I'm on. On free tiers, submitted content may be used by the provider to improve its products, so **only send public gig text and the public profile facts listed in this document; never send Telegram chat content, credentials, or private data.**

**Requirements:**
1. `GeminiClient(LLMClient)` uses native structured output (JSON response schema generated from the Pydantic models) instead of parsing free text. On a schema failure, retry once, then mark the gig `scoring_failed` and alert me.
2. A central **LLM gateway** wraps every call: async rate limiter honoring `LLM_MAX_RPM`, `tenacity` retry with exponential backoff on 429/5xx, per-call timeout, and a persisted **daily call counter** against `LLM_DAILY_CALL_BUDGET`. Log model, tokens in/out, latency, and cost estimate per call into the DB.
3. **Reduce calls before they happen:** cache by description hash, skip rule-rejected gigs, skip gigs that are too old or already over the bid cap, never score the same gig twice, and score only new or materially changed gigs.
4. **Graceful degradation:** when the daily budget or rate limit is exhausted, do not drop gigs and do not crash. Send rule-passed gigs to Telegram with an "unscored" badge and a **"Score now"** button, and queue them for scoring when quota returns. Tell me once per day when budget is exhausted, not per gig.
5. Pitch generation uses the pitch model only on Approve, so pitch calls are at most one or two per approved gig (draft plus an optional validator or regenerate pass).
6. `gigradar eval-scorer --model <id>` runs the golden set against a chosen model and prints agreement and token cost, so I can compare Flash-class models on **my** gigs (especially Arabic ones) before choosing, instead of guessing.
7. Prompt files must stay model-agnostic: plain instructions, explicit JSON schema, few-shot examples. No provider-specific tricks in the prompt text.

### 6.4 Telegram bot (`bot/`)
- Only responds to `TELEGRAM_ALLOWED_CHAT_ID`.
- **Gig card** (concise, mobile-friendly, bidirectional-text safe, escape MarkdownV2/HTML properly): platform, title, budget, bids so far, posted X minutes ago, score with a simple bar, domain/tier badge, one-line Arabic summary, top red flags, missing info, suggested price. Inline buttons: **✅ Approve · ⏭ Skip · 🧠 Why? · 🔗 Open**. Skip offers optional quick reasons (budget / not my field / too competitive / too risky), which are stored as training labels.
- **Pitch card** after Approve: pitch text, proposed price, delivery days, plus buttons **📤 Send · ✏️ Edit · 🔄 Regenerate (with optional instruction) · ❌ Cancel**. Edit = I reply with revised text and it replaces the draft. Show validator warnings prominently.
- **Send** → if `AUTO_SUBMIT=true` and the platform submitter is ready: dry-run preview, then submit. Otherwise send a clean copy-ready message with the direct link and a **"Mark as sent"** button.
- Follow-ups: buttons/commands to update outcome (`replied`, `won`, `lost`). Commands: `/stats` (today/week: seen, passed, approved, sent, replied, won), `/pause`, `/resume`, `/threshold 70`, `/status`, `/last`.
- Rate-limit alerts: batch low-score digests optionally (`/digest`) so I'm not spammed. Approved-worthy gigs (score ≥ threshold) alert immediately.
- State must survive restarts (pending approvals stored in the DB, not memory). Expire stale gig cards (e.g., gig closed or too many bids) and tell me.

### 6.5 Pitch generator (`pitch/`)
Inputs: full gig text, scorer output (missing info, price, hours), owner profile, **retrieved portfolio items** (tag-overlap + optional embeddings; pick the 1–2 most relevant, never dump all), claims allowlist, language of the gig.

Output pitch rules (put in `pitch/prompts/pitch_v1.md`):
1. Language: Arabic gig → Arabic pitch (clear, professional, natural Egyptian-friendly Modern Standard Arabic, not stiff); English gig → English; mixed → follow the dominant language of the description.
2. Structure: (a) one sentence restating the client's actual problem so they know it was read, (b) a concrete technical approach for *this* gig (name the method, e.g. "fine-tune a pretrained ResNet on your labeled images instead of training from scratch", "XGBoost with threshold tuning because your classes are imbalanced"), (c) one relevant past project from the portfolio, one sentence, (d) 1–2 sharp technical questions drawn from `missing_info`, (e) price, timeline, and a short closing. Respect platform length limits (store in `platforms.yaml`).
3. **Honesty:** only use facts from the allowlist and portfolio. For Tier B (PyTorch/CV/NLP) gigs use the honest wording from the allowlist. No fake years of experience, clients, ratings, or guarantees. Never promise accuracy figures.
4. No filler ("I am an expert with many years…"), no emoji spam, no copy-paste-looking template phrases. Each pitch must visibly depend on the gig's details.
5. Output JSON: `{pitch_text, bid_price, delivery_days, questions[], projects_used[], language}`.

**Validator (`pitch/validator.py`), a separate second pass:**
- Rule checks: length limits, no forbidden phrases (years/clients/guarantee/"100%"), no claims outside allowlist (LLM-as-judge comparing each factual claim to the allowlist and portfolio), language matches the gig, mentions at least one gig-specific detail, price within sane bounds of the suggested price.
- Output a report shown on the pitch card. A failed validation auto-regenerates once with the report as feedback, then shows me the draft with a visible warning.

### 6.6 Submitter (`submit/`, flagged, built last)
- Interface `Submitter.submit(gig, pitch, dry_run: bool)`.
- Playwright with a persisted logged-in context created by an interactive one-time `gigradar login <platform>` command. Never handle my password in code or logs.
- `dry_run=True` fills the form and screenshots it without clicking submit; the screenshot is sent to Telegram for my final check.
- Handle: captcha detected → stop and notify me to submit manually; layout drift → stop and notify; duplicate bid detected → skip; random human-like delays; never more than N submissions/hour (configurable).
- Default is off. README must state clearly that automated submission may violate platform terms and can risk the account.

### 6.7 Scheduler and orchestrator (`pipeline/`)
APScheduler jobs per platform (jittered intervals). One scheduling tick = list → dedupe → fetch detail for new → store → rules → LLM score (bounded concurrency) → notify. Jobs must be idempotent, crash-safe (a gig half-processed is resumed next tick), and log a `scrape_runs` row. Graceful shutdown. A `gigradar doctor` command checks env vars, DB connectivity, Telegram token, LLM key, and each platform's health.

### 6.8 Analytics and the "learn from me" layer (`analytics/`)
- Every approve/skip (+ skip reason) and the outcome of each sent pitch is stored.
- CLI `gigradar export-dataset` → CSV/Parquet of gig features + my decision + outcome.
- Later phase: embeddings of gigs, a lightweight classifier (logistic regression/XGBoost) trained on my own decisions, used to **re-rank or pre-filter**, compared against the LLM scorer with proper metrics (precision/recall at my approval threshold). Keep the LLM scorer as ground-truth fallback. Document the experiment in `docs/ML_EXPERIMENT.md` (this doubles as a portfolio piece).

---

## 7. Prompts to author (version them in files, never inline)

1. `classify/prompts/scorer_v1.md`: system prompt with profile tiers, rubric, hard caps, JSON schema, and 6+ few-shot examples (2 good matches, 1 llm_wrapper, 1 academic, 1 fake_ai, 1 out-of-reach). Arabic and English examples.
2. `pitch/prompts/pitch_v1.md`: as in 6.5, with 2 Arabic and 1 English example pitches that follow the structure. Examples must only use claims from the allowlist.
3. `pitch/prompts/validator_v1.md`: claim-extraction and allowlist comparison.
4. A **golden test set** in `tests/golden/`: ≥ 25 realistic gigs (mixed Arabic/English, including ≥ 5 English Freelancer.com-style gigs with USD/hourly budgets; I'll add real ones later) with expected domain/work_type/score range. A script `gigradar eval-scorer` reports agreement so prompt changes are measured, not guessed.

---

## 8. Engineering standards

- Type hints everywhere, `mypy --strict` on `src/`, `ruff` clean, `pytest` green before each phase ends.
- Structured logging with gig IDs; never log secrets or full personal data.
- Every external call (HTTP, LLM, Telegram) has timeouts, retries with backoff, and typed errors.
- Pure-function parsers and prompt builders so they're unit-testable without network.
- Mock the LLM in tests with recorded fixtures; a small number of opt-in live tests behind `--live`.
- README with quickstart (`uv sync`, `cp .env.example .env`, `gigradar doctor`, `gigradar run`), architecture diagram, config guide, and troubleshooting.
- Docker + docker-compose for always-on deployment (bot + scheduler in one process is fine); document running on a cheap VPS/Railway.
- Time handling: store UTC, display in `Africa/Cairo`.

---

## 9. Phases (stop after each one and wait for "continue")

**Phase 0: Foundation.** Repo scaffold, `pyproject.toml`, settings, logging, config loaders and validation, CLI skeleton, CI-style `make check` (ruff, mypy, pytest), `docs/PROGRESS.md`, `.env.example`.
Also create `docs/LLM_NOTES.md` with the verified Gemini SDK usage, model IDs, rate limits and data-use terms (section 6.3b).
*Done when:* `gigradar doctor` runs and reports config status (including a live Gemini key check); tests green; `docs/LLM_NOTES.md` exists.

**Phase 1: Platform discovery and parsers.** Inspect Mostaql and Khamsat for real, write `docs/PLATFORM_NOTES.md`, save HTML fixtures, implement the `PlatformClient` interface, parsers (pure functions), Arabic date/digit/budget normalization, rate limiter, backoff.
*Done when:* `gigradar scrape-once mostaql` and `... khamsat` print real parsed gigs; parser tests pass against fixtures; notes document robots/ToS findings.

**Phase 1b: Freelancer.com via official API.** Follow section 6.1b: API discovery and notes, JSON fixtures, `FreelancerClient`, parser, USD normalization, server-side filtering, platform-specific thresholds in `platforms.yaml`.
*Done when:* `gigradar scrape-once freelancer` prints real parsed gigs with USD budget estimates, the parser tests pass, and the API findings are documented in `docs/PLATFORM_NOTES.md`.

**Phase 2: Storage, dedupe, scheduling.** SQLAlchemy models + Alembic, repositories, idempotent upserts, bid-count snapshots, APScheduler jobs with jitter, `scrape_runs`, circuit breaker.
*Done when:* running `gigradar run` for 10 minutes stores new gigs without duplicates and survives a kill/restart.

**Phase 3: Stage 1 rules filter.** Rules engine, Arabic normalization, YAML rules, explainable hits, table-driven tests.
*Done when:* a CLI `classify-file`/replay over stored gigs shows pass/reject with reasons; ≥ 90% of obvious noise is dropped on the stored sample.

**Phase 4: Telegram alerts (no AI yet).** Bot skeleton, security gating, gig cards for rule-passed gigs, Approve/Skip/Open buttons with DB-persisted state, `/status`, `/pause`.
*Done when:* new real gigs arrive on my phone within one polling interval and my decisions are stored.

**Phase 5: LLM scoring.** `LLMClient` interface, scorer prompt v1, schema validation, caching, cost logging, score threshold, richer cards (score, red flags, missing info, price), "Why?" button, golden test set and `eval-scorer`.
*Done when:* the golden set agrees on domain/work_type ≥ 85% and the full live pipeline sends scored cards.

**Phase 6: Pitch generation and validation.** Portfolio retrieval, pitch prompt v1, generator, validator, regenerate/edit flows in Telegram, versioned pitches in DB.
*Done when:* Approve on a real gig yields a tailored, validated pitch in the right language within ~30 seconds, and the validator demonstrably catches a planted false claim in a test.

**Phase 7: Manual-send delivery and outcome tracking.** "Send" produces copy-ready package + link, "Mark as sent", outcome buttons, `/stats`, `export-dataset`.
*Done when:* I can complete the whole loop end-to-end by hand, and `/stats` reflects it.

**Phase 8: Hardening.** Layout-drift alerts, retries everywhere, Docker/compose, README, graceful shutdown, log rotation, `doctor` completeness, a 24h soak run with a report of errors/cost/latency.
*Done when:* it runs 24h unattended with no unhandled crashes and a written soak report.

**Phase 9: Optional auto-submit (flagged OFF).** Playwright session login for Mostaql/Khamsat, dry-run screenshot approval, captcha/drift stop conditions, hourly cap, README risk section. Freelancer.com bidding uses the official API with OAuth instead (section 6.1b item 8).
*Done when:* dry-run works on both platforms; live submit stays disabled unless I flip the flag.

**Phase 10: Learn from my decisions.** Embeddings (prefer a **local multilingual embedding model** so there is no API cost or quota use; verify a suitable model that handles Arabic and English), my-decisions classifier, evaluation vs. the LLM scorer, `docs/ML_EXPERIMENT.md`.

**Later:** more platforms (e.g. Upwork) through the same plugin interface.

---

## 9b. Model guidance per phase (for me, in Antigravity)

My Google AI Pro plan includes generous Flash-class usage and only a limited baseline quota for premium models, so I choose the model per phase. Agent: you do not choose it, but you should know why sessions are short and why handoff notes matter.

| Phase | Difficulty | Model to select |
|---|---|---|
| 0 Foundation | Low | Flash-class |
| 1 / 1b Discovery + parsers | **High** (real-world HTML/API, Arabic parsing) | Premium baseline model |
| 2 Storage + scheduler | Medium | Flash-class |
| 3 Rules filter | Low-medium | Flash-class |
| 4 Telegram alerts | Medium | Flash-class |
| 5 LLM scoring | **High** (prompt design + evaluation) | Premium baseline model |
| 6 Pitch + validator | **High** | Premium baseline model |
| 7 Manual-send + outcomes | Low | Flash-class |
| 8 Hardening | Medium | Flash-class |
| 9 Auto-submit (optional) | High | Premium baseline model |
| 10 Learn from decisions | Medium | Flash-class |

If a Flash-class session fails the same task twice, stop and report it so I can switch that one step to the premium model; do not loop.

---

## 10. Checkpoint protocol (end of every phase)

Report in this exact format, and also append it to `docs/PROGRESS.md`:

1. **What was built** (files and modules)
2. **How to run / verify it** (exact commands)
3. **Test results** (counts and anything skipped)
4. **Decisions made and why**
5. **Known issues / risks**
6. **Questions for me**
7. **Proposed next phase and any inputs you need from me**
8. **Handoff note** (3-5 lines a fresh session can start from)

Then stop.

## 11. Do not

- Do not skip the discovery step or invent selectors.
- Do not send anything to a platform automatically before Phase 9, and not even then unless the flag is on and I tapped Send.
- Do not claim skills, years, clients, or results outside the allowlist.
- Do not hard-code secrets, keywords, thresholds, or prompts in code; keep them in config or prompt files.
- Do not add features outside the current phase.
- Do not let a failing test or a noisy log pass silently; fix or document it.
