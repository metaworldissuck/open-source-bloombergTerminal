from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class AdapterProvenance:
    adapter_name: str
    is_live: bool
    fetched_at_epoch: float
    warning: str | None = None


class CircuitBreaker:
    """Simple per-adapter circuit breaker to avoid hanging on blocked/rate-limited upstream APIs."""

    def __init__(self, failure_threshold: int = 3, recovery_timeout_sec: float = 120.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout_sec = recovery_timeout_sec
        self._failures = 0
        self._opened_at: float | None = None

    def allow_request(self) -> bool:
        if self._opened_at is None:
            return True
        if (time.monotonic() - self._opened_at) >= self.recovery_timeout_sec:
            self._opened_at = None
            self._failures = 0
            return True
        return False

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._opened_at = time.monotonic()


class MarketDataAdapter(ABC):
    name: str = "base"
    supported_markets: tuple[str, ...] = ()

    def __init__(self) -> None:
        self.breaker = CircuitBreaker()

    @abstractmethod
    async def fetch_ohlcv(
        self, instrument: dict[str, Any], timeframe: str = "1d", limit: int = 250
    ) -> list[dict[str, Any]]:
        """Fetch normalized OHLCV rows for an instrument."""

    @abstractmethod
    async def fetch_quote(self, instrument: dict[str, Any]) -> dict[str, Any] | None:
        """Fetch latest quote snapshot for an instrument."""
