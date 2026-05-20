"""
collectors/youtube_collector.py
Source: YouTube Data API v3
Collects: press conference videos · match highlights · tactical breakdowns
"""
import os
import logging
from typing import Dict, List, Optional
from curl_cffi import requests

logger = logging.getLogger(__name__)

YT_API_BASE = "https://www.googleapis.com/youtube/v3"


class YouTubeCollector:
    """
    YouTube video discovery for football content.
    Requires: YOUTUBE_API_KEY env var (Google Cloud Console)
    Falls back gracefully if key is missing.
    """

    def __init__(self):
        self.api_key = os.getenv("YOUTUBE_API_KEY", "")
        self.session = requests.Session()
        if not self.api_key:
            logger.warning("[YouTube] No API key — searches will be skipped")

    def _get(self, endpoint: str, params: Dict) -> Dict:
        if not self.api_key:
            return {}
        try:
            params["key"] = self.api_key
            resp = self.session.get(
                f"{YT_API_BASE}/{endpoint}",
                params=params,
                impersonate="chrome124",
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"[YouTube] {endpoint}: {e}")
            return {}

    def search(self, query: str, max_results: int = 5) -> List[Dict]:
        """
        Generic YouTube search.
        Returns: [{ title, video_id, url, channel, published_at, thumbnail }]
        """
        data = self._get("search", {
            "part":       "snippet",
            "q":          query,
            "type":       "video",
            "maxResults": max_results,
            "order":      "relevance",
            "relevanceLanguage": "en",
        })
        results = []
        for item in data.get("items", []):
            snippet  = item.get("snippet", {})
            video_id = item.get("id", {}).get("videoId")
            results.append({
                "title":        snippet.get("title"),
                "video_id":     video_id,
                "url":          f"https://youtu.be/{video_id}",
                "channel":      snippet.get("channelTitle"),
                "published_at": snippet.get("publishedAt"),
                "thumbnail":    snippet.get("thumbnails", {}).get("high", {}).get("url"),
                "description":  snippet.get("description", "")[:200],
            })
        return results

    def get_press_conference(self, team: str, max_results: int = 3) -> List[Dict]:
        """Find the latest press conference video for a team."""
        return self.search(f"{team} press conference", max_results)

    def get_match_highlights(self, home: str, away: str, max_results: int = 3) -> List[Dict]:
        """Find match highlight videos."""
        return self.search(f"{home} vs {away} highlights", max_results)

    def get_tactical_analysis(self, team: str, max_results: int = 3) -> List[Dict]:
        """Find tactical breakdown / analysis videos."""
        return self.search(f"{team} tactical analysis", max_results)
