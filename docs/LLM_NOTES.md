# GigRadar: LLM Architecture & Gemini API Notes

This document contains verified details regarding the Google Gemini API integration for GigRadar, adhering to Section 6.3b of the Master Prompt.

---

## 1. SDK & Runtime Environment

- **Official SDK:** `google-genai` (v0.8.0+).
- **Previous/Legacy SDKs:** Do **not** use `google-generativeai`. The new official unified SDK is `google-genai`.
- **Initialization:**
  ```python
  from google import genai
  from google.genai import types

  client = genai.Client(api_key=settings.gemini_api_key.get_secret_value())
  ```
- **Async Support:** The SDK provides native async operations under `client.aio.models`.

---

## 2. Model Selection & Roles

The architecture splits LLM workloads into two distinct tiers:

| Role | Purpose | Default Config Model | Characteristics |
|---|---|---|---|
| **Stage 2 Scorer** | High-volume classification of rule-passed gigs | `gemini-2.5-flash` | Sub-second latency, cheap, strict JSON output support |
| **Pitch Generator** | High-quality tailored pitch generation on approval | `gemini-2.5-flash` (or `gemini-2.5-pro`) | Nuanced Arabic/English writing, adherence to claims allowlist |

> **Note:** Exact model IDs are strictly config-driven (`LLM_MODEL_SCORER` and `LLM_MODEL_PITCH` in `.env`), never hard-coded in python modules.

---

## 3. Rate Limits & Quotas

### Free Tier (Google AI Studio)
- **RPM (Requests Per Minute):** 15 RPM.
- **RPD (Requests Per Day):** 1,500 RPD.
- **TPM (Tokens Per Minute):** 1,000,000 TPM.

### Paid Tier / Pay-As-You-Go
- **RPM:** Typically 1,000+ RPM depending on project tier.
- **Cost:** ~$0.075 per 1M input tokens, ~$0.30 per 1M output tokens (Flash-class). Extremely economical for high-volume gig scanning.

### GigRadar Gateway Guardrails
1. **Local Async Rate Limiter:** Enforces `LLM_MAX_RPM` (default 15) using a token-bucket algorithm to prevent 429 HTTP errors.
2. **Daily Call Counter:** Tracks invocations against `LLM_DAILY_CALL_BUDGET` (persisted in DB/state).
3. **Pre-LLM Filtering:** Over 90% of noise is eliminated by Stage 1 deterministic rules (keywords, age, budget, existing bids) before touching the LLM.
4. **Content Deduplication:** Cache results by SHA-256 hash of gig description to never score identical gig text twice.

---

## 4. Data Privacy & Terms of Service

> [!IMPORTANT]
> **Data-Use Rules on Free Tier:**
> On the Google AI Studio Free Tier, prompts and responses may be logged and reviewed by human annotators to train Google models.
>
> **Enforced Architecture Boundaries:**
> - **Never send credentials, API keys, or database URLs.**
> - **Never send Telegram messages, chat histories, or user IDs.**
> - **Only send public gig postings** (already accessible on the open web).
> - **Only send public professional profile facts** listed in `config/claims_allowlist.yaml` and `config/profile.yaml`.

---

## 5. Native Structured Outputs (JSON Schema)

The Gemini API supports strict JSON schema enforcement natively:

```python
from google.genai import types
from pydantic import BaseModel

class GigScoreSchema(BaseModel):
    match_score: int
    domain: str
    work_type: str
    tier: str
    feasibility: str
    language: str
    red_flags: list[str]
    missing_info: list[str]
    suggested_price_usd: float
    est_hours: float
    reasoning: str
    one_line_summary_ar: str

config = types.GenerateContentConfig(
    response_mime_type="application/json",
    response_schema=GigScoreSchema.model_json_schema(),
    temperature=0.1,
)

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=["...prompt with gig text..."],
    config=config,
)
```

**Benefits:**
- Eliminates regex or markdown code-fence parsing.
- Model failure to adhere to the schema is caught immediately by the SDK.
- Combined with a single retry before marking `scoring_failed`.

---

## 6. Graceful Degradation Strategy

When rate limits (429) or the daily budget are reached:
1. **Do not crash and do not drop gigs.**
2. Mark rule-passed gigs with an `unscored` badge.
3. Deliver the card to Telegram with a **"Score now"** button for on-demand manual trigger.
4. Send an alert to the owner at most once per day when the daily quota is exhausted.
