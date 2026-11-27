from __future__ import annotations

from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

TZ_NY = ZoneInfo("America/New_York")
TZ_SH = ZoneInfo("Asia/Shanghai")


def get_market_sessions(now_utc: datetime | None = None) -> dict[str, dict[str, str | bool]]:
    """Compute live trading session state across US Equities, China A-Shares, and Crypto."""
    now = now_utc or datetime.now(UTC)

    # US Equities (NYSE / NASDAQ)
    ny = now.astimezone(TZ_NY)
    ny_t = ny.time()
    ny_wk = ny.weekday() < 5
    if ny_wk and time(9, 30) <= ny_t < time(16, 0):
        us_status = "REGULAR"
    elif ny_wk and time(4, 0) <= ny_t < time(9, 30):
        us_status = "PRE_MARKET"
    elif ny_wk and time(16, 0) <= ny_t < time(20, 0):
        us_status = "POST_MARKET"
    else:
        us_status = "CLOSED"

    # China A-Shares (SSE / SZSE / BSE): 09:15-09:25 Call Auction, 09:30-11:30 AM, 13:00-15:00 PM CST
    sh = now.astimezone(TZ_SH)
    sh_t = sh.time()
    sh_wk = sh.weekday() < 5
    if sh_wk and time(9, 15) <= sh_t < time(9, 30):
        cn_status = "AUCTION_OPEN"
    elif sh_wk and (time(9, 30) <= sh_t < time(11, 30) or time(13, 0) <= sh_t < time(15, 0)):
        cn_status = "REGULAR"
    elif sh_wk and time(11, 30) <= sh_t < time(13, 0):
        cn_status = "MIDDAY_BREAK"
    else:
        cn_status = "CLOSED"

    return {
        "US": {
            "label": "US NYSE/NASDAQ",
            "status": us_status,
            "is_open": us_status in ("REGULAR", "PRE_MARKET", "POST_MARKET"),
            "local_time": ny.strftime("%H:%M:%S %Z"),
            "settlement": "T+1",
        },
        "CN_ASHARE": {
            "label": "CN SSE/SZSE/BSE",
            "status": cn_status,
            "is_open": cn_status in ("REGULAR", "AUCTION_OPEN"),
            "local_time": sh.strftime("%H:%M:%S CST"),
            "settlement": "T+1 Strict",
        },
        "CRYPTO": {
            "label": "CRYPTO GLOBAL",
            "status": "CONTINUOUS_24_7",
            "is_open": True,
            "local_time": now.strftime("%H:%M:%S UTC"),
            "settlement": "T+0 Instant",
        },
    }
