"""
collectors/fotmob.py
Source: www.fotmob.com (unofficial, impersonated)
Collects: momentum · xG flow · match timeline · substitutions
"""
import logging
from typing import Dict, List, Any, Optional
from curl_cffi import requests

logger = logging.getLogger(__name__)

BASE = "https://www.fotmob.com/api"


class FotMobCollector:
    """
    Real-time momentum & xG flow source.
    FotMob offers very clean xG-by-minute data and detailed timelines.
    No API key needed — uses browser impersonation.
    """

    def __init__(self):
        self.session = requests.Session()

    def _get(self, path: str, params: Dict = None) -> Any:
        try:
            resp = self.session.get(
                f"{BASE}{path}",
                params=params or {},
                impersonate="chrome124",
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error(f"[FotMob] {path} → {e}")
        return {}

    # ── Match Details ────────────────────────────────────────────────────────

    def get_match(self, match_id: int) -> Dict:
        """
        Full match object from FotMob.
        Contains: general info, content (stats, lineup, momentum), header.
        """
        return self._get("/matchDetails", {"matchId": match_id})

    # ── Momentum ─────────────────────────────────────────────────────────────

    def get_momentum(self, match_id: int) -> List[Dict]:
        """
        Minute-by-minute momentum.
        Format: [{minute, value}] where positive = home, negative = away.
        """
        data = self.get_match(match_id)
        try:
            points = (
                data["content"]["matchFacts"]["momentum"]["main"]["data"]
            )
            return [{"minute": p.get("minute"), "value": p.get("value")} for p in points]
        except (KeyError, TypeError):
            logger.warning(f"[FotMob] Momentum not found for match {match_id}")
            return []

    # ── xG Flow ──────────────────────────────────────────────────────────────

    def get_xg_flow(self, match_id: int) -> Dict[str, List[Dict]]:
        """
        Cumulative xG flow per team over match minutes.
        Returns: { home: [{minute, xg}], away: [{minute, xg}] }
        """
        data = self.get_match(match_id)
        try:
            xg_data = data["content"]["shotmap"]["shots"]
            home_xg, away_xg = [], []
            home_cum, away_cum = 0.0, 0.0
            for shot in sorted(xg_data, key=lambda s: s.get("min", 0)):
                xg_val = shot.get("expectedGoals", 0) or 0
                minute  = shot.get("min", 0)
                if shot.get("teamId") == data["general"]["homeTeam"]["id"]:
                    home_cum += xg_val
                    home_xg.append({"minute": minute, "xg": round(home_cum, 3)})
                else:
                    away_cum += xg_val
                    away_xg.append({"minute": minute, "xg": round(away_cum, 3)})
            return {"home": home_xg, "away": away_xg}
        except (KeyError, TypeError):
            logger.warning(f"[FotMob] xG flow not found for match {match_id}")
            return {"home": [], "away": []}

    # ── Timeline ─────────────────────────────────────────────────────────────

    def get_timeline(self, match_id: int) -> List[Dict]:
        """
        Full match timeline: goals, cards, subs, VAR events.
        Each event includes minute, type, team, player.
        """
        data = self.get_match(match_id)
        try:
            events = data["content"]["matchFacts"]["events"]["events"]
            timeline = []
            for e in events:
                timeline.append({
                    "minute":    e.get("time"),
                    "type":      e.get("type"),        # goal / yellowCard / redCard / substitution
                    "team_id":   e.get("teamId"),
                    "player":    e.get("player", {}).get("name") if isinstance(e.get("player"), dict) else e.get("player"),
                    "player_id": e.get("playerId"),
                    "assist":    e.get("assistStr"),
                    "is_home":   e.get("isHome"),
                    "detail":    e.get("eventTypeId"),
                })
            return timeline
        except (KeyError, TypeError):
            logger.warning(f"[FotMob] Timeline not found for match {match_id}")
            return []

    # ── Substitutions ────────────────────────────────────────────────────────

    def get_substitutions(self, match_id: int) -> List[Dict]:
        """
        All substitutions with minute, player in, player out, team.
        """
        timeline = self.get_timeline(match_id)
        return [e for e in timeline if e.get("type") == "substitution"]

    # ── Fixture Search ───────────────────────────────────────────────────────

    def search_match_id(self, home_team: str, away_team: str, date: str) -> Optional[int]:
        """
        Try to find FotMob match ID by searching for a date's fixtures.
        date format: YYYYMMDD
        """
        data = self._get("/matches", {"date": date})
        try:
            for league in data.get("leagues", []):
                for match in league.get("matches", []):
                    h = match.get("home", {}).get("name", "").lower()
                    a = match.get("away", {}).get("name", "").lower()
                    if home_team.lower() in h and away_team.lower() in a:
                        return match.get("id")
        except Exception:
            pass
        return None
