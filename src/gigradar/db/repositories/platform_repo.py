"""Platform repository for database persistence."""

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from gigradar.db.models import Platform, utc_now


class PlatformRepository:
    """Repository handling CRUD operations on Platform records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, platform_id: int) -> Platform | None:
        """Fetch platform by its primary key ID."""
        result = await self.session.execute(select(Platform).where(Platform.id == platform_id))
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Platform | None:
        """Fetch platform by name (case-insensitive search)."""
        normalized = name.strip().lower()
        result = await self.session.execute(select(Platform).where(Platform.name == normalized))
        return result.scalar_one_or_none()

    async def get_or_create(self, name: str, base_url: str) -> tuple[Platform, bool]:
        """Fetch existing platform or insert new one idempotently."""
        normalized = name.strip().lower()
        existing = await self.get_by_name(normalized)
        if existing is not None:
            if existing.base_url != base_url:
                existing.base_url = base_url
                await self.session.flush()
            return existing, False

        new_platform = Platform(
            name=normalized,
            base_url=base_url,
            is_paused=False,
            created_at=utc_now(),
        )
        self.session.add(new_platform)
        await self.session.flush()
        return new_platform, True

    async def list_all(self) -> list[Platform]:
        """List all registered platforms."""
        result = await self.session.execute(select(Platform).order_by(Platform.id))
        return list(result.scalars().all())

    async def set_paused(
        self,
        platform_id: int,
        paused_until: datetime,
        reason: str | None = None,
    ) -> None:
        """Mark platform as paused until a specific UTC timestamp."""
        utc_paused_until = paused_until.astimezone(UTC)
        await self.session.execute(
            update(Platform)
            .where(Platform.id == platform_id)
            .values(
                is_paused=True,
                paused_until=utc_paused_until,
                pause_reason=reason,
            )
        )
        await self.session.flush()

    async def clear_paused(self, platform_id: int) -> None:
        """Unpause platform and reset pause fields."""
        await self.session.execute(
            update(Platform)
            .where(Platform.id == platform_id)
            .values(
                is_paused=False,
                paused_until=None,
                pause_reason=None,
            )
        )
        await self.session.flush()
