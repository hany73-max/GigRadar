"""Base platform abstractions and protocols."""

from datetime import datetime
from typing import Protocol, runtime_checkable

from gigradar.core.models import Gig, GigStub, HealthReport


@runtime_checkable
class PlatformClient(Protocol):
    """Standard interface for platform clients and scrapers."""

    name: str

    async def list_new_gigs(self, since: datetime | None = None) -> list[GigStub]:
        """Fetch newly posted gigs as lightweight stubs from listing pages."""
        ...

    async def fetch_gig_detail(self, stub: GigStub) -> Gig:
        """Fetch full details for a gig."""
        ...

    async def health_check(self) -> HealthReport:
        """Detect layout drift or connectivity issues against known shapes."""
        ...
