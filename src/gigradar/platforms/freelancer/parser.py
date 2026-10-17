"""Pure-function parsers for Freelancer.com official REST API."""

from datetime import UTC, datetime
from typing import Any, Literal

from gigradar.core.models import Gig, GigStub
from gigradar.platforms.common.normalization import detect_language


def is_excluded_project(data: dict[str, Any]) -> tuple[bool, str | None]:
    """Check if a project should be excluded based on platform and safety rules.

    Excludes:
    - Contests
    - NDA projects
    - On-site / local jobs
    - Recruiter-assisted / staffing fee listings
    - Inactive / non-public / deleted projects
    """
    # 1. Contests
    proj_type = str(data.get("type", "")).lower()
    if proj_type == "contest" or data.get("is_contest"):
        return True, "contest"

    # 2. Inactive / deleted / nonpublic
    status = str(data.get("status", "")).lower()
    if status and status != "active":
        return True, f"status_{status}"
    if data.get("deleted"):
        return True, "deleted"
    if data.get("nonpublic"):
        return True, "nonpublic"

    # 3. NDA
    upgrades = data.get("upgrades") or {}
    if upgrades.get("NDA") or data.get("nda_signatures") or data.get("nda_details"):
        return True, "nda"

    # 4. Local / On-site jobs
    if data.get("local") or data.get("is_local") or data.get("local_details"):
        return True, "local_job"

    # 5. Recruiter listings
    if upgrades.get("recruiter") or upgrades.get("unpaid_recruiter") or data.get("assisted"):
        return True, "recruiter"

    return False, None


def parse_freelancer_stub(data: dict[str, Any]) -> GigStub:
    """Parse a Freelancer API project dictionary into a lightweight GigStub."""
    if not isinstance(data, dict):
        raise ValueError(f"Expected dict for Freelancer project data, got {type(data).__name__}")

    proj_id = data.get("id")
    if not proj_id:
        raise ValueError("Missing required 'id' field in Freelancer project data")

    external_id = str(proj_id)
    title = str(data.get("title", "")).strip()
    if not title:
        raise ValueError(f"Missing required 'title' field in Freelancer project {external_id}")

    seo_url = data.get("seo_url")
    if seo_url:
        url = f"https://www.freelancer.com/projects/{seo_url}"
    else:
        url = f"https://www.freelancer.com/projects/{external_id}"

    # Timestamp
    submitdate = data.get("submitdate") or data.get("time_submitted")
    posted_at = datetime.fromtimestamp(int(submitdate), tz=UTC) if submitdate else None

    # Bid count
    bid_stats = data.get("bid_stats") or {}
    bids_count = bid_stats.get("bid_count")
    if bids_count is not None:
        bids_count = int(bids_count)

    brief = str(data.get("preview_description") or data.get("description") or "").strip() or None

    return GigStub(
        platform_id="freelancer",
        external_id=external_id,
        url=url,
        title=title,
        posted_at=posted_at,
        bids_count=bids_count,
        brief_description=brief,
        client_name=None,
    )


def parse_freelancer_project(data: dict[str, Any]) -> Gig:
    """Parse a Freelancer API project dictionary into a full Gig domain model."""
    if not isinstance(data, dict):
        raise ValueError(f"Expected dict for Freelancer project data, got {type(data).__name__}")

    proj_id = data.get("id")
    if not proj_id:
        raise ValueError("Missing required 'id' field in Freelancer project data")

    external_id = str(proj_id)
    title = str(data.get("title", "")).strip()
    if not title:
        raise ValueError(f"Missing required 'title' field in Freelancer project {external_id}")

    description = str(data.get("description") or data.get("preview_description") or title).strip()

    seo_url = data.get("seo_url")
    if seo_url:
        url = f"https://www.freelancer.com/projects/{seo_url}"
    else:
        url = f"https://www.freelancer.com/projects/{external_id}"

    # Project type: fixed or hourly
    raw_type = str(data.get("type", "")).lower()
    project_type: Literal["fixed", "hourly"] = "hourly" if raw_type == "hourly" else "fixed"

    # Budget
    budget_info = data.get("budget") or {}
    budget_min = float(budget_info["minimum"]) if budget_info.get("minimum") is not None else None
    budget_max = float(budget_info["maximum"]) if budget_info.get("maximum") is not None else None

    # Currency & live exchange rate normalization
    curr_info = data.get("currency") or {}
    currency_code = str(curr_info.get("code") or "USD").upper()
    exchange_rate = curr_info.get("exchange_rate")

    budget_usd_est: float | None = None
    if exchange_rate is not None and float(exchange_rate) > 0:
        rate = float(exchange_rate)
        if budget_min is not None:
            budget_usd_est = round(budget_min * rate, 2)
        elif budget_max is not None:
            budget_usd_est = round(budget_max * rate, 2)
    elif currency_code == "USD":
        budget_usd_est = budget_min if budget_min is not None else budget_max

    # Bid stats
    bid_stats = data.get("bid_stats") or {}
    bids_count = bid_stats.get("bid_count")
    if bids_count is not None:
        bids_count = int(bids_count)

    # Submitted date
    submitdate = data.get("submitdate") or data.get("time_submitted")
    posted_at = datetime.fromtimestamp(int(submitdate), tz=UTC) if submitdate else None

    # Jobs / Skill tags
    jobs = data.get("jobs") or []
    tags_raw = [str(j["name"]).strip() for j in jobs if isinstance(j, dict) and "name" in j]

    category_raw: str | None = None
    for j in jobs:
        if isinstance(j, dict) and isinstance(j.get("category"), dict):
            cat_name = j["category"].get("name")
            if cat_name:
                category_raw = str(cat_name).strip()
                break

    # Language
    api_lang = data.get("language")
    language: Literal["ar", "en", "mixed"]
    if api_lang == "en":
        language = "en"
    elif api_lang == "ar":
        language = "ar"
    else:
        language = detect_language(f"{title} {description}")

    # Client stats & hourly metadata
    client_stats: dict[str, Any] = {}
    if data.get("hourly_project_info"):
        client_stats["hourly_project_info"] = data["hourly_project_info"]
    if data.get("upgrades"):
        client_stats["upgrades"] = data["upgrades"]

    return Gig(
        platform_id="freelancer",
        external_id=external_id,
        url=url,
        title=title,
        description=description,
        budget_min=budget_min,
        budget_max=budget_max,
        currency=currency_code,
        budget_usd_est=budget_usd_est,
        bids_count=bids_count,
        posted_at=posted_at,
        deadline_text=None,
        client_name=None,
        client_stats=client_stats,
        category_raw=category_raw,
        tags_raw=tags_raw,
        language=language,
        project_type=project_type,
        raw_html_hash=None,
    )


def parse_freelancer_active_response(payload: dict[str, Any]) -> list[Gig]:
    """Parse top-level Freelancer active projects API response into a list of Gig objects.

    Filters out excluded projects (contests, NDA, local jobs, recruiter).
    """
    if not isinstance(payload, dict):
        raise ValueError("Invalid Freelancer API payload: expected JSON dict")

    result = payload.get("result") or {}
    projects = result.get("projects")
    if not isinstance(projects, list):
        raise ValueError("Missing 'projects' list in Freelancer API response 'result'")

    gigs: list[Gig] = []
    for proj in projects:
        if not isinstance(proj, dict):
            continue
        excluded, _reason = is_excluded_project(proj)
        if excluded:
            continue
        gigs.append(parse_freelancer_project(proj))

    return gigs
