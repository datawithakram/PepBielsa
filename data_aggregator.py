"""
data_aggregator.py — SofaScore Exclusive Scraping Engine
Collects deep Match, Tactical, Player, and Timeline data from SofaScore.
"""
import logging
from curl_cffi import requests
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class DataAggregator:
    def __init__(self):
        self.domains = [
            "https://api.sofascore.com/api/v1",
            "https://api.sofascore.app/api/v1"
        ]
        self.session = requests.Session()

    def _request(self, path: str, timeout: int = 15) -> Optional[requests.Response]:
        """
        Robust request helper that tries multiple SofaScore domains (.com and .app)
        and sends browser-like headers to bypass Cloudflare regional/VPS blocks.
        """
        headers = {
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.sofascore.com/",
            "Origin": "https://www.sofascore.com",
            "Cache-Control": "max-age=0",
        }
        
        last_err = None
        for base in self.domains:
            url = f"{base}{path}"
            try:
                resp = self.session.get(
                    url, 
                    headers=headers, 
                    impersonate="chrome124", 
                    timeout=timeout
                )
                if resp.status_code == 200:
                    return resp
                else:
                    logger.warning(f"SofaScore request to {url} returned status {resp.status_code}")
                    last_err = f"HTTP {resp.status_code}"
            except Exception as e:
                logger.warning(f"SofaScore request to {url} failed: {e}")
                last_err = str(e)
                
        raise Exception(f"All SofaScore domains failed. Last error: {last_err}")

    def _get_json(self, path: str, timeout: int = 15) -> Any:
        """Helper to safely fetch and return JSON from SofaScore API."""
        try:
            resp = self._request(path, timeout=timeout)
            if resp:
                return resp.json()
        except Exception as e:
            logger.error(f"[DataAggregator] Failed to get JSON for {path}: {e}")
        return {}

    def get_daily_fixtures(self, date_str: Optional[str] = None, major_only: bool = True) -> List[Dict]:
        """Fetch matches for a specific date from SofaScore."""
        try:
            if not date_str:
                date_str = datetime.now().strftime("%Y-%m-%d")
            
            data = self._get_json(f"/sport/football/scheduled-events/{date_str}")
            fixtures = []
            # Major leagues IDs in SofaScore (can be expanded)
            major_leagues = {1, 17, 8, 23, 34, 35, 7, 679} # PL, LaLiga, Serie A, Bundesliga, Ligue 1, CL, etc.
            
            for event in data.get("events", []):
                league_id = event.get("tournament", {}).get("uniqueTournament", {}).get("id")
                if major_only and league_id not in major_leagues:
                    continue
                
                status_code = event.get("status", {}).get("code")
                # Status codes: 0 (Not started), 100 (Finished), 6, 7 (Live)
                status_type = event.get("status", {}).get("type")
                
                fixtures.append({
                    "fixture": {
                        "id": event["id"], 
                        "timestamp": event["startTimestamp"],
                        "status_code": status_code,
                        "status_type": status_type
                    },
                    "league": {
                        "id": league_id, 
                        "name": event.get("tournament", {}).get("name")
                    },
                    "teams": {
                        "home": {"name": event["homeTeam"]["name"], "id": event["homeTeam"]["id"]},
                        "away": {"name": event["awayTeam"]["name"], "id": event["awayTeam"]["id"]}
                    },
                    "goals": {
                        "home": event.get("homeScore", {}).get("current", 0), 
                        "away": event.get("awayScore", {}).get("current", 0)
                    },
                    "status": {
                        "long": event.get("status", {}).get("description", "Unknown")
                    }
                })
            return fixtures
        except Exception as e:
            logger.error(f"SofaScore fixtures fetch failed: {e}")
            return []

    def get_match_all_data(self, event_id: int) -> Dict[str, Any]:
        """Deep extraction from SofaScore: stats, lineups, shotmaps, graph, incidents."""
        try:
            # 1. Basic Info
            event_data = self._get_json(f"/event/{event_id}").get("event", {})

            # 2. Statistics
            stats_data = self._get_json(f"/event/{event_id}/statistics").get("statistics", [])

            # 3. Lineups
            lineups_data = self._get_json(f"/event/{event_id}/lineups")

            # 4. Momentum Graph
            graph_data = self._get_json(f"/event/{event_id}/graph").get("graphPoints", [])

            # 5. Shotmap
            shotmap_data = self._get_json(f"/event/{event_id}/shotmap").get("shotmap", [])

            # 6. Incidents (Goals, Cards, Subs)
            incidents_data = self._get_json(f"/event/{event_id}/incidents").get("incidents", [])

            # 7. Average Positions (Passing & Spatial Nodes)
            avg_positions_data = self._get_json(f"/event/{event_id}/average-positions", timeout=10)

            # Flatten player stats from lineups
            player_stats = []
            for side in ["home", "away"]:
                side_data = lineups_data.get(side, {})
                for player_entry in side_data.get("players", []):
                    p = player_entry.get("player", {})
                    stats = player_entry.get("statistics", {})
                    
                    # Fetch player heatmap points if they played (have rating or played minutes)
                    heatmap_points = []
                    p_id = p.get("id")
                    if p_id and (stats.get("rating") or stats.get("minutesPlayed")):
                        heatmap_data = self._get_json(f"/event/{event_id}/player/{p_id}/heatmap", timeout=10)
                        heatmap_points = heatmap_data.get("heatmap", []) or []
                            
                    player_stats.append({
                        "id": p.get("id"),
                        "name": p.get("name"),
                        "team": side,
                        "rating": stats.get("rating"),
                        "stats": stats,
                        "position": player_entry.get("position"),
                        "shirtNumber": player_entry.get("shirtNumber"),
                        "grid": player_entry.get("avgPositions", {}).get("grid"), # Using grid for formation
                        "heatmap": heatmap_points
                    })

            return {
                "match_id": event_id,
                "home_team": event_data.get("homeTeam", {}).get("name"),
                "away_team": event_data.get("awayTeam", {}).get("name"),
                "home_team_id": event_data.get("homeTeam", {}).get("id"),
                "away_team_id": event_data.get("awayTeam", {}).get("id"),
                "home_score": event_data.get("homeScore", {}).get("display", event_data.get("homeScore", {}).get("current", 0)),
                "away_score": event_data.get("awayScore", {}).get("display", event_data.get("awayScore", {}).get("current", 0)),
                "home_penalties": event_data.get("homeScore", {}).get("penalties"),
                "away_penalties": event_data.get("awayScore", {}).get("penalties"),
                "league": event_data.get("tournament", {}).get("name"),
                "venue": event_data.get("venue", {}).get("name"),
                "match_date": event_data.get("startTimestamp"),
                "stats_groups": stats_data,
                "player_stats": player_stats,
                "lineups_full": lineups_data,
                "events": incidents_data,
                "momentum": graph_data,
                "shotmap": shotmap_data,
                "average_positions": avg_positions_data,
                "formations": {
                    "home": lineups_data.get("home", {}).get("formation"),
                    "away": lineups_data.get("away", {}).get("formation")
                },
                "managers": {
                    "home": event_data.get("homeTeam", {}).get("manager", {}).get("name", ""),
                    "home_id": event_data.get("homeTeam", {}).get("manager", {}).get("id", None),
                    "away": event_data.get("awayTeam", {}).get("manager", {}).get("name", ""),
                    "away_id": event_data.get("awayTeam", {}).get("manager", {}).get("id", None)
                }
            }
        except Exception as e:
            logger.error(f"Deep data extraction failed: {e}")
            return {}

    def get_next_matches(self, team_id: int) -> List[Dict]:
        """Fetch upcoming matches for a team."""
        try:
            return self._get_json(f"/team/{team_id}/events/next/0").get("events", [])
        except Exception:
            return []

aggregator = DataAggregator()
