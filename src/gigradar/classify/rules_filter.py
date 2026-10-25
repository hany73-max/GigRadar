"""Stage 1 deterministic rules filter for GigRadar.

Evaluates gigs deterministically against rules.yaml and platform thresholds.
Output is fully explainable with all hits recorded.
Order of evaluation:
1. Hard rejects (academic, unpaid trial, policy violations, guaranteed accuracy, pure irrelevant)
2. Platform thresholds (age, bids, budget/hourly limits via resolve_platform_thresholds)
3. Exclude keywords
4. Include keyword families (ML/DL, CV, NLP, Data, Backend/Deploy) + Ambiguous words
5. Category lists (weak signal: never rejects when include signal is present)
"""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gigradar.classify.normalize import compile_keyword_pattern, normalize_text
from gigradar.core.config_loader import load_rules_config, resolve_platform_thresholds
from gigradar.core.config_models import RulesConfig


@dataclass
class RuleResult:
    """Outcome of Stage 1 deterministic rules filter."""

    passed: bool
    hits: list[str] = field(default_factory=list)
    reject_reason: str | None = None
    flags: list[str] = field(default_factory=list)


def compute_rules_version(config: RulesConfig) -> str:
    """Compute a short 8-character hash of the rules config for provenance tracking."""
    serialized = config.model_dump_json(exclude_none=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:8]


class RulesFilter:
    """Deterministic, explainable Stage 1 pre-filter."""

    def __init__(
        self,
        rules_config: RulesConfig | None = None,
        config_dir: Path | None = None,
    ) -> None:
        self.config_dir = config_dir
        self.rules_config = rules_config or load_rules_config(config_dir)
        self.rules_version = compute_rules_version(self.rules_config)

        # Precompile regexes
        self._hard_reject_patterns: dict[str, list[tuple[str, re.Pattern[str]]]] = {}
        for cat, patterns in self.rules_config.hard_rejects.items():
            self._hard_reject_patterns[cat] = [
                (p, compile_keyword_pattern(p)) for p in patterns if p.strip()
            ]

        self._exclude_patterns: list[tuple[str, re.Pattern[str]]] = [
            (p, compile_keyword_pattern(p)) for p in self.rules_config.exclude_keywords if p.strip()
        ]

        self._family_patterns: dict[str, list[tuple[str, re.Pattern[str]]]] = {}
        for fam_id, family in self.rules_config.keyword_families.items():
            self._family_patterns[fam_id] = [
                (kw, compile_keyword_pattern(kw)) for kw in family.keywords if kw.strip()
            ]

        self._ambiguous_patterns: list[tuple[str, str, re.Pattern[str]]] = [
            (kw, flag, compile_keyword_pattern(kw))
            for kw, flag in self.rules_config.ambiguous_keywords.items()
            if kw.strip()
        ]

        self._deny_categories: set[str] = {
            normalize_text(c) for c in self.rules_config.category_rules.deny_categories if c.strip()
        }
        self._allow_categories: set[str] = {
            normalize_text(c)
            for c in self.rules_config.category_rules.allow_categories
            if c.strip()
        }

    def evaluate(
        self,
        gig: Any,
        platform_name: str | None = None,
        now: datetime | None = None,
    ) -> RuleResult:
        """Evaluate a gig deterministically.

        Accepts either a Domain Gig, DB Gig model, or duck-typed object.
        """
        hits: list[str] = []
        flags: list[str] = []

        # 0. Detail level handling
        detail_level = getattr(gig, "detail_level", "full") or "full"
        title = getattr(gig, "title", "") or ""
        description = getattr(gig, "description", "") or ""

        if detail_level == "title_only":
            hits.append("detail_level:title_only")
            text_to_eval = title
        else:
            text_to_eval = f"{title} {description}"

        # Include raw tags if available
        tags_raw = getattr(gig, "tags_raw", None) or getattr(gig, "tags_raw_json", None)
        if isinstance(tags_raw, list):
            text_to_eval += " " + " ".join(str(t) for t in tags_raw if t)

        norm_text = normalize_text(text_to_eval)

        # 1. Hard Rejects
        for cat, patterns in self._hard_reject_patterns.items():
            for raw_pattern, regex in patterns:
                if regex.search(norm_text):
                    hit_msg = f"hard_reject:{cat}:{raw_pattern}"
                    hits.append(hit_msg)
                    return RuleResult(
                        passed=False,
                        hits=hits,
                        reject_reason=f"hard_reject:{cat}",
                        flags=flags,
                    )

        # Resolve platform name
        plat_name = platform_name
        if not plat_name:
            if hasattr(gig, "platform_id") and isinstance(gig.platform_id, str):
                plat_name = gig.platform_id
            elif hasattr(gig, "platform") and getattr(gig.platform, "name", None):
                plat_name = str(gig.platform.name)
            else:
                plat_name = "default"

        thresholds = resolve_platform_thresholds(plat_name, self.config_dir)

        # 2. Platform Thresholds
        # 2a. Age limit
        posted_at = getattr(gig, "posted_at", None)
        if posted_at is not None:
            ref_time = now or getattr(gig, "first_seen_at", None) or datetime.now(UTC)
            posted_utc = (
                posted_at.astimezone(UTC) if posted_at.tzinfo else posted_at.replace(tzinfo=UTC)
            )
            ref_utc = ref_time.astimezone(UTC) if ref_time.tzinfo else ref_time.replace(tzinfo=UTC)
            age_minutes = (ref_utc - posted_utc).total_seconds() / 60.0
            if age_minutes > thresholds.max_gig_age_minutes:
                reason = f"age_exceeded:{int(age_minutes)}m > {thresholds.max_gig_age_minutes}m"
                hits.append(reason)
                return RuleResult(
                    passed=False,
                    hits=hits,
                    reject_reason=reason,
                    flags=flags,
                )
            hits.append(f"age_ok:{int(age_minutes)}m")

        # 2b. Bids count limit (Unknown bids_count must PASS)
        bids_count = getattr(gig, "bids_count", None)
        if bids_count is not None:
            if bids_count > thresholds.max_existing_bids:
                reason = f"bids_exceeded:{bids_count} > {thresholds.max_existing_bids}"
                hits.append(reason)
                return RuleResult(
                    passed=False,
                    hits=hits,
                    reject_reason=reason,
                    flags=flags,
                )
            hits.append(f"bids_ok:{bids_count}")
        else:
            hits.append("bids:unknown_passed")

        # 2c. Budget limit (Unknown budget must PASS)
        # Fixed-price gigs use budget_max_usd against min_budget_usd
        # Hourly gigs use budget_max_usd against min_hourly_rate_usd
        project_type = getattr(gig, "project_type", "fixed") or "fixed"
        budget_max_usd = getattr(gig, "budget_max_usd", None)
        if budget_max_usd is None:
            budget_max_usd = getattr(gig, "budget_usd_est", None)

        if budget_max_usd is not None:
            if project_type == "hourly":
                if budget_max_usd < thresholds.min_hourly_rate_usd:
                    reason = (
                        f"hourly_rate_below_min:${budget_max_usd:.0f} < "
                        f"${thresholds.min_hourly_rate_usd:.0f}"
                    )
                    hits.append(reason)
                    return RuleResult(
                        passed=False,
                        hits=hits,
                        reject_reason=reason,
                        flags=flags,
                    )
                hits.append(f"hourly_rate_ok:${budget_max_usd:.0f}")
            else:
                if budget_max_usd < thresholds.min_budget_usd:
                    reason = (
                        f"budget_below_min:${budget_max_usd:.0f} < ${thresholds.min_budget_usd:.0f}"
                    )
                    hits.append(reason)
                    return RuleResult(
                        passed=False,
                        hits=hits,
                        reject_reason=reason,
                        flags=flags,
                    )
                hits.append(f"budget_ok:${budget_max_usd:.0f}")
        else:
            hits.append("budget:unknown_passed")

        # 3. Exclude Keywords
        for raw_exclude, regex in self._exclude_patterns:
            if regex.search(norm_text):
                hit_msg = f"exclude_keyword:{raw_exclude}"
                hits.append(hit_msg)
                return RuleResult(
                    passed=False,
                    hits=hits,
                    reject_reason=hit_msg,
                    flags=flags,
                )

        # 4. Keyword Include Families & Ambiguous Words
        has_include_hit = False

        for fam_id, kw_list in self._family_patterns.items():
            for kw, regex in kw_list:
                if regex.search(norm_text):
                    hits.append(f"include:{fam_id}:{kw}")
                    has_include_hit = True

        for kw, flag, regex in self._ambiguous_patterns:
            if regex.search(norm_text):
                hits.append(f"ambiguous:{kw} -> {flag}")
                if flag not in flags:
                    flags.append(flag)
                has_include_hit = True

        # If no include keywords matched at all:
        if not has_include_hit:
            # Check if category deny also applies
            category_raw = getattr(gig, "category_raw", None)
            if category_raw:
                norm_cat = normalize_text(category_raw)
                if norm_cat in self._deny_categories:
                    reason = f"category_denied:{category_raw}"
                    hits.append(reason)
                    return RuleResult(
                        passed=False,
                        hits=hits,
                        reject_reason=reason,
                        flags=flags,
                    )

            reason = "no_include_keywords"
            hits.append(reason)
            return RuleResult(
                passed=False,
                hits=hits,
                reject_reason=reason,
                flags=flags,
            )

        # 5. Category Lists Evaluation (Weak signal: never rejects when include hit is present)
        category_raw = getattr(gig, "category_raw", None)
        if category_raw:
            norm_cat = normalize_text(category_raw)
            if norm_cat in self._deny_categories:
                hits.append(f"category_deny_overridden:{category_raw}")
            elif norm_cat in self._allow_categories:
                hits.append(f"category_allow:{category_raw}")
            else:
                hits.append(f"category_neutral:{category_raw}")

        return RuleResult(
            passed=True,
            hits=hits,
            reject_reason=None,
            flags=flags,
        )
