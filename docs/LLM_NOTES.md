# GigRadar: LLM Architecture & Gemini API Notes

This document contains implementation details regarding the Google Gemini API integration for GigRadar (Master Prompt Section 6.3b).

---

## 1. SDK & Runtime Environment

- **Official SDK:** `google-genai` (v2.31.0).
- **SDK Status:** Fully tested in this environment (`src/` and `tests/` pass with zero warnings).
- **Client Initialization:**
  ```python
  from google import genai
  client = genai.Client(api_key=settings.gemini_api_key.get_secret_value())
  ```
- **Async Execution:** Asynchronous operations are supported via `client.aio.models`.

---

## 2. Models & Live Discovery

- **Live Model Query Command:**
  When a live API key is configured in `.env`, the exact active models available to your key should be discovered and recorded using:
  ```python
  from google import genai
  client = genai.Client()
  for model in client.models.list():
      print(model.name)
  ```
- **Configured Defaults:**
  - `LLM_MODEL_SCORER`: `gemini-2.5-flash` *(UNVERIFIED until live query)*
  - `LLM_MODEL_PITCH`: `gemini-2.5-flash` *(UNVERIFIED until live query)*
- **Model Role:**
  - Flash-class model handles high-volume structured scoring.
  - Pitch generator uses the pitch model on approved bids.

---

## 3. Rate Limits & Pricing

> [!NOTE]
> Values below reflect current references and remain **UNVERIFIED** until confirmed directly in your Google AI Studio console or via live API response headers.

### Free Tier Limits (Estimated)
- **RPM:** 10 RPM *(UNVERIFIED)*
- **RPD:** 250 RPD *(UNVERIFIED)*

### Paid Tier Pricing (Estimated for 2.5 Flash)
- **Input:** $0.30 per 1M tokens *(UNVERIFIED)*
- **Output:** $2.50 per 1M tokens *(UNVERIFIED)*

### GigRadar Conservative Defaults (Active)
To ensure the pipeline never hits quota exhaustion under unconfirmed limits, `Settings` and `.env.example` are locked to conservative bounds:
- `LLM_MAX_RPM = 10`
- `LLM_DAILY_CALL_BUDGET = 200`

---

## 4. Data Privacy Boundaries

On free tiers of AI Studio, prompt/response data may be used by Google for model improvement. Regardless of tier, GigRadar enforces strict architectural boundaries:
- **Never send private data:** No credentials, no DB strings, no Telegram messages, and no chat IDs.
- **Only public data:** Only public gig listings and approved public facts from `config/claims_allowlist.yaml` are sent to the LLM.

---

## 5. Native Structured Outputs (Tested & Verified)

Tested with `google-genai` v2.31.0 and Pydantic v2:

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

client = genai.Client(api_key="...")

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Analyze gig...",
    config={
        "response_mime_type": "application/json",
        "response_schema": GigScoreSchema,
    },
)

# Parsed instance directly available:
score: GigScoreSchema = response.parsed
```

---

## 6. Graceful Degradation Strategy

When rate limits (HTTP 429) or daily budget are reached:
1. Never drop gigs or crash the background scheduler.
2. Mark rule-passed gigs with an `unscored` badge.
3. Deliver the card to Telegram with an on-demand **"Score now"** button.
4. Notify the owner via Telegram once per day upon quota exhaustion.
