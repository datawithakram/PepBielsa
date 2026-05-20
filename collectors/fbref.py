"""
collectors/fbref.py
Source: fbref.com (scraping via requests + BeautifulSoup)
Collects: progressive passes, progressive carries, PPDA,
          touches, final third entries, pressures
"""
import logging
import time
from typing import Dict, List, Optional, Any

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE = "https://fbref.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


class FBrefCollector:
    """
    Advanced passing & pressing metrics source.
    FBref requires HTML scraping — be respectful with rate limiting.
    """

    def __init__(self, delay: float = 2.0):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.delay = delay  # seconds between requests

    def _get_soup(self, url: str) -> Optional[BeautifulSoup]:
        try:
            time.sleep(self.delay)  # polite scraping
            resp = self.session.get(url, timeout=20)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "html.parser")
        except Exception as e:
            logger.error(f"[FBref] Failed to fetch {url}: {e}")
            return None

    def _parse_table(self, soup: BeautifulSoup, table_id: str) -> List[Dict]:
        """Generic table parser → list of row dicts."""
        table = soup.find("table", {"id": table_id})
        if not table:
            return []

        headers = [th.get_text(strip=True) for th in table.find("thead").find_all("th")]
        rows = []
        for tr in table.find("tbody").find_all("tr"):
            if "class" in tr.attrs and "thead" in tr.attrs["class"]:
                continue
            cells = [td.get_text(strip=True) for td in tr.find_all(["th", "td"])]
            if cells and len(cells) == len(headers):
                rows.append(dict(zip(headers, cells)))
        return rows

    # ── Match Stats ──────────────────────────────────────────────────────────

    def get_match_stats(self, fbref_match_url: str) -> Dict[str, Any]:
        """
        Scrape a FBref match page and return:
        - progressive_passes (home/away)
        - progressive_carries (home/away)
        - ppda (home/away)
        - touches (home/away)
        - final_third_entries (home/away)
        - pressures (home/away)

        fbref_match_url: e.g. 'https://fbref.com/en/matches/abc123/...'
        """
        soup = self._get_soup(fbref_match_url)
        if not soup:
            return {}

        result: Dict[str, Any] = {}

        # Summary stats box (possession, passes, etc.)
        result["summary"]         = self._parse_summary(soup)
        result["passing"]         = self._parse_passing(soup)
        result["possession"]      = self._parse_possession(soup)
        result["defensive_actions"] = self._parse_defensive(soup)

        return result

    def _parse_summary(self, soup: BeautifulSoup) -> Dict:
        """Top-level match summary stats."""
        stats = {}
        score_div = soup.find("div", {"class": "scorebox"})
        if score_div:
            teams = score_div.find_all("strong")
            scores = score_div.find_all("div", {"class": "score"})
            if len(teams) >= 2:
                stats["home_team"] = teams[0].get_text(strip=True)
                stats["away_team"] = teams[1].get_text(strip=True)
            if len(scores) >= 2:
                stats["home_score"] = scores[0].get_text(strip=True)
                stats["away_score"] = scores[1].get_text(strip=True)
        return stats

    def _parse_passing(self, soup: BeautifulSoup) -> Dict[str, List]:
        """Progressive passes for both teams."""
        home_rows = self._parse_table(soup, "stats_a_passing")
        away_rows = self._parse_table(soup, "stats_b_passing")

        def _extract(rows: List[Dict]) -> Dict:
            total_prog = 0
            for r in rows:
                try:
                    total_prog += int(r.get("Prg", 0) or 0)
                except ValueError:
                    pass
            return {"progressive_passes": total_prog, "players": rows}

        return {"home": _extract(home_rows), "away": _extract(away_rows)}

    def _parse_possession(self, soup: BeautifulSoup) -> Dict[str, List]:
        """Progressive carries & touches in final third."""
        home_rows = self._parse_table(soup, "stats_a_possession")
        away_rows = self._parse_table(soup, "stats_b_possession")

        def _extract(rows: List[Dict]) -> Dict:
            prog_carries, final_third, touches = 0, 0, 0
            for r in rows:
                try:
                    prog_carries  += int(r.get("PrgC", 0) or 0)
                    final_third   += int(r.get("1/3",  0) or 0)
                    touches       += int(r.get("Touches", 0) or 0)
                except ValueError:
                    pass
            return {
                "progressive_carries": prog_carries,
                "final_third_entries": final_third,
                "touches":             touches,
                "players":             rows,
            }

        return {"home": _extract(home_rows), "away": _extract(away_rows)}

    def _parse_defensive(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Pressures and defensive actions. Also used to derive PPDA."""
        home_rows = self._parse_table(soup, "stats_a_defense")
        away_rows = self._parse_table(soup, "stats_b_defense")

        def _extract(rows: List[Dict]) -> Dict:
            pressures = 0
            for r in rows:
                try:
                    pressures += int(r.get("Press", 0) or 0)
                except ValueError:
                    pass
            return {"pressures": pressures, "players": rows}

        return {"home": _extract(home_rows), "away": _extract(away_rows)}

    # ── Team Season Stats ────────────────────────────────────────────────────

    def get_team_season_stats(self, team_fbref_url: str) -> List[Dict]:
        """Scrape a team's season stats page for league table & schedule."""
        soup = self._get_soup(team_fbref_url)
        if not soup:
            return []
        return self._parse_table(soup, "matchlogs_for")
