"""Circuit breaker per platform to pause polling after repeated failures."""

from datetime import datetime, timedelta

import structlog

from gigradar.db.models import utc_now
from gigradar.db.repositories.platform_repo import PlatformRepository
from gigradar.db.repositories.scrape_run_repo import ScrapeRunRepository

logger = structlog.get_logger(__name__)


class CircuitBreaker:
    """Per-platform circuit breaker tracking consecutive failures and managing cooldown."""

    def __init__(
        self,
        failure_threshold: int | None = None,
        cooldown_minutes: int | None = None,
    ) -> None:
        self.default_failure_threshold = failure_threshold
        self.default_cooldown_minutes = cooldown_minutes

    @property
    def failure_threshold(self) -> int:
        return self.default_failure_threshold if self.default_failure_threshold is not None else 3

    @property
    def cooldown_minutes(self) -> int:
        return self.default_cooldown_minutes if self.default_cooldown_minutes is not None else 15

    async def can_execute(
        self,
        platform_repo: PlatformRepository,
        platform_id: int,
        now: datetime | None = None,
    ) -> tuple[bool, str | None]:
        """Check if platform is allowed to run a tick.

        Returns (True, None) if execution is permitted,
        or (False, reason) if paused.
        Auto-recovers if cooldown period has elapsed.
        """
        current_time = now or utc_now()
        platform = await platform_repo.get_by_id(platform_id)
        if platform is None:
            return False, f"Platform #{platform_id} not found"

        if platform.is_paused:
            if platform.paused_until and current_time < platform.paused_until:
                reason = (
                    f"Platform '{platform.name}' is paused until {platform.paused_until.isoformat()} "
                    f"({platform.pause_reason})"
                )
                logger.info(
                    "circuit_breaker_paused",
                    platform=platform.name,
                    paused_until=platform.paused_until.isoformat(),
                    reason=platform.pause_reason,
                )
                return False, reason

            # Cooldown elapsed -> auto-recover
            await platform_repo.clear_paused(platform_id)
            logger.info(
                "circuit_breaker_recovered",
                platform=platform.name,
                message="Platform cooldown period expired; resuming polling.",
            )

        return True, None

    async def record_failure(
        self,
        platform_repo: PlatformRepository,
        scrape_run_repo: ScrapeRunRepository,
        platform_id: int,
        error_message: str,
        now: datetime | None = None,
        failure_threshold: int | None = None,
        cooldown_minutes: int | None = None,
    ) -> bool:
        """Record a tick failure. Trips circuit breaker if consecutive failures >= threshold.

        Resolves circuit_breaker_failures and circuit_breaker_cooldown_minutes from platforms.yaml
        unless explicitly provided.
        Returns True if the breaker was tripped, False otherwise.
        """
        current_time = now or utc_now()
        platform = await platform_repo.get_by_id(platform_id)
        if platform is None:
            return False

        # Resolve thresholds:
        # 1. Method arguments override everything if given
        thresh = failure_threshold
        cd_min = cooldown_minutes

        # 2. Explicit instance configuration overrides platforms.yaml
        if thresh is None and self.default_failure_threshold is not None:
            thresh = self.default_failure_threshold
        if cd_min is None and self.default_cooldown_minutes is not None:
            cd_min = self.default_cooldown_minutes

        # 3. Otherwise resolve from platforms.yaml
        if thresh is None or cd_min is None:
            try:
                from gigradar.core.config_loader import load_platforms_config

                plat_cfg = load_platforms_config()
                norm_name = platform.name.strip().lower()
                plat_settings = plat_cfg.platforms.get(norm_name)
                if plat_settings is not None:
                    if thresh is None:
                        thresh = plat_settings.circuit_breaker_failures
                    if cd_min is None:
                        cd_min = plat_settings.circuit_breaker_cooldown_minutes
            except Exception:
                pass

        eff_failure_threshold = thresh if thresh is not None else 3
        eff_cooldown_minutes = cd_min if cd_min is not None else 15

        consecutive_errors = await scrape_run_repo.count_consecutive_errors(platform_id)
        logger.warning(
            "circuit_breaker_tick_failed",
            platform=platform.name,
            consecutive_errors=consecutive_errors,
            threshold=eff_failure_threshold,
            error=error_message,
        )

        if consecutive_errors >= eff_failure_threshold:
            paused_until = current_time + timedelta(minutes=eff_cooldown_minutes)
            reason = (
                f"Consecutive failure threshold ({eff_failure_threshold}) reached. "
                f"Latest error: {error_message}"
            )
            await platform_repo.set_paused(platform_id, paused_until, reason=reason)
            logger.error(
                "circuit_breaker_tripped",
                platform=platform.name,
                consecutive_errors=consecutive_errors,
                paused_until=paused_until.isoformat(),
                reason=reason,
            )
            return True

        return False

    async def record_success(
        self,
        platform_repo: PlatformRepository,
        platform_id: int,
    ) -> None:
        """Record a successful tick. Clears paused state if platform was previously paused."""
        platform = await platform_repo.get_by_id(platform_id)
        if platform is not None and platform.is_paused:
            await platform_repo.clear_paused(platform_id)
            logger.info(
                "circuit_breaker_reset_on_success",
                platform=platform.name,
            )
