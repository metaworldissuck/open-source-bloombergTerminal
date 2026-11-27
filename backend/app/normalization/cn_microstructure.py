from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class PriceLimitBand:
    prev_close: float
    limit_pct: float
    limit_up: float
    limit_down: float
    hit_limit_up: bool
    hit_limit_down: bool
    pct_from_limit_up: float
    pct_from_limit_down: float


def _round_cny(val: Decimal) -> float:
    """CSRC / SSE / SZSE standard half-up rounding to 0.01 CNY."""
    return float(val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def compute_cn_price_limits(
    prev_close: float,
    current_price: float,
    limit_pct: float = 0.10,
) -> PriceLimitBand:
    """Compute exact A-share 涨停 (limit-up) and 跌停 (limit-down) prices and status flags."""
    pc = Decimal(str(prev_close))
    lp = Decimal(str(limit_pct))
    limit_up = _round_cny(pc * (Decimal(1) + lp))
    limit_down = _round_cny(pc * (Decimal(1) - lp))

    eps = 0.005
    hit_up = current_price >= (limit_up - eps)
    hit_down = current_price <= (limit_down + eps)

    pct_to_up = ((limit_up - current_price) / prev_close) * 100.0 if prev_close > 0 else 0.0
    pct_to_down = ((current_price - limit_down) / prev_close) * 100.0 if prev_close > 0 else 0.0

    return PriceLimitBand(
        prev_close=prev_close,
        limit_pct=limit_pct,
        limit_up=limit_up,
        limit_down=limit_down,
        hit_limit_up=hit_up,
        hit_limit_down=hit_down,
        pct_from_limit_up=round(pct_to_up, 2),
        pct_from_limit_down=round(pct_to_down, 2),
    )


def compute_settlement_date(trade_date: date, settlement_rule: str) -> date:
    """Calculate next business settlement date for T+1 markets vs instant T+0 for Crypto."""
    if settlement_rule == "T+0_INSTANT":
        return trade_date
    # T+1: advance to next weekday
    nxt = trade_date + timedelta(days=1)
    while nxt.weekday() >= 5:
        nxt += timedelta(days=1)
    return nxt
