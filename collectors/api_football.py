"""
collectors/api_football.py
Source: api-football.com (RapidAPI)
Collects: fixtures, lineups, players, events, standings, formations
"""
import os
import logging
from typing import Dict, List, Optional, Any
from curl_cffi import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://v3.football.api-sports.io"


class APIFootballCollector:
    """
    Primary stats source.
    Provides: fixtures · lineups · player stats · events · standings · formations
    """

    def __init__(self):
        self.key = os.getenv("API_FOOTBALL_KEY", "")
        self.session = requests.Session()
        self.headers = {
            "x-apisports-key": self.key,
        }

    def _get(self, endpoint: str, params: Dict = None) -> Dict:
        try:
            url = f"{BASE_URL}/{endpoint}"
            resp = self.session.get(
                url, headers=self.headers, params=params or {},
                impersonate="chrome124", timeout=15
            )
            resp.raise_for_status()
            data = resp.json()
            errors = data.get("errors", {})
            if errors:
                logger.warning(f"[APIFootball] API errors on {endpoint}: {errors}")
            return data.get("response", [])
        except Exception as e:
            logger.error(f"[APIFootball] {endpoint} failed: {e}")
            return []

    # ── Fixtures ────────────────────────────────────────────────────────────

    def get_fixture(self, fixture_id: int) -> Dict:
        """Full fixture data by ID."""
        results = self._get("fixtures", {"id": fixture_id})
        return results[0] if results else {}

    def get_fixtures_by_date(self, date: str, league_id: int = None) -> List[Dict]:
        """All fixtures for a given date (YYYY-MM-DD), optionally filtered by league."""
        params = {"date": date, "timezone": "UTC"}
        if league_id:
            params["league"] = league_id
        return self._get("fixtures", params)

    def get_live_fixtures(self, league_id: int = None) -> List[Dict]:
        """All currently live matches."""
        params = {"live": "all"}
        if league_id:
            params["league"] = league_id
        return self._get("fixtures", params)

    # ── Lineups & Formations ────────────────────────────────────────────────

    def get_lineups(self, fixture_id: int) -> Dict[str, Any]:
        """
        Returns home/away lineups including:
        - formation string (e.g. '4-3-3')
        - starting XI with positions and grids
        - substitutes
        """
        results = self._get("fixtures/lineups", {"fixture": fixture_id})
        if not results:
            return {"home": {}, "away": {}}

        home = results[0] if len(results) > 0 else {}
        away = results[1] if len(results) > 1 else {}

        def _parse_side(side: Dict) -> Dict:
            return {
                "team":      side.get("team", {}).get("name"),
                "team_id":   side.get("team", {}).get("id"),
                "formation": side.get("formation"),
                "coach":     side.get("coach", {}).get("name"),
                "startXI":   side.get("startXI", []),
                "substitutes": side.get("substitutes", []),
            }

        return {"home": _parse_side(home), "away": _parse_side(away)}

    # ── Players ─────────────────────────────────────────────────────────────

    def get_player_stats(self, fixture_id: int) -> List[Dict]:
        """
        Per-player statistics for a fixture:
        shots, passes, dribbles, tackles, duels, cards, rating.
        """
        results = self._get("fixtures/players", {"fixture": fixture_id})
        players = []
        for team_block in results:
            team_name = team_block.get("team", {}).get("name")
            team_id   = team_block.get("team", {}).get("id")
            for p in team_block.get("players", []):
                info  = p.get("player", {})
                stats = p.get("statistics", [{}])[0]
                players.append({
                    "player_id":   info.get("id"),
                    "name":        info.get("name"),
                    "team":        team_name,
                    "team_id":     team_id,
                    "position":    stats.get("games", {}).get("position"),
                    "rating":      stats.get("games", {}).get("rating"),
                    "minutes":     stats.get("games", {}).get("minutes"),
                    "shots":       stats.get("shots", {}),
                    "goals":       stats.get("goals", {}),
                    "passes":      stats.get("passes", {}),
                    "dribbles":    stats.get("dribbles", {}),
                    "tackles":     stats.get("tackles", {}),
                    "duels":       stats.get("duels", {}),
                    "fouls":       stats.get("fouls", {}),
                    "cards":       stats.get("cards", {}),
                })
        return players

    # ── Events ──────────────────────────────────────────────────────────────

    def get_events(self, fixture_id: int) -> List[Dict]:
        """
        All match events: goals, cards, substitutions.
        Returns normalized list with time, type, player, team.
        """
        results = self._get("fixtures/events", {"fixture": fixture_id})
        events = []
        for e in results:
            events.append({
                "minute":      e.get("time", {}).get("elapsed"),
                "extra":       e.get("time", {}).get("extra"),
                "team":        e.get("team", {}).get("name"),
                "team_id":     e.get("team", {}).get("id"),
                "player":      e.get("player", {}).get("name"),
                "player_id":   e.get("player", {}).get("id"),
                "assist":      e.get("assist", {}).get("name"),
                "type":        e.get("type"),       # Goal / Card / Subst
                "detail":      e.get("detail"),     # Normal Goal / Yellow Card / etc.
                "comments":    e.get("comments"),
            })
        return events

    # ── Standings ───────────────────────────────────────────────────────────

    def get_standings(self, league_id: int, season: int) -> List[Dict]:
        """League table for a given league and season."""
        results = self._get("standings", {"league": league_id, "season": season})
        try:
            return results[0]["league"]["standings"][0]
        except (IndexError, KeyError):
            return []

    # ── Statistics (match-level) ─────────────────────────────────────────────

    def get_match_statistics(self, fixture_id: int) -> Dict[str, Any]:
        """
        Team-level match stats:
        possession, shots on/off, fouls, corners, offsides, yellow/red cards, saves.
        """
        results = self._get("fixtures/statistics", {"fixture": fixture_id})
        output = {}
        for team_block in results:
            team_name = team_block.get("team", {}).get("name")
            stats_raw = team_block.get("statistics", [])
            flat = {s["type"]: s["value"] for s in stats_raw}
            output[team_name] = flat
        return output
