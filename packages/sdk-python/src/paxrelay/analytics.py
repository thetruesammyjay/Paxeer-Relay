"""Spend and capability analytics methods for the Python SDK."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Literal

from paxrelay.models import AnalyticsCapability, AnalyticsSpend

if TYPE_CHECKING:
    from paxrelay.client import AsyncPaxRelayClient

AnalyticsPeriod = Literal["daily", "monthly"]


class AnalyticsResource:
    """Read tenant-scoped spend analytics from the API."""

    def __init__(self, client: AsyncPaxRelayClient) -> None:
        self._client = client

    async def spend(
        self,
        *,
        period: AnalyticsPeriod = "daily",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> AnalyticsSpend:
        """Return a committed-spend total over an optional date range."""
        params = _date_params(start_date, end_date)
        params["period"] = period
        result = await self._client._request(
            "GET", "analytics/spend", params=params
        )
        return AnalyticsSpend.model_validate(result)

    async def capabilities(
        self,
        *,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 20,
    ) -> list[AnalyticsCapability]:
        """Return committed-spend totals grouped by capability."""
        params = _date_params(start_date, end_date)
        params["limit"] = limit
        result = await self._client._request(
            "GET", "analytics/capabilities", params=params
        )
        return [AnalyticsCapability.model_validate(item) for item in result]


def _date_params(
    start_date: datetime | None,
    end_date: datetime | None,
) -> dict[str, object]:
    """Serialize optional date bounds for the API's datetime query parameters."""
    return {
        key: value.isoformat()
        for key, value in {
            "start_date": start_date,
            "end_date": end_date,
        }.items()
        if value is not None
    }
