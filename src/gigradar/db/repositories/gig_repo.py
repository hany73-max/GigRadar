"""Gig repository for database persistence and idempotent upserting."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from gigradar.core.models import Gig as DomainGig
from gigradar.core.models import GigStub
from gigradar.db.models import Classification, Gig, GigSnapshot, Platform, utc_now


class GigRepository:
    """Repository handling CRUD and idempotent upsert operations for Gigs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, gig_id: int) -> Gig | None:
        """Fetch gig by its primary key with snapshots loaded."""
        result = await self.session.execute(
            select(Gig).options(selectinload(Gig.snapshots)).where(Gig.id == gig_id)
        )
        return result.scalar_one_or_none()

    async def get_by_external_id(self, platform_id: int, external_id: str) -> Gig | None:
        """Fetch gig by platform_id and external_id with snapshots loaded."""
        result = await self.session.execute(
            select(Gig)
            .options(selectinload(Gig.snapshots))
            .where(
                Gig.platform_id == platform_id,
                Gig.external_id == external_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_snapshots(self, gig_id: int) -> list[GigSnapshot]:
        """Fetch all snapshots for a gig ordered chronologically."""
        result = await self.session.execute(
            select(GigSnapshot).where(GigSnapshot.gig_id == gig_id).order_by(GigSnapshot.seen_at)
        )
        return list(result.scalars().all())

    async def upsert_stub(
        self,
        platform_id: int,
        stub: GigStub,
        processing_state: str = "new",
    ) -> tuple[Gig, bool]:
        """Idempotently upsert a gig stub.

        If gig already exists:
            - Updates `last_seen_at`.
            - If bids_count has changed, updates bids_count and creates a GigSnapshot.
            - Does NOT overwrite processing_state or detail fields.
            - Returns (existing_gig, False).

        If gig does NOT exist:
            - Inserts new Gig row with initial fields and specified processing_state.
            - Creates initial GigSnapshot if bids_count is known.
            - Returns (new_gig, True).
        """
        existing = await self.get_by_external_id(platform_id, stub.external_id)
        now = utc_now()

        if existing is not None:
            existing.last_seen_at = now
            # Check for bid count change
            if stub.bids_count is not None and stub.bids_count != existing.bids_count:
                existing.bids_count = stub.bids_count
                snapshot = GigSnapshot(
                    gig_id=existing.id,
                    bids_count=stub.bids_count,
                    seen_at=now,
                )
                self.session.add(snapshot)

            await self.session.flush()
            return existing, False

        # Create new gig
        new_gig = Gig(
            platform_id=platform_id,
            external_id=stub.external_id,
            url=stub.url,
            title=stub.title,
            description=stub.brief_description,
            budget_min=None,
            budget_max=None,
            currency=None,
            budget_min_usd=None,
            budget_max_usd=None,
            budget_usd_est=None,
            project_type="fixed",
            bids_count=stub.bids_count,
            posted_at=stub.posted_at,
            deadline_text=None,
            client_name=stub.client_name,
            client_stats_json=None,
            category_raw=None,
            tags_raw_json=None,
            language=None,
            raw_html_hash=None,
            detail_level=stub.detail_level,
            processing_state=processing_state,
            first_seen_at=now,
            last_seen_at=now,
        )
        self.session.add(new_gig)
        await self.session.flush()

        if stub.bids_count is not None:
            snapshot = GigSnapshot(
                gig_id=new_gig.id,
                bids_count=stub.bids_count,
                seen_at=now,
            )
            self.session.add(snapshot)
            await self.session.flush()

        return new_gig, True

    async def update_gig_detail(self, gig_id: int, detail: DomainGig) -> Gig:
        """Update an existing gig with full details fetched from platform.

        Sets detail_level="full" and processing_state="detail_fetched".
        Updates bids_count and snapshot if bids changed.
        """
        gig = await self.get_by_id(gig_id)
        if gig is None:
            raise ValueError(f"Cannot update details for non-existent gig #{gig_id}")

        now = utc_now()
        gig.title = detail.title
        gig.description = detail.description
        gig.budget_min = detail.budget_min
        gig.budget_max = detail.budget_max
        gig.currency = detail.currency
        gig.budget_min_usd = detail.budget_min_usd
        gig.budget_max_usd = detail.budget_max_usd
        gig.budget_usd_est = detail.budget_usd_est
        gig.project_type = detail.project_type
        if detail.posted_at is not None:
            gig.posted_at = detail.posted_at
        gig.deadline_text = detail.deadline_text
        if detail.client_name:
            gig.client_name = detail.client_name
        gig.client_stats_json = detail.client_stats
        gig.category_raw = detail.category_raw
        gig.tags_raw_json = detail.tags_raw
        gig.language = detail.language
        gig.raw_html_hash = detail.raw_html_hash
        gig.detail_level = "full"
        gig.processing_state = "detail_fetched"
        gig.last_seen_at = now

        if detail.bids_count is not None and detail.bids_count != gig.bids_count:
            gig.bids_count = detail.bids_count
            snapshot = GigSnapshot(
                gig_id=gig.id,
                bids_count=detail.bids_count,
                seen_at=now,
            )
            self.session.add(snapshot)

        await self.session.flush()
        return gig

    async def mark_detail_fetched(self, gig_id: int) -> Gig:
        """Transition gig from 'new' to 'detail_fetched' without updating fields.

        Used for platforms like Khamsat where listing stub constitutes full detail.
        """
        gig = await self.get_by_id(gig_id)
        if gig is None:
            raise ValueError(f"Cannot mark non-existent gig #{gig_id} as detail_fetched")

        gig.processing_state = "detail_fetched"
        gig.last_seen_at = utc_now()
        await self.session.flush()
        return gig

    async def record_detail_failure(self, gig_id: int, max_attempts: int = 3) -> tuple[Gig, bool]:
        """Record a failed detail fetch attempt, incrementing detail_attempts.

        If attempts reach max_attempts, marks processing_state='detail_failed'.
        Returns (gig, is_permanently_failed).
        """
        gig = await self.get_by_id(gig_id)
        if gig is None:
            raise ValueError(f"Cannot record detail failure for non-existent gig #{gig_id}")

        gig.detail_attempts += 1
        is_permanently_failed = gig.detail_attempts >= max_attempts
        if is_permanently_failed:
            gig.processing_state = "detail_failed"
        gig.last_seen_at = utc_now()
        await self.session.flush()
        return gig, is_permanently_failed

    async def mark_stale(self, gig_id: int) -> Gig:
        """Mark a gig as 'stale' (e.g. exceeded max_gig_age_minutes)."""
        gig = await self.get_by_id(gig_id)
        if gig is None:
            raise ValueError(f"Cannot mark non-existent gig #{gig_id} as stale")

        gig.processing_state = "stale"
        gig.last_seen_at = utc_now()
        await self.session.flush()
        return gig

    async def get_incomplete_gigs(self, platform_id: int) -> list[Gig]:
        """Retrieve gigs stuck in 'new' processing_state that need details fetched."""
        result = await self.session.execute(
            select(Gig)
            .where(
                Gig.platform_id == platform_id,
                Gig.processing_state == "new",
            )
            .order_by(Gig.id)
        )
        return list(result.scalars().all())

    async def get_stats(self) -> dict[str, Any]:
        """Aggregate summary statistics across all stored platforms and gigs."""
        # Total gigs
        total_result = await self.session.execute(select(func.count(Gig.id)))
        total_gigs = total_result.scalar_one() or 0

        # Gigs per platform
        platform_counts_query = (
            select(Platform.name, func.count(Gig.id))
            .join(Gig, Gig.platform_id == Platform.id, isouter=True)
            .group_by(Platform.name)
        )
        counts_res = await self.session.execute(platform_counts_query)
        by_platform = {str(row[0]): int(row[1]) for row in counts_res.all()}

        # Gigs by processing state
        state_counts_query = select(Gig.processing_state, func.count(Gig.id)).group_by(
            Gig.processing_state
        )
        state_res = await self.session.execute(state_counts_query)
        by_state = {str(row[0]): int(row[1]) for row in state_res.all()}

        return {
            "total_gigs": total_gigs,
            "by_platform": by_platform,
            "by_state": by_state,
        }

    async def record_classification(
        self,
        gig_id: int,
        stage: str,
        passed: bool,
        rule_hits: list[str],
        reject_reason: str | None = None,
        flags: list[str] | None = None,
        rules_version: str | None = None,
    ) -> tuple[Gig, Classification]:
        """Record a classification row and update gig processing_state.

        Provenance: Always appends a new row to `classifications` table.
        Safety invariant: If the gig is already 'stale', its processing_state is NEVER
        overwritten to rules_passed/rules_rejected.
        """
        gig = await self.get_by_id(gig_id)
        if gig is None:
            raise ValueError(f"Cannot classify non-existent gig #{gig_id}")

        now = utc_now()
        classification = Classification(
            gig_id=gig.id,
            stage=stage,
            passed=passed,
            rule_hits_json=rule_hits,
            reject_reason=reject_reason,
            flags_json=flags,
            rules_version=rules_version,
            created_at=now,
        )
        self.session.add(classification)

        # Do NOT change state if gig is stale!
        if gig.processing_state != "stale":
            gig.processing_state = "rules_passed" if passed else "rules_rejected"

        gig.last_seen_at = now
        await self.session.flush()
        return gig, classification

    async def get_latest_classification(
        self, gig_id: int, stage: str = "rules"
    ) -> Classification | None:
        """Fetch the most recent classification record for a gig and stage."""
        result = await self.session.execute(
            select(Classification)
            .where(
                Classification.gig_id == gig_id,
                Classification.stage == stage,
            )
            .order_by(Classification.created_at.desc(), Classification.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_gigs_for_rules_classification(
        self,
        platform_id: int | None = None,
        limit: int | None = None,
        reclassify: bool = False,
    ) -> list[Gig]:
        """Retrieve gigs ready for Stage 1 rules classification.

        If reclassify is False: picks gigs in 'detail_fetched' state (excluding 'stale').
        If reclassify is True: picks all non-stale gigs.
        """
        query = select(Gig).options(selectinload(Gig.platform))

        if platform_id is not None:
            query = query.where(Gig.platform_id == platform_id)

        # Safety: never classify or reclassify stale gigs
        query = query.where(Gig.processing_state != "stale")

        if not reclassify:
            query = query.where(Gig.processing_state == "detail_fetched")

        query = query.order_by(Gig.id.asc())

        if limit is not None:
            query = query.limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_all_classified_gigs(
        self, platform_id: int | None = None
    ) -> list[tuple[Gig, Classification]]:
        """Retrieve all non-stale gigs with their latest rules classification."""
        query = (
            select(Gig, Classification)
            .options(selectinload(Gig.platform))
            .join(Classification, Classification.gig_id == Gig.id)
            .where(Classification.stage == "rules")
            .where(Gig.processing_state != "stale")
        )
        if platform_id is not None:
            query = query.where(Gig.platform_id == platform_id)

        query = query.order_by(Classification.created_at.desc())
        result = await self.session.execute(query)
        rows = result.all()

        # Deduplicate keeping latest classification per gig
        seen_gig_ids: set[int] = set()
        deduped: list[tuple[Gig, Classification]] = []
        for g, c in rows:
            if g.id not in seen_gig_ids:
                seen_gig_ids.add(g.id)
                deduped.append((g, c))
        return deduped
