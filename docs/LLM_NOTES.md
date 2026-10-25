# GigRadar: LLM Architecture & Gemini API Notes

This document contains empirical findings and architectural rules for Google Gemini API integration in GigRadar.

---

## 1. SDK & Runtime Environment

- **Official SDK:** `google-genai` (v2.31.0).
- **Client Initialization:**
  ```python
  from google import genai

  client = genai.Client(api_key=settings.gemini_api_key.get_secret_value())
  ```
- **Async Execution:** Asynchronous generation is supported via `client.aio.models.generate_content(...)`.

---

## 2. Models & Empirical Verification

### Verified Working Models (Live 1-Token Generation Tested)
The following models have been verified by live generation against real API keys:
- **`gemini-3.8-flash`**: High capability, recommended default for proposal pitch generation (`LLM_MODEL_PITCH`).
- **`gemini-3.7-flash`**: High capability flash model.
- **`gemini-3.6-flash`**: High capability flash model.
- **`gemini-3.5-flash`**: Balanced speed and quality.
- **`gemini-3.5-flash-lite`**: Ultra-fast, cost-effective Flash-Lite model, recommended default for Stage 2 scoring (`LLM_MODEL_SCORER`).
- **`gemini-3.1-flash-lite`**: Fast low-latency variant.

> [!IMPORTANT]
> **Strict Model Identifier Rules:**
> - Do **not** use `-latest` aliases (e.g., `gemini-flash-latest`), as their underlying targets shift over time without pinning.
> - Do **not** use `-preview` models in production.
> - **`gemini-2.5-flash` Deprecation:** `gemini-2.5-flash` is no longer available to new users and returns HTTP 404. All defaults have been migrated to Gemini 3.x generation (`gemini-3.5-flash-lite` for scorer, `gemini-3.8-flash` for pitch).

---

## 3. Active Defaults in GigRadar

Configured in `src/gigradar/core/settings.py` and `.env.example`:
- `LLM_MODEL_SCORER = "gemini-3.5-flash-lite"`
- `LLM_MODEL_PITCH = "gemini-3.8-flash"`
- `LLM_MAX_RPM = 10`
- `LLM_DAILY_CALL_BUDGET = 200`

---

## 4. Rate Limits & Console Visibility

> [!WARNING]
> **Per-Model Rate Limits (UNVERIFIED):**
> Specific RPM, RPD, and TPM limits per model tier are only visible in the Google AI Studio console for your account. They are not exposed via a standard programmatic metadata API.
> - Free-tier limits are marked **UNVERIFIED** (estimated ~10-15 RPM, ~200-250 RPD depending on region and account status).
> - GigRadar enforces client-side safety bounds via `LLM_MAX_RPM=10` and `LLM_DAILY_CALL_BUDGET=200` to prevent quota exhaustion.

---

## 5. Data Privacy & Free-Tier Policy

Google's Terms of Service state that prompts and responses submitted on the AI Studio free tier may be reviewed and used by Google to improve its products and services.

To ensure absolute privacy:
- **Only public gig text:** GigRadar sends **only public project listings and descriptions** retrieved from public freelance platforms to the Gemini API.
- **No private user data:** No personal credentials, database connection strings, local filesystem paths, Telegram messages, chat IDs, or private correspondence are ever sent to the LLM.
- **Fact-grounded pitches:** Pitches draw strictly from publicly disclosed CV facts in `config/claims_allowlist.yaml` and verified public portfolio items in `config/portfolio.yaml`.

---

## 6. Native Structured Outputs Pattern

Tested with `google-genai` and Pydantic v2:

```python
from google import genai
from pydantic import BaseModel, Field


class GigScoreSchema(BaseModel):
    match_score: int = Field(ge=0, le=100)
    domain: str
    work_type: str
    tier: str
    feasibility: str
    reasoning: str


client = genai.Client(api_key=api_key)

response = client.models.generate_content(
    model="gemini-3.5-flash-lite",
    contents="Analyze gig...",
    config={
        "response_mime_type": "application/json",
        "response_schema": GigScoreSchema,
    },
)

# Parsed Pydantic instance directly accessible:
score: GigScoreSchema = response.parsed
```
