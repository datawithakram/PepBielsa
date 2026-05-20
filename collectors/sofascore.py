"""
collectors/sofascore.py
Source: api.sofascore.app (unofficial, impersonated via curl_cffi)
Collects: heatmaps · average positions · momentum graph · shotmap · player positions
"""
import logging
from typing import Dict, List, Optional, Any
from curl_cffi import requests

logger = logging.getLogger(__name__)

BASE = "https://api.sofascore.app/api/v1"


class SofaScoreCollector:
    """
    Visual & positional data source.
    All endpoints use Chrome impersonation — no API key required.
    """

    def __init__(self):
        self.session = requests.Session()

    def _get(self, path: str) -> Any:
        try:
            resp = self.session.get(
                f"{BASE}{path}", impersonate="chrome124", timeout=15
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error(f"[SofaScore] {path} → {e}")
        return {}

    # ── Heatmaps ────────────────────────────────────────────────────────────

    def get_player_heatmap(self, event_id: int, player_id: int) -> List[Dict]:
        """
        Player heatmap as list of {x, y} coordinate objects (0–100 scale).
        Ideal for position density overlays on pitch.
        """
        data = self._get(f"/event/{event_id}/player/{player_id}/heatmap")
        return data.get("heatmap", [])

    def get_team_heatmap(self, event_id: int, team_id: int) -> List[Dict]:
        """Aggregate team heatmap (all players combined)."""
        data = self._get(f"/event/{event_id}/team/{team_id}/heatmap/overall")
        return data.get("heatmap", [])

    # ── Average Positions ───────────────────────────────────────────────────

    def get_average_positions(self, event_id: int) -> Dict[str, Any]:
        """
        Average position for every player during the match.
        Returns: { home: [{player_id, name, avgX, avgY}], away: [...] }
        """
        data = self._get(f"/event/{event_id}/average-positions")
        home = data.get("home", {})
        away = data.get("away", {})

        def _parse(side: Dict) -> List[Dict]:
            return [
                {
                    "player_id": p.get("player", {}).get("id"),
                    "name":      p.get("player", {}).get("shortName"),
                    "avgX":      p.get("averageX"),
                    "avgY":      p.get("averageY"),
                    "grid":      p.get("grid"),
                }
                for p in side.get("players", [])
            ]

        return {"home": _parse(home), "away": _parse(away)}

    # ── Momentum Graph ──────────────────────────────────────────────────────

    def get_momentum(self, event_id: int) -> List[Dict]:
        """
        Minute-by-minute momentum values.
        Positive = home team dominant, Negative = away.
        Format: [{minute, value}]
        """
        data = self._get(f"/event/{event_id}/graph")
        return [
            {"minute": p.get("minute"), "value": p.get("value")}
            for p in data.get("graphPoints", [])
        ]

    # ── Shotmap ─────────────────────────────────────────────────────────────

    def get_shotmap(self, event_id: int) -> List[Dict]:
        """
        All shots taken in the match.
        Returns normalized list with location, type, outcome, xG per shot.
        """
        data = self._get(f"/event/{event_id}/shotmap")
        shots = []
        for s in data.get("shotmap", []):
            shots.append({
                "player_id":  s.get("player", {}).get("id"),
                "player":     s.get("player", {}).get("shortName"),
                "team_id":    s.get("teamId"),
                "is_home":    s.get("isHome"),
                "minute":     s.get("time"),
                "shot_type":  s.get("shotType"),       # SavedShot / Goal / Miss / Block
                "body_part":  s.get("bodyPart"),
                "goal_parts": s.get("goalParts"),
                "xg":         s.get("xg"),
                "xgot":       s.get("xgot"),
                "x":          s.get("draw", {}).get("start", {}).get("x"),
                "y":          s.get("draw", {}).get("start", {}).get("y"),
                "end_x":      s.get("draw", {}).get("end", {}).get("x"),
                "end_y":      s.get("draw", {}).get("end", {}).get("y"),
            })
        return shots

    # ── Incidents (Goals, Cards, Subs) ──────────────────────────────────────

    def get_incidents(self, event_id: int) -> List[Dict]:
        """All match incidents with time, type, player info."""
        data = self._get(f"/event/{event_id}/incidents")
        return data.get("incidents", [])

    # ── Player Positions / Lineups ───────────────────────────────────────────

    def get_lineups(self, event_id: int) -> Dict[str, Any]:
        """Full lineup data including formation, positions, ratings."""
        data = self._get(f"/event/{event_id}/lineups")
        return data  # { home: {...}, away: {...} }

    # ── Match Statistics ─────────────────────────────────────────────────────

    def get_statistics(self, event_id: int) -> List[Dict]:
        """All grouped match stats (possession, xG, shots, etc.)."""
        data = self._get(f"/event/{event_id}/statistics")
        return data.get("statistics", [])

    # ── Team Logo / Player Photo (for visuals) ───────────────────────────────

    def get_team_logo_url(self, team_id: int) -> str:
        return f"{BASE}/team/{team_id}/image"

    def get_player_photo_url(self, player_id: int) -> str:
        return f"{BASE}/player/{player_id}/image"
