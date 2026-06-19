"""
News Feed Service - Mengambil berita terkini untuk XAUUSD/Gold dari RSS feed publik.

Strategi:
1. Primary: RSS feed gratis dari Reuters, FXStreet Gold, MarketWatch
2. Optional: NewsAPI jika NEWS_API_KEY tersedia di .env
3. Cache in-memory 5 menit agar tidak spam request setiap 30 detik pipeline

Output: List of headline strings siap dikonsumsi oleh SentimentAgent.
"""

import logging
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ─── Cache ─────────────────────────────────────────────────────────────────────
_CACHE_TTL_SECONDS = 300  # 5 menit
_cache: Dict[str, Tuple[float, List[str]]] = {}

# ─── RSS Feed Sources untuk Gold/XAUUSD ────────────────────────────────────────
RSS_FEEDS = [
    {
        "name": "Reuters Markets",
        "url": "https://feeds.reuters.com/reuters/businessNews",
        "gold_keywords": ["gold", "xauusd", "bullion", "precious metal", "federal reserve", "fed", "inflation", "dollar"],
    },
    {
        "name": "MarketWatch Markets",
        "url": "https://feeds.marketwatch.com/marketwatch/marketpulse/",
        "gold_keywords": ["gold", "xau", "bullion", "fed", "dollar", "inflation", "commodities"],
    },
    {
        "name": "FXStreet Gold",
        "url": "https://www.fxstreet.com/rss/news",
        "gold_keywords": ["gold", "xauusd", "xau/usd", "precious", "fed", "dollar", "inflation"],
    },
]

# Keyword filter: hanya ambil berita yang relevan dengan gold
RELEVANCE_KEYWORDS = [
    "gold", "xauusd", "xau", "bullion", "precious metal",
    "federal reserve", "fed rate", "inflation", "cpi", "dollar",
    "safe haven", "commodities", "gdp", "nfp", "payroll",
    "recession", "yield", "treasury", "powell", "fomc",
]


def _is_relevant(title: str, description: str = "") -> bool:
    """Cek apakah berita relevan dengan gold/forex trading."""
    text = (title + " " + description).lower()
    return any(kw in text for kw in RELEVANCE_KEYWORDS)


def _fetch_rss_headlines(feed_url: str, gold_keywords: List[str], max_age_hours: int = 24) -> List[str]:
    """
    Ambil headlines dari satu RSS feed URL.
    Hanya ambil berita yang mengandung keyword relevan gold.
    """
    try:
        import urllib.request
        import urllib.error

        req = urllib.request.Request(
            feed_url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; ValueCell/1.0; +trading-bot)",
                "Accept": "application/rss+xml, application/xml, text/xml, */*",
            }
        )

        with urllib.request.urlopen(req, timeout=5) as response:
            raw_xml = response.read()

        root = ET.fromstring(raw_xml)

        # Namespace handling untuk berbagai format RSS
        ns = ""
        if root.tag.startswith("{"):
            ns = root.tag.split("}")[0] + "}"

        headlines = []
        now_utc = datetime.now(timezone.utc)

        # Navigasi ke items (RSS 2.0: channel > item, Atom: entry)
        items = root.findall(f".//{ns}item") or root.findall(".//item")
        if not items:
            items = root.findall(f".//{ns}entry") or root.findall(".//entry")

        for item in items[:30]:  # Maksimal 30 item per feed
            # Ambil title
            title_el = item.find(f"{ns}title") or item.find("title")
            if title_el is None or not title_el.text:
                continue
            title = title_el.text.strip()

            # Ambil description untuk filter relevansi
            desc_el = item.find(f"{ns}description") or item.find("description") or item.find(f"{ns}summary") or item.find("summary")
            description = (desc_el.text or "") if desc_el is not None else ""

            # Filter hanya berita relevan gold
            if not _is_relevant(title, description):
                continue

            headlines.append(title)

        return headlines

    except Exception as exc:
        logger.debug(f"[NewsFeed] Failed to fetch {feed_url}: {exc}")
        return []


def _fetch_newsapi_headlines(api_key: str, max_items: int = 15) -> List[str]:
    """
    Ambil berita dari NewsAPI.org jika API key tersedia.
    NewsAPI free tier: 100 requests/day
    """
    try:
        import urllib.request
        import urllib.parse
        import json

        params = urllib.parse.urlencode({
            "q": "gold OR XAUUSD OR \"federal reserve\" OR \"gold price\"",
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": max_items,
            "apiKey": api_key,
        })
        url = f"https://newsapi.org/v2/everything?{params}"

        req = urllib.request.Request(url, headers={"User-Agent": "ValueCell/1.0"})
        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read())

        if data.get("status") != "ok":
            return []

        headlines = []
        for article in data.get("articles", [])[:max_items]:
            title = article.get("title", "").strip()
            if title and title != "[Removed]":
                headlines.append(title)

        logger.debug(f"[NewsFeed] NewsAPI returned {len(headlines)} headlines")
        return headlines

    except Exception as exc:
        logger.debug(f"[NewsFeed] NewsAPI failed: {exc}")
        return []


def fetch_gold_news_headlines(max_age_hours: int = 24, max_items: int = 20) -> List[str]:
    """
    Ambil headline berita terkini yang relevan dengan XAUUSD/Gold.

    Urutan prioritas:
    1. Return dari cache jika masih segar (< 5 menit)
    2. Coba NewsAPI jika NEWS_API_KEY tersedia
    3. Fallback ke RSS feed publik (Reuters, MarketWatch, FXStreet)
    4. Return [] jika semua gagal (pipeline tetap berjalan)

    Args:
        max_age_hours: Batas usia berita yang diterima (default: 24 jam)
        max_items: Maksimal jumlah headline yang dikembalikan

    Returns:
        List of headline strings dalam bahasa Inggris
    """
    cache_key = "gold_news"
    now = time.time()

    # Cek cache
    if cache_key in _cache:
        cached_time, cached_data = _cache[cache_key]
        if now - cached_time < _CACHE_TTL_SECONDS:
            logger.debug(f"[NewsFeed] Returning {len(cached_data)} cached headlines")
            return cached_data

    headlines: List[str] = []

    # 1. Coba NewsAPI (jika API key ada dan valid)
    news_api_key = os.getenv("NEWS_API_KEY", "")
    if news_api_key and news_api_key != "your_newsapi_key_here":
        headlines = _fetch_newsapi_headlines(news_api_key, max_items=max_items)
        if headlines:
            logger.info(f"[NewsFeed] NewsAPI: {len(headlines)} headlines fetched")

    # 2. Fallback ke RSS jika NewsAPI kosong atau tidak tersedia
    if not headlines:
        for feed in RSS_FEEDS:
            feed_headlines = _fetch_rss_headlines(
                feed_url=feed["url"],
                gold_keywords=feed["gold_keywords"],
                max_age_hours=max_age_hours,
            )
            headlines.extend(feed_headlines)
            if feed_headlines:
                logger.debug(f"[NewsFeed] {feed['name']}: {len(feed_headlines)} headlines")

            # Hentikan jika sudah cukup
            if len(headlines) >= max_items:
                break

    # Deduplicate dan batasi
    seen = set()
    unique_headlines = []
    for h in headlines:
        normalized = h.lower().strip()
        if normalized not in seen:
            seen.add(normalized)
            unique_headlines.append(h)
        if len(unique_headlines) >= max_items:
            break

    # Simpan ke cache
    _cache[cache_key] = (now, unique_headlines)

    if unique_headlines:
        logger.info(f"[NewsFeed] Total {len(unique_headlines)} unique gold-relevant headlines fetched")
    else:
        logger.debug("[NewsFeed] No headlines fetched — Sentiment Agent will use neutral baseline")

    return unique_headlines
