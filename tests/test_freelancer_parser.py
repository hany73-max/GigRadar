"""Unit tests for Freelancer.com API JSON parser against fixtures."""

import json
from pathlib import Path

import pytest

from gigradar.platforms.freelancer.parser import (
    is_excluded_project,
    parse_freelancer_active_response,
    parse_freelancer_project,
    parse_freelancer_stub,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "json"


def test_parse_freelancer_single_project_fixture() -> None:
    data = json.loads((FIXTURES_DIR / "freelancer_single_project.json").read_text(encoding="utf-8"))
    proj_raw = data["result"]
    gig = parse_freelancer_project(proj_raw)

    assert gig.platform_id == "freelancer"
    assert gig.external_id == "40773380"
    assert gig.url == "https://www.freelancer.com/projects/ios/Extract-Restricted-App-Photos"
    assert gig.title == "Extract Restricted App Photos"
    assert "pull my own images" in gig.description
    assert gig.project_type == "fixed"
    assert gig.budget_min == 10.0
    assert gig.budget_max == 20.0
    assert gig.currency == "GBP"
    # 10.0 * 1.3328 = 13.328 -> 13.33
    assert gig.budget_usd_est == 13.33
    assert gig.bids_count == 31
    assert gig.posted_at is not None
    assert gig.posted_at.year == 2026
    assert gig.category_raw == "Websites, IT & Software"
    assert "Python" in gig.tags_raw
    assert "Machine Learning (ML)" in gig.tags_raw
    assert "Web Scraping" in gig.tags_raw
    assert gig.language == "en"
    assert gig.client_name is None


def test_parse_freelancer_stub_fixture() -> None:
    data = json.loads((FIXTURES_DIR / "freelancer_single_project.json").read_text(encoding="utf-8"))
    stub = parse_freelancer_stub(data["result"])

    assert stub.platform_id == "freelancer"
    assert stub.external_id == "40773380"
    assert stub.title == "Extract Restricted App Photos"
    assert stub.bids_count == 31
    assert stub.posted_at is not None
    assert stub.url == "https://www.freelancer.com/projects/ios/Extract-Restricted-App-Photos"


def test_parse_freelancer_active_response_and_hourly() -> None:
    data = json.loads((FIXTURES_DIR / "freelancer_projects.json").read_text(encoding="utf-8"))
    gigs = parse_freelancer_active_response(data)

    # Out of 8 projects in fixture:
    # 5 standard (4 fixed, 1 hourly) + 1 NDA + 1 local + 1 recruiter
    # The 3 with safety flags (NDA, local, recruiter) MUST be excluded
    assert len(gigs) == 5

    # Check hourly project (ID 40773167)
    hourly_gigs = [g for g in gigs if g.project_type == "hourly"]
    assert len(hourly_gigs) == 1
    hg = hourly_gigs[0]
    assert hg.external_id == "40773167"
    assert hg.currency == "INR"
    assert hg.budget_min == 1500.0
    assert hg.budget_max == 3500.0
    # 1500 * 0.010531 = 15.7965 -> 15.8
    assert hg.budget_usd_est == 15.8
    assert "hourly_project_info" in hg.client_stats


def test_is_excluded_project_flags() -> None:
    # 1. Normal project
    ok_proj = {"id": 1, "title": "Normal Job", "type": "fixed", "status": "active"}
    excluded, reason = is_excluded_project(ok_proj)
    assert not excluded
    assert reason is None

    # 2. Contest
    contest_proj = {"id": 2, "title": "Contest", "type": "contest", "status": "active"}
    excluded, reason = is_excluded_project(contest_proj)
    assert excluded and reason == "contest"

    # 3. NDA
    nda_proj = {"id": 3, "title": "NDA Job", "type": "fixed", "status": "active", "upgrades": {"NDA": True}}
    excluded, reason = is_excluded_project(nda_proj)
    assert excluded and reason == "nda"

    # 4. Local
    local_proj = {"id": 4, "title": "Local Job", "type": "fixed", "status": "active", "local": True}
    excluded, reason = is_excluded_project(local_proj)
    assert excluded and reason == "local_job"

    # 5. Recruiter
    recruiter_proj = {"id": 5, "title": "Recruiter Job", "type": "fixed", "status": "active", "upgrades": {"recruiter": True}}
    excluded, reason = is_excluded_project(recruiter_proj)
    assert excluded and reason == "recruiter"

    # 6. Inactive / deleted / nonpublic
    inactive_proj = {"id": 6, "title": "Inactive", "type": "fixed", "status": "closed"}
    assert is_excluded_project(inactive_proj)[0]
    deleted_proj = {"id": 7, "title": "Deleted", "type": "fixed", "deleted": True}
    assert is_excluded_project(deleted_proj)[0]
    nonpublic_proj = {"id": 8, "title": "Private", "type": "fixed", "nonpublic": True}
    assert is_excluded_project(nonpublic_proj)[0]


def test_parser_validation_errors() -> None:
    with pytest.raises(ValueError, match="Expected dict"):
        parse_freelancer_project([])  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="Missing required 'id'"):
        parse_freelancer_project({"title": "No ID"})

    with pytest.raises(ValueError, match="Missing required 'title'"):
        parse_freelancer_project({"id": 123})

    with pytest.raises(ValueError, match="Invalid Freelancer API payload"):
        parse_freelancer_active_response("not a dict")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="Missing 'projects' list"):
        parse_freelancer_active_response({"result": {}})
