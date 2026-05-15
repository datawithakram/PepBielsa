"""
feed_fetcher.py
Lightweight football news feed system.
Fetches RSS feeds and extracts: title, source, publication time, image, link.
NO analysis — pure data extraction only.
"""
import logging
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional
from urllib.parse import urlparse

import feedparser
import requests

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# RSS FEED CATALOGUE  (free, public, no auth)
# ─────────────────────────────────────────────
FEEDS: Dict[str, List[Dict]] = {
    "general": [
        {
            "url": "https://feeds.bbci.co.uk/sport/football/rss.xml",
            "source": "BBC Sport",
        },
        {
            "url": "https://www.skysports.com/rss/12040",
            "source": "Sky Sports Football",
        },
        {
            "url": "https://www.espn.com/espn/rss/soccer/news",
            "source": "ESPN Soccer",
        },
        {
            "url": "https://www.theguardian.com/football/rss",
            "source": "The Guardian Football",
        },
        {
            "url": "https://www.football365.com/feed",
            "source": "Football365",
        },
    ],
    "transfers": [
        {
            "url": "https://www.skysports.com/rss/11095",
            "source": "Sky Sports Transfers",
        },
        {
            "url": "https://www.footballtransfers.com/en/rss",
            "source": "FootballTransfers",
        },
        {
            "url": "https://www.transfermarkt.com/rss/newsartikel/rss/news",
            "source": "Transfermarkt",
        },
        {
            "url": "https://www.givemesport.com/rss/?topic=transfer-news",
            "source": "GiveMeSport Transfers",
        },
    ],
    "press_conference": [
        {
            "url": "https://www.skysports.com/rss/12040",
            "source": "Sky Sports (Press)",
            "keywords": ["press conference", "manager said", "coach said", "post-match", "pre-match"],
        },
        {
            "url": "https://www.bbc.co.uk/sport/football/rss.xml",
            "source": "BBC Sport (Press)",
            "keywords": ["press conference", "manager", "head coach"],
        },
    ],
    "injuries": [
        {
            "url": "https://www.physioroom.com/rss/feed.xml",
            "source": "PhysioRoom",
        },
        {
            "url": "https://www.skysports.com/rss/12040",
            "source": "Sky Sports (Injuries)",
            "keywords": ["injured", "injury", "ruled out", "fitness", "doubt", "return", "fracture", "knock"],
        },
        {
            "url": "https://feeds.bbci.co.uk/sport/football/rss.xml",
            "source": "BBC Sport (Injuries)",
            "keywords": ["injured", "injury", "ruled out", "fitness", "doubt"],
        },
    ],
    "breaking": [
        {
            "url": "https://www.bbc.co.uk/sport/football/rss.xml",
            "source": "BBC Sport Breaking",
        },
        {
            "url": "https://www.skysports.com/rss/12040",
            "source": "Sky Sports Breaking",
        },
        {
            "url": "https://www.goal.com/feeds/en/news",
            "source": "Goal.com Breaking",
        },
        {
            "url": "https://onefootball.com/en/feed",
            "source": "OneFootball Breaking",
        },
    ],
}

# Headlines that look like "breaking" news
BREAKING_KEYWORDS = [
    "breaking", "official", "confirmed", "done deal", "signs", "signed",
    "sacked", "fired", "appointed", "shock", "exclusive", "urgent", "alert",
    "announce", "announced", "agrees", "agree", "completes", "completed",
]

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _parse_published(entry) -> Optional[datetime]:
    """Convert feedparser time tuple → aware datetime (UTC)."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        return datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
    if hasattr(entry, "published") and entry.published:
        try:
            return parsedate_to_datetime(entry.published)
        except Exception:
            pass
    return datetime.now(timezone.utc)


def _extract_image(entry, feed_url: str) -> Optional[str]:
    """Best-effort image extraction from an RSS entry."""
    # 1. media:thumbnail
    if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
        url = entry.media_thumbnail[0].get("url")
        if url:
            return url

    # 2. media:content with medium=image
    if hasattr(entry, "media_content") and entry.media_content:
        for mc in entry.media_content:
            if mc.get("medium") == "image" or mc.get("type", "").startswith("image/"):
                url = mc.get("url")
                if url:
                    return url

    # 3. enclosures
    if hasattr(entry, "enclosures") and entry.enclosures:
        for enc in entry.enclosures:
            if "image" in enc.get("type", ""):
                return enc.get("href") or enc.get("url")

    # 4. Scan summary HTML for <img src="...">
    summary_raw = entry.get("summary", "") or ""
    img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', summary_raw)
    if img_match:
        return img_match.group(1)

    # 5. content:encoded
    if hasattr(entry, "content") and entry.content:
        for c in entry.content:
            img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', c.get("value", ""))
            if img_match:
                return img_match.group(1)

    return None


def _clean_title(title: str) -> str:
    """Strip HTML tags from title."""
    return re.sub(r"<[^>]+>", "", title).strip()


def _matches_keywords(entry, keywords: List[str]) -> bool:
    """Return True if title or summary contains any keyword (case-insensitive)."""
    haystack = (
        (entry.get("title", "") or "") + " " + (entry.get("summary", "") or "")
    ).lower()
    return any(kw.lower() in haystack for kw in keywords)


def _is_breaking(title: str) -> bool:
    return any(kw in title.lower() for kw in BREAKING_KEYWORDS)


def _build_item(entry, source_name: str, category: str) -> Optional[Dict]:
    """Build a clean news item dict from a feedparser entry."""
    title = _clean_title(entry.get("title", "")).strip()
    link = entry.get("link", "").strip()
    if not title or not link:
        return None

    published = _parse_published(entry)
    image = _extract_image(entry, link)

    return {
        "id": link,           # used as dedup key
        "title": title,
        "source": source_name,
        "published": published.isoformat() if published else None,
        "published_ts": int(published.timestamp()) if published else int(time.time()),
        "image": image,
        "link": link,
        "category": category,
        "is_breaking": _is_breaking(title),
    }


# ─────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────

def fetch_category(category: str, max_per_feed: int = 5) -> List[Dict]:
    """
    Fetch all feeds for a given category.
    Returns a flat list of clean news items sorted newest-first.
    """
    feeds = FEEDS.get(category, [])
    items: List[Dict] = []

    for feed_cfg in feeds:
        url = feed_cfg["url"]
        source = feed_cfg["source"]
        keywords = feed_cfg.get("keywords")  # optional keyword filter

        try:
            parsed = feedparser.parse(url)
            entries = parsed.entries[:max_per_feed]
        except Exception as e:
            logger.warning(f"[{source}] RSS parse failed: {e}")
            continue

        for entry in entries:
            # Apply keyword filter if defined
            if keywords and not _matches_keywords(entry, keywords):
                continue

            item = _build_item(entry, source, category)
            if item:
                items.append(item)

    # Sort newest-first
    items.sort(key=lambda x: x["published_ts"], reverse=True)
    return items


def fetch_all(max_per_feed: int = 5) -> Dict[str, List[Dict]]:
    """Fetch all categories and return a dict keyed by category name."""
    return {cat: fetch_category(cat, max_per_feed) for cat in FEEDS}


def fetch_breaking_alerts(max_per_feed: int = 10) -> List[Dict]:
    """
    Fetch recent items across all categories and return only those
    that match breaking-news keywords. Used for alert polling.
    """
    all_items: List[Dict] = []
    for cat in FEEDS:
        all_items.extend(fetch_category(cat, max_per_feed))

    breaking = [i for i in all_items if i["is_breaking"]]
    # Remove duplicates by link within this batch
    seen = set()
    unique = []
    for item in breaking:
        if item["id"] not in seen:
            seen.add(item["id"])
            unique.append(item)

    unique.sort(key=lambda x: x["published_ts"], reverse=True)
    return unique
