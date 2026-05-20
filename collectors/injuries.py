"""
collectors/injuries.py
Source: Transfermarkt (scraping) + existing RSS injury feeds
Collects: squad availability · injury list · return dates
"""
import re
import logging
import time
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

TM_BASE = "https://www.transfermarkt.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0"}


class InjuriesCollector:
    """Squad availability from Transfermarkt + RSS fallback."""

    def __init__(self, delay: float = 2.0):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.delay = delay

    def _get_soup(self, url: str) -> Optional[BeautifulSoup]:
        try:
            time.sleep(self.delay)
            resp = self.session.get(url, timeout=20)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "html.parser")
        except Exception as e:
            logger.error(f"[Injuries] {url}: {e}")
            return None

    def get_team_injuries(self, tm_team_path: str) -> List[Dict]:
        """
        Scrape Transfermarkt injury table.
        tm_team_path: e.g. '/manchester-city/startseite/verein/281'
        Returns: [{ name, position, injury_type, since, until, missed_games }]
        """
        soup = self._get_soup(f"{TM_BASE}{tm_team_path}/kader")
        if not soup:
            return []
        table = soup.find("table", {"class": "items"})
        if not table:
            return []
        injuries = []
        for row in table.find("tbody").find_all("tr"):
            cols = row.find_all("td")
            if len(cols) < 4:
                continue
            try:
                injuries.append({
                    "name":         cols[1].get_text(strip=True),
                    "position":     cols[2].get_text(strip=True),
                    "injury_type":  cols[3].get_text(strip=True),
                    "since":        cols[4].get_text(strip=True) if len(cols) > 4 else "",
                    "until":        cols[5].get_text(strip=True) if len(cols) > 5 else "Unknown",
                    "missed_games": cols[6].get_text(strip=True) if len(cols) > 6 else "0",
                })
            except Exception:
                continue
        return injuries

    def get_match_availability(self, home_tm_path: str, away_tm_path: str) -> Dict:
        return {
            "home": self.get_team_injuries(home_tm_path),
            "away": self.get_team_injuries(away_tm_path),
        }

    def get_injury_news(self, max_items: int = 10) -> List[Dict]:
        """Fast RSS-based injury alerts (no scraping)."""
        try:
            from feed_fetcher import fetch_category
            return fetch_category("injuries", max_per_feed=max_items)
        except Exception as e:
            logger.error(f"[Injuries] RSS fallback: {e}")
            return []
