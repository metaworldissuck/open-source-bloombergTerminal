from __future__ import annotations

import re

EN_POSITIVE = {
    "beat", "beats", "surge", "surges", "record", "growth", "upgrade", "bullish",
    "outperform", "strong", "acceleration", "buyback", "dividend", "breakout",
    "inflow", "inflows", "approval", "approved", "expansion", "rally", "profit",
    "guidance raised", "higher", "milestone", "adoption",
}
EN_NEGATIVE = {
    "miss", "misses", "drop", "drops", "plunge", "downgrade", "bearish",
    "underperform", "weak", "decline", "lawsuit", "investigation", "probe",
    "outflow", "outflows", "hack", "exploit", "cut", "layoffs", "tariff",
    "sanction", "slump", "warning", "default", "liquidation", "sec charges",
}

ZH_POSITIVE = {
    "增长", "超预期", "突破", "净流入", "回购", "分红", "盈利", "利好", "涨停",
    "创新高", "增持", "签约", "中标", "领先", "复苏", "扩产", "上调",
}
ZH_NEGATIVE = {
    "下滑", "不及预期", "跌停", "净流出", "减持", "立案", "处罚", "亏损", "下调",
    "风险", "警示", "暴跌", "违规", "调查", "承压", "裁员", "违约",
}


def score_financial_sentiment(text: str, language: str = "en") -> tuple[float, str]:
    """Deterministic bilingual (EN/ZH) financial sentiment scorer returning (score, label)."""
    lowered = text.lower()
    pos_hits = 0
    neg_hits = 0

    if language == "zh" or re.search(r"[\u4e00-\u9fff]", text):
        for kw in ZH_POSITIVE:
            if kw in text:
                pos_hits += 1
        for kw in ZH_NEGATIVE:
            if kw in text:
                neg_hits += 1
    else:
        for kw in EN_POSITIVE:
            if kw in lowered:
                pos_hits += 1
        for kw in EN_NEGATIVE:
            if kw in lowered:
                neg_hits += 1

    total = pos_hits + neg_hits
    if total == 0:
        return 0.0, "NEUTRAL"

    raw = (pos_hits - neg_hits) / (total + 1.0)
    score = round(max(-1.0, min(1.0, raw * 1.25)), 3)
    if score >= 0.18:
        label = "BULLISH"
    elif score <= -0.18:
        label = "BEARISH"
    else:
        label = "NEUTRAL"
    return score, label
