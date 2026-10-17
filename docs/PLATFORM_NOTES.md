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
