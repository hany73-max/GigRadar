"""Unit tests for Mostaql and Khamsat HTML parsers against sanitized fixtures."""

from pathlib import Path

import pytest

from gigradar.platforms.khamsat.parser import (
    parse_khamsat_gig_from_stub,
    parse_khamsat_listing,
)
from gigradar.platforms.mostaql.parser import (
    parse_mostaql_detail,
    parse_mostaql_listing,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "html"


def test_parse_mostaql_listing_fixture() -> None:
    html = (FIXTURES_DIR / "mostaql_listing.html").read_text(encoding="utf-8")
    stubs = parse_mostaql_listing(html)

    assert len(stubs) == 25
    first = stubs[0]
    assert first.platform_id == "mostaql"
    assert first.external_id == "1286263"
    assert first.url.startswith("https://mostaql.com/project/1286263")
    assert "Media Buyer" in first.title
    assert first.posted_at is not None
    assert first.bids_count == 0  # 'أضف أول عرض'
    assert first.client_name is not None

    # Check a project with bids
    second = stubs[1]
    assert second.external_id == "1286262"
    assert second.bids_count == 14  # '14 عرض'


def test_parse_mostaql_detail_fixture() -> None:
    html = (FIXTURES_DIR / "mostaql_detail.html").read_text(encoding="utf-8")
    gig = parse_mostaql_detail(html)

    assert gig.platform_id == "mostaql"
    assert gig.external_id == "1286262"
    assert gig.url.startswith("https://mostaql.com/project/1286262")
    assert "نقل استضافة موقع" in gig.title
    assert "نقل استضافة موقع من منصة إلى أخرى" in gig.description
    assert gig.budget_min == 50.0
    assert gig.budget_max == 100.0
    assert gig.currency == "USD"
    assert gig.deadline_text is not None and "7" in gig.deadline_text
    assert gig.posted_at is not None
    assert gig.category_raw == "برمجة، تطوير المواقع والتطبيقات"
    assert len(gig.tags_raw) == 6
    assert "استضافة المواقع" in gig.tags_raw
    assert "إنشاء موقع إلكتروني" in gig.tags_raw
    assert "برمجة مواقع" in gig.tags_raw
    assert gig.client_name == "User A"
    assert "معدل التوظيف" in gig.client_stats
    assert gig.raw_html_hash is not None


def test_parse_khamsat_listing_fixture() -> None:
    html = (FIXTURES_DIR / "khamsat_listing.html").read_text(encoding="utf-8")
    stubs = parse_khamsat_listing(html)

    assert len(stubs) == 25
    first = stubs[0]
    assert first.platform_id == "khamsat"
    assert first.external_id == "799121"
    assert first.url.startswith("https://khamsat.com/community/requests/799121")
    assert "روابط باك لينك" in first.title
    assert first.posted_at is not None
    assert first.client_name is not None
    assert first.bids_count is None

    gig = parse_khamsat_gig_from_stub(first, raw_html=html)
    assert gig.platform_id == "khamsat"
    assert gig.external_id == "799121"
    assert gig.budget_min is None
    assert gig.budget_max is None
    assert gig.bids_count is None
    assert gig.category_raw == "طلبات الخدمات غير الموجودة"


def test_parser_fails_on_missing_required_fields() -> None:
    # 1. Empty HTML
    with pytest.raises(ValueError, match="empty Mostaql listing"):
        parse_mostaql_listing("")

    with pytest.raises(ValueError, match="empty Mostaql detail"):
        parse_mostaql_detail("")

    with pytest.raises(ValueError, match="empty Khamsat listing"):
        parse_khamsat_listing("")

    # 2. Malformed row in Mostaql listing
    bad_html = "<html><body><table class='projects-table'><tbody><tr class='project-row'><td>No link</td></tr></tbody></table></body></html>"
    with pytest.raises(ValueError, match="missing required title link"):
        parse_mostaql_listing(bad_html)

    # 3. Missing description in Mostaql detail
    bad_detail = "<html><head><link rel='canonical' href='https://mostaql.com/project/123-test'></head><body><h1 class='heada__title'>Test</h1></body></html>"
    with pytest.raises(ValueError, match="missing required project description"):
        parse_mostaql_detail(bad_detail)

    # 4. Missing link in Khamsat listing
    bad_khamsat = "<html><body><table id='forums_table'><tbody><tr class='forum_post'><td>No link</td></tr></tbody></table></body></html>"
    with pytest.raises(ValueError, match="missing required title link"):
        parse_khamsat_listing(bad_khamsat)
