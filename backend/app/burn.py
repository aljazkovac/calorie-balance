from dataclasses import dataclass
from datetime import date
from typing import Protocol

from .config import settings


@dataclass
class DailyBurn:
    date: date
    total_kcal: int  # what the balance screen shows
    active_kcal: int | None
    source: str  # "fixed", "strava+bmr", "coros", ...


class BurnProvider(Protocol):
    async def get_daily_burn(self, day: date) -> DailyBurn: ...


class FixedBurnProvider:
    """Placeholder: the same burned value every day, from FIXED_BURNED_KCAL."""

    async def get_daily_burn(self, day: date) -> DailyBurn:
        return DailyBurn(day, settings.fixed_burned_kcal, None, "fixed")


burn_provider: BurnProvider = FixedBurnProvider()
