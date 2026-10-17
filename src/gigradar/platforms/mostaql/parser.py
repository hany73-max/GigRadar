"""Pure-function HTML parsers for Mostaql (projects listing and project detail)."""

import hashlib
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from gigradar.core.models import Gig, GigStub
from gigradar.platforms.common.normalization import (
    detect_language,
    parse_bids_count,
    parse_budget_range,
    parse_datetime_or_relative,
)


def parse_mostaql_listing(html: str, base_url: str = "https://mostaql.com") -> list[GigStub]:
    """Parse a Mostaql projects listing page HTML into a list of GigStub objects.

    Raises:
        ValueError: If HTML is completely invalid or rows lack required fields (id, title, url).
    """
    if not html or not html.strip():
        raise ValueError("Cannot parse empty Mostaql listing HTML")

    soup = BeautifulSoup(html, "lxml")
    rows = soup.select("table.projects-table tbody tr.project-row")

    stubs: list[GigStub] = []

    for index, row in enumerate(rows):
        link_el = row.select_one("div.card--title h2 a")
        if not link_el:
            # Check if this row is malformed
            raise ValueError(f"Mostaql listing row #{index} missing required title link ('h2 a')")

        title = link_el.get_text(strip=True)
        if not title:
            raise ValueError(f"Mostaql listing row #{index} has empty project title")

        href = link_el.get("href")
        if not href or not isinstance(href, str):
            raise ValueError(f"Mostaql listing row #{index} missing required href attribute")

        full_url = urljoin(base_url, href)

        # Extract external ID from URL (e.g., /project/1286263-slug)
        id_match = re.search(r"/project/(\d+)", href)
        if not id_match:
            raise ValueError(f"Mostaql listing row #{index} has invalid project URL format: {href}")

        external_id = id_match.group(1)

        # Brief description
        brief_el = row.select_one("p.project__brief a.details-url")
        brief = brief_el.get_text(strip=True) if brief_el else None

        # Poster / Client name
        user_bdi = row.select_one("ul.project__meta li bdi")
        client_name = user_bdi.get_text(strip=True) if user_bdi else None

        # Posted timestamp
        time_el = row.select_one("time")
        time_text = time_el.get_text(strip=True) if time_el else ""
        raw_dt = time_el.get("datetime") if time_el else None
        time_attr = raw_dt if isinstance(raw_dt, str) else None
        posted_at = parse_datetime_or_relative(time_text, datetime_attr=time_attr)

        # Bids count
        bids_count = 0
        meta_items = row.select("ul.project__meta li")
        for item in meta_items:
            item_text = item.get_text(strip=True)
            if "عرض" in item_text or "أول عرض" in item_text:
                bids_count = parse_bids_count(item_text)
                break

        stubs.append(
            GigStub(
                platform_id="mostaql",
                external_id=external_id,
                url=full_url,
                title=title,
                posted_at=posted_at,
                bids_count=bids_count,
                brief_description=brief,
                client_name=client_name,
            )
        )

    return stubs


def parse_mostaql_detail(
    html: str,
    stub: GigStub | None = None,
    base_url: str = "https://mostaql.com",
) -> Gig:
    """Parse a Mostaql project detail page HTML into a Gig object.

    Raises:
        ValueError: If required fields (id, title, url, description) cannot be extracted.
    """
    if not html or not html.strip():
        raise ValueError("Cannot parse empty Mostaql detail HTML")

    soup = BeautifulSoup(html, "lxml")

    # 1. Canonical URL & External ID
    canonical_el = soup.select_one('link[rel="canonical"]')
    raw_canonical = canonical_el.get("href") if canonical_el else None
    canonical_url = raw_canonical if isinstance(raw_canonical, str) else None
    url = canonical_url or (stub.url if stub else None)

    if not url:
        raise ValueError("Mostaql detail page missing required URL/canonical link")

    id_match = re.search(r"/project/(\d+)", url)
    external_id = id_match.group(1) if id_match else (stub.external_id if stub else None)
    if not external_id:
        raise ValueError(f"Mostaql detail page could not determine external_id from URL: {url}")

    # 2. Title
    title_el = soup.select_one(
        'h1.heada__title [data-type="page-header-title"]'
    ) or soup.select_one("h1.heada__title")
    title = title_el.get_text(strip=True) if title_el else (stub.title if stub else None)
    if not title:
        raise ValueError(f"Mostaql detail page #{external_id} missing required title")

    # 3. Description
    desc_el = (
        soup.select_one("div#projectDetailsTab div.text-wrapper-div")
        or soup.select_one("div#projectDetailsTab")
        or soup.select_one("div.carda__content")
    )
    description = desc_el.get_text("\n", strip=True) if desc_el else None
    if not description:
        raise ValueError(f"Mostaql detail page #{external_id} missing required project description")

    # 4. Budget
    budget_min: float | None = None
    budget_max: float | None = None
    currency = "USD"
    budget_el = soup.select_one('div[data-type="project-budget_range"] span') or soup.select_one(
        'div[data-type="project-budget_range"]'
    )
    if budget_el:
        budget_min, budget_max, currency = parse_budget_range(budget_el.get_text(strip=True))

    # 5. Execution Duration / Deadline
    deadline_text: str | None = None
    for meta_row in soup.select("div.meta-container div.meta-row"):
        label_el = meta_row.select_one("div.meta-label")
        val_el = meta_row.select_one("div.meta-value")
        if label_el and val_el and "مدة التنفيذ" in label_el.get_text():
            deadline_text = val_el.get_text(" ", strip=True)
            break

    # 6. Posted timestamp
    time_el = soup.select_one("div.meta-container time") or soup.select_one("time")
    time_text = time_el.get_text(strip=True) if time_el else ""
    raw_dt = time_el.get("datetime") if time_el else None
    time_attr = raw_dt if isinstance(raw_dt, str) else None
    posted_at = parse_datetime_or_relative(time_text, datetime_attr=time_attr)
    if not posted_at and stub:
        posted_at = stub.posted_at

    # 7. Bids count
    bids_count = stub.bids_count if stub else 0
    bids_elements = soup.select("div#bidsCollection-panel div.bid")
    if bids_elements:
        bids_count = len(bids_elements)

    # 8. Category
    category_raw: str | None = None
    cat_el = soup.select_one('ol.breadcrumb li[data-index="2"] a') or soup.select_one(
        'ol.breadcrumb li[data-index="2"]'
    )
    if cat_el:
        category_raw = cat_el.get_text(strip=True)

    # 9. Tags / Skills
    tags_raw: list[str] = []
    seen_tags: set[str] = set()
    for tag in soup.select("ul.skills li.skills__item a.tag"):
        tag_text = tag.get_text(strip=True)
        if tag_text and tag_text not in seen_tags:
            seen_tags.add(tag_text)
            tags_raw.append(tag_text)

    # 10. Client info & stats
    client_name: str | None = stub.client_name if stub else None
    client_name_el = soup.select_one("h5.profile__name bdi") or soup.select_one("h5.profile__name")
    if client_name_el:
        client_name = client_name_el.get_text(strip=True)

    client_stats: dict[str, str] = {}
    for row in soup.select("table.table-meta tr"):
        cols = row.select("td")
        if len(cols) >= 2:
            key = cols[0].get_text(strip=True)
            val = cols[1].get_text(strip=True)
            if key and val:
                client_stats[key] = val

    # 11. Language detection
    language = detect_language(f"{title} {description}")

    # 12. Hash
    raw_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()

    return Gig(
        platform_id="mostaql",
        external_id=external_id,
        url=url,
        title=title,
        description=description,
        budget_min=budget_min,
        budget_max=budget_max,
        currency=currency,
        budget_min_usd=budget_min,
        budget_max_usd=budget_max,
        budget_usd_est=(
            round((budget_min + budget_max) / 2.0, 2)
            if budget_min is not None and budget_max is not None
            else (budget_min or budget_max)
        ),
        bids_count=bids_count,
        posted_at=posted_at,
        deadline_text=deadline_text,
        client_name=client_name,
        client_stats=client_stats,
        category_raw=category_raw,
        tags_raw=tags_raw,
        language=language,
        raw_html_hash=raw_hash,
    )
