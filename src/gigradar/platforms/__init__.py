"""Platform clients and scrapers for GigRadar."""

from gigradar.platforms.base import PlatformClient
from gigradar.platforms.khamsat.client import KhamsatClient
from gigradar.platforms.mostaql.client import MostaqlClient

__all__ = ["KhamsatClient", "MostaqlClient", "PlatformClient"]
