"""
collectors/statsbomb.py
Source: StatsBomb Open Data (GitHub) + statsbombpy library
Collects: event coordinates · pass locations · pressure data · open data
"""
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

try:
    from statsbombpy import sb
    _SB_AVAILABLE = True
except ImportError:
    _SB_AVAILABLE = False
    logger.warning("[StatsBomb] statsbombpy not installed. Run: pip install statsbombpy")

try:
    import pandas as pd
    _PD_AVAILABLE = True
except ImportError:
    _PD_AVAILABLE = False


class StatsBombCollector:
    """
    Event-level coordinate data source.
    Uses StatsBomb Open Data (free) via statsbombpy.
    For commercial data, set SB_USERNAME and SB_PASSWORD env vars.
    """

    def __init__(self):
        if not _SB_AVAILABLE:
            raise RuntimeError(
                "statsbombpy is required: pip install statsbombpy"
            )

    # ── Open Data Catalog ───────────────────────────────────────────────────

    def get_competitions(self) -> List[Dict]:
        """All competitions available in StatsBomb Open Data."""
        df = sb.competitions()
        return df.to_dict("records") if _PD_AVAILABLE else []

    def get_matches(self, competition_id: int, season_id: int) -> List[Dict]:
        """All matches for a competition + season."""
        df = sb.matches(competition_id=competition_id, season_id=season_id)
        return df.to_dict("records") if _PD_AVAILABLE else []

    # ── Event Data ──────────────────────────────────────────────────────────

    def get_events(self, match_id: int) -> List[Dict]:
        """
        All events for a match.
        Each event has: type, location [x,y], player, team, timestamp, etc.
        """
        try:
            df = sb.events(match_id=match_id)
            if _PD_AVAILABLE:
                return df.to_dict("records")
            return []
        except Exception as e:
            logger.error(f"[StatsBomb] events({match_id}) failed: {e}")
            return []

    # ── Pass Locations ──────────────────────────────────────────────────────

    def get_pass_locations(self, match_id: int) -> Dict[str, List[Dict]]:
        """
        All passes with start [x,y] and end [x,y] coordinates.
        Returns: { home: [passes], away: [passes] }
        Each pass: { player, x, y, end_x, end_y, outcome, length, angle }
        """
        events = self.get_events(match_id)
        result: Dict[str, List] = {"home": [], "away": []}

        for e in events:
            if e.get("type", {}) == "Pass" or (
                isinstance(e.get("type"), dict) and e["type"].get("name") == "Pass"
            ):
                pass_obj = e.get("pass", {})
                loc      = e.get("location", [None, None])
                end_loc  = pass_obj.get("end_location", [None, None])
                team_key = "home" if e.get("possession_team", {}) == e.get("home_team") else "away"

                result[team_key].append({
                    "player":      e.get("player", {}).get("name") if isinstance(e.get("player"), dict) else e.get("player"),
                    "x":           loc[0] if loc else None,
                    "y":           loc[1] if loc else None,
                    "end_x":       end_loc[0] if end_loc else None,
                    "end_y":       end_loc[1] if end_loc else None,
                    "outcome":     pass_obj.get("outcome", {}).get("name") if isinstance(pass_obj.get("outcome"), dict) else pass_obj.get("outcome"),
                    "length":      pass_obj.get("length"),
                    "angle":       pass_obj.get("angle"),
                    "progressive": pass_obj.get("technique", {}).get("name") if isinstance(pass_obj.get("technique"), dict) else None,
                })
        return result

    # ── Pressure Data ───────────────────────────────────────────────────────

    def get_pressure_data(self, match_id: int) -> Dict[str, List[Dict]]:
        """
        All pressure events with location [x,y].
        Returns: { home: [pressures], away: [pressures] }
        Useful for PPDA calculation and pressing heatmaps.
        """
        events = self.get_events(match_id)
        result: Dict[str, List] = {"home": [], "away": []}

        for e in events:
            type_name = e.get("type", {})
            if isinstance(type_name, dict):
                type_name = type_name.get("name", "")
            if type_name != "Pressure":
                continue

            loc = e.get("location", [None, None])
            team_key = "home" if e.get("index", 0) % 2 == 0 else "away"

            result[team_key].append({
                "player":    e.get("player", {}).get("name") if isinstance(e.get("player"), dict) else e.get("player"),
                "x":         loc[0] if loc else None,
                "y":         loc[1] if loc else None,
                "minute":    e.get("minute"),
                "second":    e.get("second"),
                "duration":  e.get("duration"),
            })
        return result

    # ── Event Coordinates (generic) ──────────────────────────────────────────

    def get_event_coordinates(self, match_id: int, event_type: str) -> List[Dict]:
        """
        Generic extractor: get all [x,y] coordinates for any event type.
        event_type: 'Shot', 'Pass', 'Dribble', 'Carry', 'Pressure', etc.
        """
        events = self.get_events(match_id)
        result = []
        for e in events:
            type_name = e.get("type", {})
            if isinstance(type_name, dict):
                type_name = type_name.get("name", "")
            if type_name == event_type:
                loc = e.get("location", [None, None])
                result.append({
                    "x":      loc[0] if loc else None,
                    "y":      loc[1] if loc else None,
                    "player": e.get("player", {}).get("name") if isinstance(e.get("player"), dict) else e.get("player"),
                    "team":   e.get("team", {}).get("name") if isinstance(e.get("team"), dict) else e.get("team"),
                    "minute": e.get("minute"),
                })
        return result
