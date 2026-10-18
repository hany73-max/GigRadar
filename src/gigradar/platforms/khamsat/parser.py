"""Pure-function HTML parsers for Khamsat (buyer requests listing).

Per project architectural decision, Khamsat detail pages sit behind an AWS WAF
challenge and are intentionally not fetched. All fields are parsed from listing pages.
"""

import hashlib
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from gigradar.core.models import Gig, GigStub
from gigradar.platforms.common.normalization import (
    detect_language,
    parse_datetime_or_relative,
)


def parse_khamsat_listing(html: str, base_url: str = "https://khamsat.com") -> list[GigStub]:
    """Parse a Khamsat buyer requests listing page HTML into a list of GigStub objects.

    Raises:
        ValueError: If HTML is empty or rows lack required fields (id, title, url).
    """
    if not html or not html.strip():
        raise ValueError("Cannot parse empty Khamsat listing HTML")

    soup = BeautifulSoup(html, "lxml")
    rows = soup.select("table#forums_table tbody tr.forum_post")

    stubs: list[GigStub] = []

    for index, row in enumerate(rows):
        link_el = row.select_one("td.details-td h3.details-head a")
        if not link_el:
            raise ValueError(
                f"Khamsat listing row #{index} missing required title link ('h3.details-head a')"
            )

        title = link_el.get_text(strip=True)
        if not title:
            raise ValueError(f"Khamsat listing row #{index} has empty title")

        href = link_el.get("href")
        if not href or not isinstance(href, str):
            raise ValueError(f"Khamsat listing row #{index} missing required href attribute")

        full_url = urljoin(base_url, href)

        # Extract external ID: either from row id 'forum_post-799121' or URL '/community/requests/799121-slug'
        external_id: str | None = None
        row_id_attr = row.get("id")
        if row_id_attr and isinstance(row_id_attr, str):
            row_match = re.search(r"forum_post-(\d+)", row_id_attr)
            if row_match:
                external_id = row_match.group(1)

        if not external_id:
            url_match = re.search(r"/community/requests/(\d+)", href)
            if url_match:
                external_id = url_match.group(1)

        if not external_id:
            raise ValueError(
                f"Khamsat listing row #{index} could not extract external_id from row or URL: {href}"
            )

        # Buyer / user name
        user_el = row.select_one("td.details-td ul.details-list li a.user")
        client_name = user_el.get_text(strip=True) if user_el else None

        # Posted timestamp (Khamsat provides exact GMT in span title)
        time_span = row.select_one("td.details-td ul.details-list li span[title]")
        time_text = time_span.get_text(strip=True) if time_span else ""
        raw_title_attr = time_span.get("title") if time_span else None
        time_attr = raw_title_attr if isinstance(raw_title_attr, str) else None
        posted_at = parse_datetime_or_relative(time_text, datetime_attr=time_attr)

        stubs.append(
            GigStub(
                platform_id="khamsat",
                external_id=external_id,
                url=full_url,
                title=title,
                posted_at=posted_at,
                bids_count=None,
                brief_description=title,
                client_name=client_name,
                detail_level="title_only",
            )
        )

    return stubs


def parse_khamsat_gig_from_stub(stub: GigStub, raw_html: str | None = None) -> Gig:
    """Build a complete Gig from a Khamsat GigStub without fetching detail pages.

    Detail-only fields (budget, tags, extended description) remain None or defaults.
    """
    raw_hash = hashlib.sha256(raw_html.encode("utf-8")).hexdigest() if raw_html else None

    return Gig(
        platform_id="khamsat",
        external_id=stub.external_id,
        url=stub.url,
        title=stub.title,
        description=stub.brief_description or stub.title,
        budget_min=None,
        budget_max=None,
        currency="USD",
        budget_min_usd=None,
        budget_max_usd=None,
        budget_usd_est=None,
        bids_count=stub.bids_count,
        posted_at=stub.posted_at,
        deadline_text=None,
        client_name=stub.client_name,
        client_stats={},
        category_raw="طلبات الخدمات غير الموجودة",
        tags_raw=[],
        language=detect_language(stub.title),
        detail_level="title_only",
        raw_html_hash=raw_hash,
    )
