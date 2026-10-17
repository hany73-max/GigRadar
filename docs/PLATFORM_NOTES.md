# GigRadar: Platform Discovery & Parsing Notes

This document contains empirical findings and technical discovery data for supported freelance platforms.

---

## 1. Mostaql (مستقل)

### 1.1 Technical Profile
- **Base URL:** `https://mostaql.com`
- **Listing URL:** `https://mostaql.com/projects`
- **Pagination:** Query parameter `?page=2`, `?page=3`, etc.
- **Rendering Model:** **Server-Side Rendered (SSR)**. Full project tables and details are present in the initial HTML response. No client-side hydration or JavaScript execution is required to read content.
- **Authentication:** Public listing and detail pages do **not** require login to read. (Only project submission / bidding requires an authenticated session).
- **Anti-Bot Protections:** Standard Cloudflare/Hsoub infrastructure. Plain `httpx` GET requests with a standard browser `User-Agent` receive clean HTTP 200 responses. No captchas or WAF challenges encountered on listing or project detail pages.

### 1.2 Robots.txt & Terms of Service
- **`robots.txt` (`https://mostaql.com/robots.txt`):**
  ```text
  User-agent: *
  Disallow: /search*
  Disallow: /ajax/
  ```
  - `/projects` (listing) and `/project/*` (details) are **explicitly allowed** (not disallowed).
- **Terms of Service (`https://mostaql.com/p/terms`):**
  - Section 3: Forbids automated project delivery, automated translation/design generation, or fraudulent activity.
  - Section 5: Standard prohibition against platform circumvention (off-platform payments/contact).
  - Courteous read-only inspection at low frequency honors Hsoub infrastructure constraints.

### 1.3 URL & Identifier Structure
- **Listing URLs:** `https://mostaql.com/projects`
- **Project Detail URLs:** `https://mostaql.com/project/{id}-{slug}`
  - Example: `https://mostaql.com/project/1286262-%D9%86%D9%82%D9%84-%D8%A7%D8%B3%D8%AA%D8%B6%D8%A7%D9%81%D8%A9-%D9%85%D9%88%D9%82%D8%B9-%D9%84%D9%83%D8%AA%D8%B1%D9%88%D9%86%D9%8A`
  - Canonical project identifier is the integer prefix directly following `/project/` (`r"/project/(\d+)"`).
  - Short URL `https://mostaql.com/project/1286262` automatically resolves/redirects to the canonical project page.

### 1.4 DOM Structure & Stable Selectors
- **Listing Container:**
  - Rows: `table.projects-table tbody tr.project-row`
  - Title & Link: `div.card--title h2 a` (`href` contains URL with external ID; text content is title).
  - External ID: Extracted from link href via regex `r"/project/(\d+)"`.
  - Brief Description: `p.project__brief a.details-url`
  - Posted Time: `<time datetime="YYYY-MM-DD HH:MM:SS" itemprop="datePublished">` (Provides machine-readable UTC/server timestamp directly in attribute, accompanied by relative Arabic text e.g. "منذ 10 دقائق").
  - Bids Count: Meta item `ul.project__meta li` containing "عرض" (e.g. `14 عرض`, `عرض واحد`, or `أضف أول عرض` indicating 0 bids).
  - Client / Poster Name: `ul.project__meta li bdi`
- **Detail Page:**
  - Title: `h1.heada__title [data-type="page-header-title"]`
  - Category: `ol.breadcrumb li[data-index="2"] a bdi`
  - Description: `div#projectDetailsTab div.text-wrapper-div`
  - Budget: `div[data-type="project-budget_range"] span` (e.g., `$50.00 - $100.00`)
  - Execution Duration: Meta row where label is `مدة التنفيذ` (e.g., `7 أيام`)
  - Skills / Tags: `ul.skills li.skills__item a.tag bdi`
  - Client Info:
    - Name: `h5.profile__name bdi`
    - Meta Table (`table.table-meta`):
      - Registration date (`تاريخ التسجيل`)
      - Hire rate (`معدل التوظيف`, e.g. `62.37%`)
      - Open projects (`المشاريع المفتوحة`)
      - In-progress projects (`مشاريع قيد التنفيذ`)

---

## 2. Khamsat (خمسات)

### 2.1 Technical Profile
- **Base URL:** `https://khamsat.com`
- **Requests Listing URL:** `https://khamsat.com/community/requests`
- **Pagination:** Query parameter `?page=2`, `?page=3`, etc.
- **Rendering Model:**
  - Listing: **Server-Side Rendered (SSR)**. The table of buyer requests (`table#forums_table`) is directly embedded in HTML.
  - Detail: Server-side rendered once past the edge layer, but sits behind an edge challenge.
- **Authentication:** Public listing does not require login.

### 2.2 Robots.txt & Terms of Service
- **`robots.txt` (`https://khamsat.com/robots.txt`):**
  - Disallows `/search*`, `/community/search*`, `/login*`, `/register*`, `/home/*`, `/ajax/*`, `/?show=*`.
  - `/community/requests` is **allowed**.
- **Terms of Service:**
  - Strictly requires transactions and agreements to take place within Khamsat.

### 2.3 Anti-Bot Protections & Edge Architecture Decision
- **Listing Page (`https://khamsat.com/community/requests`):**
  - Responds with **HTTP 200 OK** to `httpx` requests using standard browser headers. Sets `rack.session` cookie.
- **Detail Pages (`https://khamsat.com/community/requests/{id}-{slug}`):**
  - **AWS WAF Challenge:** Responds with **HTTP 202 Accepted** (`x-amzn-waf-action: challenge` with AWS WAF JS token challenge script `challenge.js`).
  - **Architectural Decision:** Per project safety and anti-bot rules, GigRadar does **not** use browser automation/Playwright or attempt to bypass the AWS WAF challenge. Khamsat requests are parsed **from listing pages only** over plain `httpx`. Fields that exist only on detail pages (e.g. extended descriptions or thread replies) remain `None`. Detailed pages are intentionally not fetched.

### 2.4 DOM Structure & Stable Selectors (Listing Page)
- **Requests Table:** `table#forums_table tbody tr.forum_post`
- **Row ID:** `tr#forum_post-{id}` (e.g. `forum_post-799121`)
- **Title & URL:** `td.details-td h3.details-head a.ajaxbtn`
  - URL format: `/community/requests/799121-slug`
  - ID pattern: `r"/community/requests/(\d+)"`
- **Buyer / User Name:** `td.details-td ul.details-list li a.user`
- **Posted Time:**
  - `<span dir="ltr" title="DD/MM/YYYY HH:MM:SS GMT">منذ X دقيقة</span>`
  - Contains exact GMT/UTC datetime in `title` attribute, plus relative Arabic string.
- **Last Reply / Activity:**
  - `td.d-lg-block div.o-media` contains the last responder's username and interaction timestamp.
- **Offers Count, Budget & Description (Listing Limitations):**
  - Khamsat listing rows expose only the request title, buyer username, posted timestamp, and last responder activity.
  - Listings do **not** display an offers/bids count, budget range, or extended description.
  - Consequently, `bids_count`, `budget_min`, `budget_max`, and `budget_usd_est` are parsed as `None` (unknown), and `description` is initialized from the request title/stub. In CLI listings, unknown bids count renders cleanly as `-`.

---

## 3. Shared Normalization Requirements

### 3.1 Arabic-Indic Digits to ASCII
- Arabic-Indic numerals (`٠١٢٣٤٥٦٧٨٩`) and Extended Arabic-Indic numerals (`۰۱۲۳۴۵۶۷۸۹`) must be mapped 1:1 to ASCII digits (`0-9`).
- Currency separators (Arabic comma `،` and standard comma `,`) and decimals (Arabic decimal separator `٫` vs period `.`) must be normalized.

### 3.2 Relative Arabic Timestamps to UTC
Platforms express relative time in Arabic phrasing:
- `منذ دقيقة` / `منذ دقيقتين` / `منذ X دقائق` / `منذ دقيقة واحدة`
- `منذ ساعة` / `منذ ساعتين` / `منذ X ساعات`
- `منذ يوم` / `منذ يومين` / `منذ X أيام`
- `منذ شهر` / `منذ شهرين` / `منذ X أشهر`
- Where `<time datetime="...">` (Mostaql) or `<span title="... GMT">` (Khamsat) exists, parse the explicit UTC timestamp first, falling back to relative string parsing when missing.

### 3.3 Budget Range & Currency
- Mostaql budgets are stated in USD ranges: `$25.00 - $50.00`, `$50.00 - $100.00`, etc.
- Khamsat requests typically default to base service pricing ($5 multiples) or mention budgets in request body text. Default `currency = "USD"`.

### 3.4 Language Detection
- Inspect title and description.
- Count Arabic Unicode code points (`[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]`) vs Latin alphabetic code points (`[a-zA-Z]`).
- Classify:
  - `ar`: Arabic character ratio > 70%
  - `en`: Latin character ratio > 70%
  - `mixed`: Neither exceeds 70% or contains substantial technical jargon in both.

---

## 4. Freelancer.com (Official REST API)

### 4.1 Technical Profile
- **Base URL:** `https://www.freelancer.com`
- **Official API Root:** `https://www.freelancer.com/api/projects/0.1/`
- **Developer Documentation Portal:** `https://developers.freelancer.com/`
- **Active Projects Endpoint Docs:** `https://developers.freelancer.com/docs/projects/projects#projects-get-3`
- **Jobs / Skills Endpoint Docs:** `https://developers.freelancer.com/docs/projects/jobs`
- **Currencies Endpoint Docs:** `https://developers.freelancer.com/docs/projects/currencies`
- **Rate Limiting Docs:** `https://developers.freelancer.com/docs/api-overview/rate-limiting`
- **Terms & Prohibited Integrations:** `https://developers.freelancer.com/docs/api-overview/types-of-integrations#header-prohibited-integrations`
- **Rendering Model:** **REST JSON API**. No HTML scraping, zero headless browser/Playwright required.
- **Authentication Model:**
  - Public search for active projects (`/projects/0.1/projects/active/`) works **unauthenticated** (HTTP 200).
  - Unauthenticated responses provide full project metadata (title, full description, budget ranges, currency, real-time exchange rates, submit timestamps, bid counts, skill tags, and upgrade flags).
  - Client / buyer personal data (`owner_id`, `owner_info`, detailed location, buyer KYC, client engagement, bids list) are hidden by Freelancer (`None` / empty) on unauthenticated requests.
  - Authenticated requests (required only for bidding or private client data) require OAuth 2.0 access token passed via `Freelancer-OAuth-v1: <token>` header.

### 4.2 Verified Endpoints & Query Parameters
- **Active Projects Search:** `GET https://www.freelancer.com/api/projects/0.1/projects/active/`
  - `query`: String keyword search filter.
  - `jobs[]`: Array of integer skill/job IDs (e.g. `?jobs[]=13&jobs[]=292`).
  - `project_types[]`: `fixed`, `hourly`.
  - `sort_field`: Criteria to sort results. Official choices in developer documentation are: `time_updated` (default newest first), `bid_count`, `bid_enddate`, `bid_avg_usd`.
    - *Note on `sort_field=submitdate`:* Empirical probing confirmed that `submitdate` is **not** an accepted value for `sort_field`; passing it causes the API to ignore the parameter and fall back to internal default order.
  - `reverse_sort`: Boolean ("If true, results appear in ascending order instead of descending order").
    - *Note:* Because default order for `time_updated` is descending (newest first), setting `reverse_sort=true` reverses it to **ascending** (oldest first, e.g. 2022-2025). Do **not** use `reverse_sort=true` when fetching newest projects.
  - `from_time`: Integer epoch timestamp (optional). Official docs specify: "Returns projects last updated after this time (inclusive)".
    - *Empirical Verification:* Setting `from_time = now - max_gig_age_minutes` server-side isolates projects posted/updated within the specified age window (confirmed returning active projects posted within minutes/hours).
  - `to_time`: Integer epoch timestamp (optional). Returns projects last updated before this time (inclusive).
  - `limit`: Number of projects per request (default 10, max 100).
  - `full_description`: `true` (ensures complete description text is returned rather than truncated preview).
  - `job_details`: `true` (expands full skill object with `name` and `category`).
  - *Status Filter on API:* Official documentation inspection confirms there is **no** `status` or `statuses[]` query parameter on `/projects/0.1/projects/active/`. The endpoint occasionally returns closed or archived projects present in the search cache; local exclusion of `status != "active"` is mandatory.
- **Skill / Job Directory:** `GET https://www.freelancer.com/api/projects/0.1/jobs/`
  - Query parameters: `job_names[]` (e.g. `?job_names[]=Python`).
  - Returns array of job objects with `id`, `name`, `category`, and `seo_url`.
- **Currencies Directory:** `GET https://www.freelancer.com/api/projects/0.1/currencies/`
  - Returns supported currencies with currency code, sign, and `exchange_rate` to USD.

### 4.3 Verified Freelancer Skill / Job IDs
Discovered and verified empirically via the `/projects/0.1/jobs/` endpoint:
- **Python:** `13`
- **Machine Learning (ML):** `292`
- **Deep Learning:** `1601`
- **Data Science:** `761`
- **Natural Language Processing:** `2833`
- **Computer Vision:** `1558`
- **Web Scraping:** `95`
- **SQL:** `68`
- **Data Processing:** `36`
- **Data Mining:** `334`

### 4.4 Verified Response Schema & Field Mapping to `Gig`
From real API responses returned by `/projects/0.1/projects/active/`:
- `id` (int) -> `Gig.external_id` (str)
- `seo_url` (str) -> `Gig.url`: `https://www.freelancer.com/projects/{seo_url}` (fallback: `https://www.freelancer.com/projects/{id}`)
- `title` (str) -> `Gig.title`
- `description` (str) -> `Gig.description` (fallback: `preview_description`)
- `type` (str) -> `"fixed"` or `"hourly"` (`Gig.project_type`)
- `budget.minimum` (float) -> `Gig.budget_min`
- `budget.maximum` (float) -> `Gig.budget_max`
- `currency.code` (str) -> `Gig.currency` (e.g. `"USD"`, `"GBP"`, `"EUR"`, `"INR"`)
- `currency.exchange_rate` (float) -> Live exchange rate to USD provided natively by the API.
  - USD rate is `1.0`.
  - `Gig.budget_min_usd`: `round(budget_min * exchange_rate, 2)` if `budget_min` exists, else `None`.
  - `Gig.budget_max_usd`: `round(budget_max * exchange_rate, 2)` if `budget_max` exists, else `None`.
  - Fixed projects: `budget_usd_est` is computed as the midpoint `round((budget_min_usd + budget_max_usd) / 2.0, 2)` when both exist, otherwise whichever exists.
  - Hourly projects: Stored as hourly rate ranges in `budget_min_usd` and `budget_max_usd`. `budget_usd_est` is set to `None`, relying on `project_type == "hourly"`.
- `bid_stats.bid_count` (int) -> `Gig.bids_count`
- `submitdate` (int unix timestamp) -> `Gig.posted_at`: `datetime.fromtimestamp(submitdate, tz=timezone.utc)`
- `jobs` (list[dict]) -> `Gig.tags_raw`: `[job["name"] for job in jobs if "name" in job]`
- `jobs[0].category.name` -> `Gig.category_raw`
- `language` (str) -> `Gig.language`: `"en"` for English, mapped via language detection for others.
- `client_stats`: Stores `{}` in unauthenticated mode since Freelancer hides owner details on unauthenticated endpoints.

### 4.5 Server-Side & Local Filtering Requirements
Per Master Prompt rules, the client applies strict filtering to discard irrelevant or risky listings:
- **Exclusions:**
  - `upgrades.NDA is True`: Exclude NDA projects.
  - `local is True` or `is_local is True`: Exclude on-site/local jobs.
  - `upgrades.recruiter is True` or `assisted is True`: Exclude recruiter-managed/fee listings.
  - `type == "contest"`: Exclude contests.
  - `status != "active"` or `deleted is True` or `nonpublic is True`: Exclude non-active.
- **Server-Side Freshness Filtering:**
  - `from_time` set to `int(since.timestamp())` to ensure the API returns only gigs within the allowed age window (`max_gig_age_minutes`).
- **Deduplication:**
  - Queries across multiple skill IDs or keywords are merged and deduplicated by project `id`.
  - Client sorts returned stubs descending by `posted_at` in Python to guarantee newest-first presentation.

### 4.6 Rate Limits & Terms of Service Compliance
- **Rate Limits:** Approximately 100 requests per minute per IP. `PoliteHttpClient` enforces jitter, rate limiting, and backoff on HTTP 429 (`Retry-After`).
- **Terms of Service:** Read-only inspection of active listings through the official API does not violate platform rules. Automated bidding without human oversight is prohibited (bidding is out of scope for Phase 1b and strictly human-gated in Phase 9).

- **Terms of Service:** Read-only inspection of active listings through the official API does not violate platform rules. Automated bidding without human oversight is prohibited (bidding is out of scope for Phase 1b and strictly human-gated in Phase 9).

