"""
Local tactical analytics engine – computes metrics from match stats/events
to create a compact intelligence summary before LLM processing.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List

def _safe_stat(stats_list, team_id, stat_name):
    """Extract a statistic value for a specific team."""
    for team_stats in stats_list:
        if team_stats["team"]["id"] == team_id:
            for s in team_stats.get("statistics", []):
                if s["type"] == stat_name:
                    try:
                        return float(s["value"]) if s["value"] else 0.0
                    except:
                        return s["value"]
    return 0

def compute_tactical_summary(match: Dict, stats: List, events: List, lineups: List) -> Dict[str, Any]:
    """
    Process match data and return a compact tactical intelligence dictionary.
    Works with limited API-Football free-tier statistics.
    """
    home_id = match["teams"]["home"]["id"]
    away_id = match["teams"]["away"]["id"]

    # ---------- Basic Possession & Shot Metrics ----------
    home_poss = _safe_stat(stats, home_id, "Ball Possession")
    away_poss = _safe_stat(stats, away_id, "Ball Possession")

    home_shots_on = _safe_stat(stats, home_id, "Shots on Goal")
    home_shots_off = _safe_stat(stats, home_id, "Shots off Goal")
    away_shots_on = _safe_stat(stats, away_id, "Shots on Goal")
    away_shots_off = _safe_stat(stats, away_id, "Shots off Goal")
    home_total_shots = home_shots_on + home_shots_off
    away_total_shots = away_shots_on + away_shots_off

    home_corners = _safe_stat(stats, home_id, "Corner Kicks")
    away_corners = _safe_stat(stats, away_id, "Corner Kicks")
    home_fouls = _safe_stat(stats, home_id, "Fouls")
    away_fouls = _safe_stat(stats, away_id, "Fouls")
    home_yellow = _safe_stat(stats, home_id, "Yellow Cards")
    away_yellow = _safe_stat(stats, away_id, "Yellow Cards")
    home_offsides = _safe_stat(stats, home_id, "Offsides")
    away_offsides = _safe_stat(stats, away_id, "Offsides")

    # ---------- Tactical Derived Metrics ----------
    # Pressing intensity proxy: fouls + offsides in attacking third (crude)
    # We'll use total fouls as pressing intensity indicator
    # Defensive compactness: low shots on target allowed
    home_def_compact = 1.0 - (away_shots_on / max(away_total_shots, 1)) if away_total_shots else 0.5
    away_def_compact = 1.0 - (home_shots_on / max(home_total_shots, 1)) if home_total_shots else 0.5

    # Momentum swing: corners + shots on target differential
    home_momentum = home_total_shots + home_corners
    away_momentum = away_total_shots + away_corners
    momentum_diff = home_momentum - away_momentum

    # Half-space occupation cannot be determined without events, so set as unknown
    # Build-up structure: high possession with low shots may indicate sterile possession
    home_buildup_efficiency = home_total_shots / max(home_poss, 1) if home_poss else 0
    away_buildup_efficiency = away_total_shots / max(away_poss, 1) if away_poss else 0

    # Progressive passing proxy: corners + shots (corners come from attacking moves)
    # Width usage: offsides can indicate wide runs behind defence
    home_width_usage = home_offsides / max(home_poss, 1) if home_poss else 0
    away_width_usage = away_offsides / max(away_poss, 1) if away_poss else 0

    # xG dominance (not available, so we simulate a basic shot quality metric)
    home_shot_quality = (home_shots_on / max(home_total_shots, 1)) if home_total_shots else 0
    away_shot_quality = (away_shots_on / max(away_total_shots, 1)) if away_total_shots else 0

    summary = {
        "home_team": match["teams"]["home"]["name"],
        "away_team": match["teams"]["away"]["name"],
        "home_score": match["goals"]["home"],
        "away_score": match["goals"]["away"],
        "possession": {"home": home_poss, "away": away_poss},
        "shots": {
            "home": {"total": home_total_shots, "on_target": home_shots_on},
            "away": {"total": away_total_shots, "on_target": away_shots_on}
        },
        "corners": {"home": home_corners, "away": away_corners},
        "fouls": {"home": home_fouls, "away": away_fouls},
        "yellow_cards": {"home": home_yellow, "away": away_yellow},
        "offsides": {"home": home_offsides, "away": away_offsides},
        "tactical_metrics": {
            "defensive_compactness": {"home": round(home_def_compact, 2), "away": round(away_def_compact, 2)},
            "momentum_index": round(momentum_diff, 2),
            "buildup_efficiency": {"home": round(home_buildup_efficiency, 2), "away": round(away_buildup_efficiency, 2)},
            "width_usage": {"home": round(home_width_usage, 2), "away": round(away_width_usage, 2)},
            "shot_quality": {"home": round(home_shot_quality, 2), "away": round(away_shot_quality, 2)},
        }
    }
    return summary