from __future__ import annotations

from typing import Any

from app.storage.duckdb_engine import DuckDBEngine


class NewsService:
    """NEWS (Real-Time News, SEC/CSRC Filings & Sentiment) service."""

    def __init__(self, db: DuckDBEngine):
        self.db = db

    def list_news(
        self,
        instrument_id: str | None = None,
        sentiment: str | None = None,
        keyword: str | None = None,
        language: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        clauses: list[str] = ["1=1"]
        params: list[Any] = []

        if instrument_id:
            clauses.append("list_contains(instrument_ids, ?)")
            params.append(instrument_id)
        if sentiment and sentiment.upper() in ("BULLISH", "NEUTRAL", "BEARISH"):
            clauses.append("sentiment_label = ?")
            params.append(sentiment.upper())
        if language and language.lower() in ("en", "zh"):
            clauses.append("language = ?")
            params.append(language.lower())
        if keyword and keyword.strip():
            kw = f"%{keyword.strip().lower()}%"
            clauses.append("(LOWER(title) LIKE ? OR LOWER(COALESCE(summary, '')) LIKE ? OR LOWER(source) LIKE ?)")
            params.extend([kw, kw, kw])

        where_sql = " AND ".join(clauses)
        rows = self.db.query_dicts(
            f"""
            SELECT news_id, published_at_utc, source, language, title, summary, url,
                   instrument_ids, sentiment_score, sentiment_label, relevance_score
            FROM fact_news_sentiment
            WHERE {where_sql}
            ORDER BY published_at_utc DESC
            LIMIT ?
            """,
            [*params, limit],
        )

        items = [
            {
                "news_id": r["news_id"],
                "published_at_utc": str(r["published_at_utc"]),
                "source": r["source"],
                "language": r["language"],
                "title": r["title"],
                "summary": r["summary"],
                "url": r["url"],
                "instrument_ids": list(r["instrument_ids"] or []),
                "sentiment_score": r["sentiment_score"],
                "sentiment_label": r["sentiment_label"],
                "relevance_score": r["relevance_score"],
            }
            for r in rows
        ]

        bullish = sum(1 for x in items if x["sentiment_label"] == "BULLISH")
        bearish = sum(1 for x in items if x["sentiment_label"] == "BEARISH")
        neutral = sum(1 for x in items if x["sentiment_label"] == "NEUTRAL")
        avg_score = round(sum(float(x["sentiment_score"] or 0.0) for x in items) / len(items), 3) if items else 0.0

        return {
            "count": len(items),
            "sentiment_summary": {
                "bullish": bullish,
                "neutral": neutral,
                "bearish": bearish,
                "avg_score": avg_score,
            },
            "items": items,
        }
