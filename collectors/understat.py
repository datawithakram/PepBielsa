"""
collectors/understat.py
Source: understat.com (unofficial JSON API embedded in HTML)
Collects: xG per match · shot quality · shot locations · player xG
"""
import re
import json
import logging
from typing import Dict, List, Optional, Any

import requests

logger = logging.getLogger(__name__)

BASE = "https://understat.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# Understat encodes data as JSON inside JS var declarations in page HTML
_JSON_PATTERN = re.compile(r"var\s+(\w+)\s*=\s*JSON\.parse\('(.+?)'\)", re.DOTALL)


class UnderstatCollector:
    """
    xG and shot quality source.
    Understat embeds data as JSON.parse() calls inside page HTML.
    We extract and decode them directly — no scraping of HTML tables needed.
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _get_page_data(self, url: str) -> Dict[str, Any]:
        """Fetch a page and extract all JSON.parse() variables."""
        try:
            resp = self.session.get(url, timeout=20)
            resp.raise_for_status()
            page_vars: Dict[str, Any] = {}
            for match in _JSON_PATTERN.finditer(resp.text):
                var_name   = match.group(1)
                raw_json   = match.group(2).encode().decode("unicode_escape")
                try:
                    page_vars[var_name] = json.loads(raw_json)
                except json.JSONDecodeError:
                    pass
            return page_vars
        except Exception as e:
            logger.error(f"[Understat] Failed to fetch {url}: {e}")
            return {}

    # ── Match xG & Shots ────────────────────────────────────────────────────

    def get_match_shots(self, match_id: int) -> Dict[str, List[Dict]]:
        """
        All shots in a match with xG, location, outcome.
        Returns: { h: [shots], a: [shots] }
        Shot keys: minute, result (Goal/MissedShots/SavedShot/BlockedShot),
                   X, Y, xG, player, situation, shotType.
        """
        url  = f"{BASE}/match/{match_id}"
        data = self._get_page_data(url)
        shots = data.get("shotsData", {"h": [], "a": []})
        return shots

    def get_match_xg(self, match_id: int) -> Dict[str, float]:
        """
        Aggregate xG per team for a match.
        Returns: { home: 1.45, away: 0.72 }
        """
        shots = self.get_match_shots(match_id)
        home_xg = sum(float(s.get("xG", 0) or 0) for s in shots.get("h", []))
        away_xg = sum(float(s.get("xG", 0) or 0) for s in shots.get("a", []))
        return {"home": round(home_xg, 3), "away": round(away_xg, 3)}

    def get_shot_locations(self, match_id: int) -> Dict[str, List[Dict]]:
        """
        Shot coordinates normalized to (0–1) pitch space.
        Returns: { home: [{x, y, xG, result, minute}], away: [...] }
        """
        shots = self.get_match_shots(match_id)
        result: Dict[str, List[Dict]] = {"home": [], "away": []}

        for side_key, output_key in [("h", "home"), ("a", "away")]:
            for s in shots.get(side_key, []):
                result[output_key].append({
                    "x":       float(s.get("X", 0)),
                    "y":       float(s.get("Y", 0)),
                    "xg":      float(s.get("xG", 0) or 0),
                    "result":  s.get("result"),     # Goal / SavedShot / MissedShots / BlockedShot
                    "minute":  s.get("minute"),
                    "player":  s.get("player"),
                    "shot_type": s.get("shotType"), # LeftFoot / RightFoot / Head
                    "situation": s.get("situation"),# OpenPlay / SetPiece / FromCorner / Penalty
                })
        return result

    # ── xG Flow (cumulative) ─────────────────────────────────────────────────

    def get_xg_flow(self, match_id: int) -> Dict[str, List[Dict]]:
        """
        Cumulative xG over time for home and away.
        Returns: { home: [{minute, cumulative_xg}], away: [...] }
        """
        shots = self.get_match_shots(match_id)
        result: Dict[str, List] = {"home": [], "away": []}

        for side_key, output_key in [("h", "home"), ("a", "away")]:
            cumulative = 0.0
            for s in sorted(shots.get(side_key, []), key=lambda x: int(x.get("minute", 0))):
                cumulative += float(s.get("xG", 0) or 0)
                result[output_key].append({
                    "minute": int(s.get("minute", 0)),
                    "xg":     round(cumulative, 3),
                })
        return result

    # ── Player xG (season) ───────────────────────────────────────────────────

    def get_player_xg(self, player_id: int) -> List[Dict]:
        """
        Per-match xG for a player over the season.
        Returns list of { match_id, date, h_a, xG, xA, goals, assists, time }
        """
        url  = f"{BASE}/player/{player_id}"
        data = self._get_page_data(url)
        return data.get("matchesData", [])

    # ── League xG Table ──────────────────────────────────────────────────────

    def get_league_xg_table(self, league: str, season: int) -> List[Dict]:
        """
        xG table for a full league season.
        league: 'EPL', 'La_liga', 'Bundesliga', 'Serie_A', 'Ligue_1', 'RFPL'
        Returns: list of { team, xG, xGA, xPTS, ... }
        """
        url  = f"{BASE}/league/{league}/{season}"
        data = self._get_page_data(url)
        return data.get("teamsData", {})
