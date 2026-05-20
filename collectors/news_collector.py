"""
collectors/news_collector.py
Sources: RSS feeds + Google News (via feed_fetcher)
Collects: breaking news · transfers · press conferences · injuries news
"""
import logging
from typing import Dict, List, Optional
from feed_fetcher import fetch_category, fetch_breaking_alerts, fetch_all

logger = logging.getLogger(__name__)


class NewsCollector:
    """
    Football news aggregator.
    Wraps feed_fetcher with extra filtering and team-specific search.
    """

    def get_breaking(self, max_items: int = 5) -> List[Dict]:
        """Latest breaking news across all categories."""
        return fetch_breaking_alerts(max_per_feed=max_items)

    def get_category(self, category: str, max_items: int = 5) -> List[Dict]:
        """News for a specific category: general / transfers / injuries / press_conference."""
        return fetch_category(category, max_per_feed=max_items)

    def get_all(self, max_items: int = 3) -> Dict[str, List[Dict]]:
        """All categories combined."""
        return fetch_all(max_per_feed=max_items)

    def get_team_news(self, team_name: str, max_items: int = 10) -> List[Dict]:
        """
        Filter news items mentioning a specific team name.
        Searches across all categories.
        """
        all_items: List[Dict] = []
        for items in fetch_all(max_per_feed=max_items).values():
            all_items.extend(items)

        team_lower = team_name.lower()
        filtered = [
            item for item in all_items
            if team_lower in item.get("title", "").lower()
            or team_lower in item.get("source", "").lower()
        ]
        # Deduplicate by link
        seen, unique = set(), []
        for item in filtered:
            if item["id"] not in seen:
                seen.add(item["id"])
                unique.append(item)
        return sorted(unique, key=lambda x: x["published_ts"], reverse=True)

    def get_press_conference(self, team_name: Optional[str] = None) -> List[Dict]:
        """Press conference summaries, optionally filtered by team."""
        items = fetch_category("press_conference", max_per_feed=10)
        if team_name:
            items = [i for i in items if team_name.lower() in i.get("title", "").lower()]
        return items
