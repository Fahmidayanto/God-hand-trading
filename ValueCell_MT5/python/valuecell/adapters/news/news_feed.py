"""
News Feed Adapter (Sprint 1)

Wraps ``news_agent.tools.web_search`` with a TTL cache and a thin parser that
splits the LLM-summarized text into headline-shaped chunks suitable for
``SentimentAgent.analyze(news_headlines=...)``.

Ponytail choices:
- No new dependencies (uses stdlib ``re`` + lazy import of news_agent)
- Cache is in-process; one fetch per TTL window is enough for shadow mode
- Failure returns whatever is in cache (or empty list); never raises into
  the trading cycle so a flaky Perplexity/Gemini call can't break the system
- Each headline is stamped with ``timestamp=now`` so SentimentAgent's recency
  weighting treats them as fresh, and tagged with ``source`` (provider name)
  so DecisionLogger can attribute per-source PnL (Sprint 4 #17).
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from loguru import logger


# Default query tuned for XAUUSD; ``sector="gold"`` was the recommendation from
# the Sprint 1 landscape review, but raw web_search gives more flexible query
# control so we keep it inline.
DEFAULT_QUERY = "gold XAUUSD market news today safe haven dollar fed"


def _get_web_search():
    """Lazy import — news_agent pulls in agno which may not be installed everywhere."""
    from valuecell.agents.news_agent.tools import web_search

    return web_search


class NewsFeed:
    """Lightweight async-first wrapper around ``news_agent.web_search``.

    Parameters
    ----------
    query : str
        Search query passed to the underlying web search provider.
    ttl_minutes : int
        Cache lifetime. Default 10 minutes — short enough that sentiment
        reflects current news, long enough that we don't spam the API on a
        5-second polling loop.
    max_headlines : int
        Hard cap on parsed headlines per fetch to bound downstream cost.
    """

    _SENT_SPLIT = re.compile(r"\n+|(?<=[.!?])\s+(?=[A-Z])")

    def __init__(
        self,
        query: str = DEFAULT_QUERY,
        ttl_minutes: int = 10,
        max_headlines: int = 30,
    ) -> None:
        self.query = query
        self.ttl = timedelta(minutes=ttl_minutes)
        self.max_headlines = max_headlines
        self._cache: List[Dict[str, Any]] = []
        self._cached_at: Optional[datetime] = None
        logger.info(
            f"NewsFeed initialized | query='{query[:50]}...' | "
            f"ttl={ttl_minutes}m | max_headlines={max_headlines}"
        )

    def _is_cache_fresh(self, now: datetime) -> bool:
        if self._cached_at is None or not self._cache:
            return False
        return (now - self._cached_at) < self.ttl

    async def fetch(self, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Return list of ``{headline, timestamp}`` dicts.

        On any failure, returns the last-known-good cache (possibly empty).
        Never raises — the trading cycle must not depend on news availability.
        """
        now = now or datetime.now()

        if self._is_cache_fresh(now):
            age = (now - self._cached_at).total_seconds() if self._cached_at else 0.0
            logger.debug(
                f"NewsFeed cache HIT | {len(self._cache)} headlines | age={age:.0f}s"
            )
            return list(self._cache)

        try:
            web_search = _get_web_search()
            logger.info(f"NewsFeed cache MISS → fetching: '{self.query[:60]}...'")
            raw = await web_search(self.query)
            parsed = self._split_into_headlines(raw or "", now)
            self._cache = parsed
            self._cached_at = now
            logger.info(f"NewsFeed fetched {len(parsed)} headlines")
            return list(parsed)
        except Exception as e:
            logger.error(f"NewsFeed fetch failed: {e} | serving stale ({len(self._cache)} items)")
            # Stale-while-error: better than dropping all context
            return list(self._cache)

    def fetch_sync(self, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Sync wrapper for callers that aren't async (e.g. ``TradingSystem``).

        Uses ``asyncio.run`` — fine because ``TradingSystem._fetch_market_data``
        is called once per new bar (every 15 min on M15), not in a hot loop.
        """
        try:
            asyncio.get_running_loop()
            # Already in an async context — fall back to direct thread run.
            # This branch is defensive: the current ``TradingSystem`` flow is
            # sync, so we expect the outer branch.
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(asyncio.run, self.fetch(now))
                return future.result(timeout=30)
        except RuntimeError:
            # No running loop — safe to use asyncio.run directly.
            return asyncio.run(self.fetch(now))

    def _split_into_headlines(
        self, raw: str, ts: datetime
    ) -> List[Dict[str, Any]]:
        """Parse a blob of LLM-summarized news into headline-shaped chunks.

        Heuristics:
        - Split on newlines or sentence boundaries.
        - Drop bullets/leading dashes, normalize whitespace.
        - Keep chunks between 15 and 400 chars with at least one space
          (filters out trivial fragments and the LLM's wrapper prose).
        """
        if not raw:
            return []

        text = raw.strip()
        chunks = self._SENT_SPLIT.split(text)

        headlines: List[Dict[str, Any]] = []
        for chunk in chunks:
            cleaned = chunk.strip(" -\t•*#")
            if len(cleaned) < 15 or len(cleaned) > 400:
                continue
            if " " not in cleaned:
                continue
            headlines.append({"headline": cleaned, "timestamp": ts, "source": "web_search"})
            if len(headlines) >= self.max_headlines:
                break

        return headlines

    def clear_cache(self) -> None:
        """Force the next fetch to re-query the upstream provider."""
        self._cache = []
        self._cached_at = None

    def get_info(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "ttl_minutes": self.ttl.total_seconds() / 60,
            "max_headlines": self.max_headlines,
            "cache_size": len(self._cache),
            "cache_age_seconds": (
                (datetime.now() - self._cached_at).total_seconds()
                if self._cached_at
                else None
            ),
        }


# ========== STANDALONE TEST ==========

if __name__ == "__main__":
    import json

    feed = NewsFeed(ttl_minutes=1, max_headlines=10)
    print("Testing NewsFeed (will hit upstream API — needs GOOGLE_API_KEY or "
          "OPENROUTER_API_KEY env vars)...")
    try:
        headlines = feed.fetch_sync()
        print(f"\nFetched {len(headlines)} headlines:")
        for i, h in enumerate(headlines[:5], 1):
            print(f"  {i}. {h['headline'][:100]}...")
        print(f"\nFeed info: {json.dumps(feed.get_info(), indent=2, default=str)}")
    except Exception as e:
        print(f"\nFAILED (expected if no API key set): {e}")