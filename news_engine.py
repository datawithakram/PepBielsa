"""
news_engine.py — Football News Intelligence
Fetches RSS feeds and provides news summaries.
"""
import os
import json
import logging
import feedparser
from typing import List, Dict
from pathlib import Path

logger = logging.getLogger(__name__)

RSS_FEEDS = [
    "http://feeds.bbci.co.uk/sport/football/rss.xml",
    "https://www.skysports.com/football/rss",
    "https://www.espn.com/espn/rss/soccer/news",
]

_CACHE_FILE = Path("data") / "news_cache.json"


def _load_cache() -> List[Dict]:
    try:
        if _CACHE_FILE.exists():
            return json.loads(_CACHE_FILE.read_text())
    except Exception:
        pass
    return []


def _save_cache(data: List[Dict]):
    try:
        _CACHE_FILE.parent.mkdir(exist_ok=True)
        _CACHE_FILE.write_text(json.dumps(data, ensure_ascii=False))
    except Exception as e:
        logger.warning(f"Cache save failed: {e}")


def fetch_recent_news(max_per_feed: int = 3) -> List[Dict]:
    """Fetch latest football news from RSS feeds."""
    articles = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_feed]:
                articles.append({
                    "title":   entry.get("title", ""),
                    "summary": entry.get("summary", ""),
                    "link":    entry.get("link", ""),
                    "source":  url,
                })
        except Exception as e:
            logger.warning(f"RSS parse error {url}: {e}")
    return articles


def get_latest_news(force_refresh: bool = False) -> List[Dict]:
    """Return cached news or fetch fresh articles."""
    if not force_refresh:
        cached = _load_cache()
        if cached:
            return cached
    articles = fetch_recent_news()
    _save_cache(articles)
    return articles