# GigRadar: LLM Architecture & Gemini API Notes

This document contains verified details regarding the Google Gemini API integration for GigRadar, adhering to Section 6.3b of the Master Prompt. All facts are verified against official Google documentation (`ai.google.dev`) with sources and verification dates.

---

## 1. SDK & Runtime Environment

- **Official SDK:** `google-genai` (upgraded to v2.31.0+).
- **Source:** [https://ai.google.dev/gemini-api/docs/quickstart](https://ai.google.dev/gemini-api/docs/quickstart) *(Verified: 2026-10-17)*
- **Legacy SDK Status:** `google-generativeai` is deprecated. Only the unified `google-genai` package is supported.
- **Client Initialization:**
  ```python
  from google import genai
  client = genai.Client(api_key=settings.gemini_api_key.get_secret_value())
  ```
- **Async Execution:** Asynchronous calls are supported via `client.aio.models.generate_content(...)`.
  *(Verified: 2026-10-17 via SDK inspection)*

---

## 2. Model Selection & Roles

- **Source:** [https://ai.google.dev/gemini-api/docs/models/gemini](https://ai.google.dev/gemini-api/docs/models/gemini) *(Verified: 2026-10-17)*

| Role | Config Variable | Default Model ID | Verified Status & Notes |
|---|---|---|---|
| **Stage 2 Scorer** | `LLM_MODEL_SCORER` | `gemini-2.5-flash` | **VERIFIED (Active)**: Primary high-throughput Flash model for structured JSON scoring. Sub-second latency. |
| **Pitch Generator** | `LLM_MODEL_PITCH` | `gemini-2.5-flash` | **VERIFIED (Active)**: Can be upgraded to `gemini-2.5-pro` if nuanced reasoning on approved bids requires it. |
| **Alternative Fast** | (Optional override) | `gemini-3.5-flash-lite` | **VERIFIED (Active)**: Designed for cost efficiency and ultra-high throughput. |
| **Legacy Models** | `gemini-2.0-flash` | Deprecated / Shut down | **VERIFIED**: Deprecated and shut down on Google AI Studio API; do not use. |

---

## 3. Rate Limits & Quotas

- **Source:** [https://ai.google.dev/pricing](https://ai.google.dev/pricing) and [https://ai.google.dev/gemini-api/docs/rate-limits](https://ai.google.dev/gemini-api/docs/rate-limits) *(Verified: 2026-10-17)*

### Free Tier (Google AI Studio)
- **RPM (Requests Per Minute):** 15 RPM. *(Verified: 2026-10-17)*
- **RPD (Requests Per Day):** 1,500 RPD (resets midnight Pacific Time). *(Verified: 2026-10-17)*
- **TPM (Tokens Per Minute):** 1,000,000 TPM. *(Verified: 2026-10-17)*

### Paid Tier (Pay-As-You-Go / Tier 1)
- **RPM:** 1,000 RPM. *(Verified: 2026-10-17)*
- **TPM:** 4,000,000 TPM. *(Verified: 2026-10-17)*
- **Spend-Based Cap:** $10 per rolling 10-minute window for Tier 1. *(Verified: 2026-10-17)*

### Pricing (Gemini 2.5 Flash on Paid Tier)
- **Prompt / Input:** ~$0.075 per 1 million tokens (for prompts $\le$ 128k tokens). *(Verified: 2026-10-17)*
- **Output / Candidates:** ~$0.30 per 1 million tokens. *(Verified: 2026-10-17)*
- **Google AI Pro Subscription details for external API quota:** *UNVERIFIED* whether personal Google AI Pro consumer subscriptions increase AI Studio API developer project quotas automatically, or whether AI Studio requires linking Google Cloud billing for Pay-As-You-Go rates.

---

## 4. Data Privacy & Terms of Service

- **Source:** [https://ai.google.dev/terms](https://ai.google.dev/terms) and [https://ai.google.dev/pricing](https://ai.google.dev/pricing) *(Verified: 2026-10-17)*

> [!IMPORTANT]
> **Free Tier Terms:**
> When using free-of-charge API keys, prompts, responses, and related data may be logged and reviewed by human annotators to train and improve Google products.
>
> **Paid Tier (Pay-As-You-Go) Terms:**
> Data is **not** reviewed by humans and is **not** used to train Google models.
>
> **Strict GigRadar Privacy Guardrails:**
> - Never send credentials, database connection strings, or environment secrets to the API.
> - Never send Telegram chat messages or private user identity details.
> - Only send public gig titles and descriptions (already public on the freelance platforms).
> - Only send public professional profile facts from `config/claims_allowlist.yaml` and `config/profile.yaml`.

---

## 5. Native Structured Outputs (JSON Schema)

- **Source:** [https://ai.google.dev/gemini-api/docs/structured-output](https://ai.google.dev/gemini-api/docs/structured-output) *(Verified: 2026-10-17)*

The `google-genai` SDK natively supports Pydantic models in `response_schema` and automatically parses the output:

```python
from google import genai
from pydantic import BaseModel, Field

class GigClassification(BaseModel):
    match_score: int = Field(ge=0, le=100)
    domain: str
    work_type: str
    tier: str
    feasibility: str
    reasoning: str

client = genai.Client(api_key="...")

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Brief description of an ML classification gig...",
    config={
        "response_mime_type": "application/json",
        "response_schema": GigClassification,
    },
)

# Output is directly accessible as a validated Pydantic instance:
parsed_result: GigClassification = response.parsed
```

*(Verified: 2026-10-17)*

---

## 6. Graceful Degradation Strategy

When rate limits (HTTP 429) or daily budget are reached:
1. **Never drop gigs or crash the background scheduler.**
2. Mark rule-passed gigs with an `unscored` badge.
3. Deliver the card to Telegram with an on-demand **"Score now"** button.
4. Notify the owner via Telegram once per day upon quota exhaustion.
