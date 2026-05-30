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
        self.base_url = "https://api.sofascore.app/api/v1"
        self.session = requests.Session()
        # No need for complex manual headers, curl_cffi handles it via impersonate

    def get_daily_fixtures(self, date_str: Optional[str] = None, major_only: bool = True) -> List[Dict]:
        """Fetch matches for a specific date from SofaScore."""
        try:
            if not date_str:
                date_str = datetime.now().strftime("%Y-%m-%d")
            
            url = f"{self.base_url}/sport/football/scheduled-events/{date_str}"
            resp = self.session.get(url, impersonate="chrome124", timeout=15)
            resp.raise_for_status()
            data = resp.json()
            
            fixtures = []
            # Major leagues IDs in SofaScore (can be expanded)
            major_leagues = {1, 17, 8, 23, 34, 35, 7, 679} # PL, LaLiga, Serie A, Bunesliga, Ligue 1, CL, etc.
            
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
            event_url = f"{self.base_url}/event/{event_id}"
            event_data = self.session.get(event_url, impersonate="chrome124").json().get("event", {})

            # 2. Statistics
            stats_url = f"{self.base_url}/event/{event_id}/statistics"
            stats_data = self.session.get(stats_url, impersonate="chrome124").json().get("statistics", [])

            # 3. Lineups
            lineups_url = f"{self.base_url}/event/{event_id}/lineups"
            lineups_data = self.session.get(lineups_url, impersonate="chrome124").json()

            # 4. Momentum Graph
            graph_url = f"{self.base_url}/event/{event_id}/graph"
            graph_data = self.session.get(graph_url, impersonate="chrome124").json().get("graphPoints", [])

            # 5. Shotmap
            shotmap_url = f"{self.base_url}/event/{event_id}/shotmap"
            shotmap_data = self.session.get(shotmap_url, impersonate="chrome124").json().get("shotmap", [])

            # 6. Incidents (Goals, Cards, Subs)
            incidents_url = f"{self.base_url}/event/{event_id}/incidents"
            incidents_data = self.session.get(incidents_url, impersonate="chrome124").json().get("incidents", [])

            # 7. Average Positions (Passing & Spatial Nodes)
            avg_positions_data = {}
            try:
                avg_pos_url = f"{self.base_url}/event/{event_id}/average-positions"
                avg_pos_resp = self.session.get(avg_pos_url, impersonate="chrome124", timeout=10)
                if avg_pos_resp.status_code == 200:
                    avg_positions_data = avg_pos_resp.json()
            except Exception as e:
                logger.warning(f"Could not fetch average-positions: {e}")

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
                        try:
                            hm_url = f"{self.base_url}/event/{event_id}/player/{p_id}/heatmap"
                            hm_resp = self.session.get(hm_url, impersonate="chrome124", timeout=10)
                            if hm_resp.status_code == 200 and hm_resp.content:
                                try:
                                    heatmap_points = hm_resp.json().get("heatmap", []) or []
                                except Exception:
                                    pass
                        except Exception:
                            pass
                            
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
            url = f"{self.base_url}/team/{team_id}/events/next/0"
            resp = self.session.get(url, impersonate="chrome124", timeout=15)
            resp.raise_for_status()
            return resp.json().get("events", [])
        except Exception:
            return []

aggregator = DataAggregator()
