"""
tactical_engine.py — Advanced Tactical Preprocessing (SofaScore Edition)
Processes deep Match, Tactical, Player, and Timeline data for elite LLM analysis.
"""
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

def _get_ss_stat(stats_data: List, title: str, side: str = None) -> List[Any]:
    """Helper to extract a specific stat from SofaScore's grouped structure."""
    if not stats_data: return [0, 0]
    all_period = stats_data[0] if stats_data else {}
    for group in all_period.get("groups", []):
        for item in group.get("statisticsItems", []):
            if item.get("name").lower() == title.lower():
                if side == "home": return [item.get("home")]
                if side == "away": return [item.get("away")]
                return [item.get("home"), item.get("away")]
    return [0, 0]

def _parse_val(val: Any) -> float:
    if isinstance(val, str):
        return float(val.replace("%", "").replace(",", ""))
    return float(val or 0)

def compute_tactical_summary_from_scraping(raw: Dict) -> Dict[str, Any]:
    """
    Exhaustive tactical preprocessing of SofaScore data.
    """
    sd = raw.get("stats_groups", [])
    
    # ─── 1. MATCH DATA ───
    poss = [_parse_val(v) for v in _get_ss_stat(sd, "Ball possession")]
    shots = [_parse_val(v) for v in _get_ss_stat(sd, "Total shots")]
    shots_on = [_parse_val(v) for v in _get_ss_stat(sd, "Shots on target")]
    xg = [_parse_val(v) for v in _get_ss_stat(sd, "Expected goals")]
    if sum(xg) == 0:
        xg = [_parse_val(v) for v in _get_ss_stat(sd, "Expected goals (xG)")]
        
    passes = [_parse_val(v) for v in _get_ss_stat(sd, "Passes")]
    accurate_passes = [_parse_val(v) for v in _get_ss_stat(sd, "Accurate passes")]
    pass_acc = [0.0, 0.0]
    if passes[0] > 0: pass_acc[0] = (accurate_passes[0] / passes[0]) * 100
    if passes[1] > 0: pass_acc[1] = (accurate_passes[1] / passes[1]) * 100
    
    corners = [_parse_val(v) for v in _get_ss_stat(sd, "Corner kicks")]
    fouls = [_parse_val(v) for v in _get_ss_stat(sd, "Fouls")]
    big_chances = [_parse_val(v) for v in _get_ss_stat(sd, "Big chances")]
    offsides = [_parse_val(v) for v in _get_ss_stat(sd, "Offsides")]
    saves = [_parse_val(v) for v in _get_ss_stat(sd, "Goalkeeper saves")]
    yellow_cards = [_parse_val(v) for v in _get_ss_stat(sd, "Yellow cards")]
    red_cards = [_parse_val(v) for v in _get_ss_stat(sd, "Red cards")]
    
    attacks = [_parse_val(v) for v in _get_ss_stat(sd, "Attacks")]
    dangerous_attacks = [_parse_val(v) for v in _get_ss_stat(sd, "Dangerous attacks")]
    final_third = [_parse_val(v) for v in _get_ss_stat(sd, "Final third entries")]
    penalty_touches = [_parse_val(v) for v in _get_ss_stat(sd, "Touches in penalty area")]
    
    if sum(attacks) == 0: attacks = final_third
    if sum(dangerous_attacks) == 0: dangerous_attacks = penalty_touches
    
    # ─── 2. TACTICAL DATA ───
    home_compactness = 1.0 - (shots_on[1] / max(shots[1], 1)) if shots[1] > 0 else 0.7
    away_compactness = 1.0 - (shots_on[0] / max(shots[0], 1)) if shots[0] > 0 else 0.7
    
    ppda_h = _parse_val(_get_ss_stat(sd, "PPDA", side="home")[0])
    ppda_a = _parse_val(_get_ss_stat(sd, "PPDA", side="away")[0])
    home_pressing = 100 - ppda_h if ppda_h > 0 else 50
    away_pressing = 100 - ppda_a if ppda_a > 0 else 50

    players = raw.get("player_stats", [])
    home_players = [p for p in players if p.get("team") == "home" and p.get("rating")]
    away_players = [p for p in players if p.get("team") == "away" and p.get("rating")]
    
    def get_stat(p, stat_group, stat_name): return _parse_val(p.get("stats", {}).get(stat_group, {}).get(stat_name, 0))
    def get_def(p): return get_stat(p, "Defense", "Clearances") + get_stat(p, "Defense", "Tackles") + get_stat(p, "Defense", "Interceptions")
    def get_sht(p): return get_stat(p, "Attack", "Total shots")
    
    h_best = sorted(home_players, key=lambda x: _parse_val(x.get("rating")), reverse=True)
    a_best = sorted(away_players, key=lambda x: _parse_val(x.get("rating")), reverse=True)
    
    h_def = sorted(home_players, key=get_def, reverse=True)
    a_def = sorted(away_players, key=get_def, reverse=True)
    
    h_sht = sorted(home_players, key=get_sht, reverse=True)
    a_sht = sorted(away_players, key=get_sht, reverse=True)

    # Momentum Shifts
    momentum = raw.get("momentum", [])
    shifts = []
    for i in range(1, len(momentum)):
        if abs(momentum[i]["value"] - momentum[i-1]["value"]) > 40:
            shifts.append({"minute": momentum[i]["minute"], "value": momentum[i]["value"]})

    # AI Observation Logic
    obs = {
        "possession": f"{'Dominant' if poss[0]>60 else 'Superior' if poss[0]>55 else 'Balanced' if poss[0]>45 else 'Reactive'} possession by {raw['home_team']}.",
        "pressing": f"{'Aggressive' if home_pressing>80 else 'Moderate' if home_pressing>60 else 'Low'} press.",
        "result_fairness": f"{'Fair' if abs(xg[0]-xg[1] - (raw['home_score']-raw['away_score'])) < 0.7 else 'Undeserved'} based on xG."
    }

    summary = {
        "home_team": raw["home_team"], "away_team": raw["away_team"],
        "home_team_id": raw.get("home_team_id"), "away_team_id": raw.get("away_team_id"),
        "home_score": raw["home_score"], "away_score": raw["away_score"],
        "home_penalties": raw.get("home_penalties"), "away_penalties": raw.get("away_penalties"),
        "managers": raw.get("managers", {"home": "", "away": ""}),
        "match_info": {
            "teams": f"{raw['home_team']} vs {raw['away_team']}",
            "score": f"{raw['home_score']} - {raw['away_score']}",
            "league": raw.get("league"), "venue": raw.get("venue"), "date": raw.get("match_date")
        },
        "match_stats": {
            "possession": {"home": poss[0], "away": poss[1]},
            "xg": {"home": xg[0], "away": xg[1]},
            "shots": {"home": {"total": shots[0], "on_target": shots_on[0]}, "away": {"total": shots[1], "on_target": shots_on[1]}},
            "passing": {"home": {"accurate": accurate_passes[0], "total": passes[0], "accuracy": pass_acc[0]}, 
                        "away": {"accurate": accurate_passes[1], "total": passes[1], "accuracy": pass_acc[1]}},
            "corners": {"home": corners[0], "away": corners[1]}, "fouls": {"home": fouls[0], "away": fouls[1]},
            "big_chances": {"home": big_chances[0], "away": big_chances[1]}, "offsides": {"home": offsides[0], "away": offsides[1]},
            "saves": {"home": saves[0], "away": saves[1]}, "attacks": {"home": attacks[0], "away": attacks[1]},
            "dangerous_attacks": {"home": dangerous_attacks[0], "away": dangerous_attacks[1]},
            "yellow_cards": {"home": yellow_cards[0], "away": yellow_cards[1]}, "red_cards": {"home": red_cards[0], "away": red_cards[1]}
        },
        "tactical_intelligence": {
            "formations": raw.get("formations", {}), "lineups_full": raw.get("lineups_full", {}),
            "defensive_compactness": {"home": round(home_compactness, 2), "away": round(away_compactness, 2)},
            "pressing_intensity": {"home": round(home_pressing, 1), "away": round(away_pressing, 1)},
            "field_tilt": round(poss[0] / (poss[0] + poss[1]) * 100, 1) if (poss[0]+poss[1]) > 0 else 50
        },
        "player_analytics": {
            "best_home": h_best[0] if h_best else {}, "best_away": a_best[0] if a_best else {},
            "worst_home": h_best[-1] if h_best else {}, "worst_away": a_best[-1] if a_best else {},
            "most_def_home": h_def[0] if h_def else {}, "most_def_away": a_def[0] if a_def else {},
            "most_sht_home": h_sht[0] if h_sht else {}, "most_sht_away": a_sht[0] if a_sht else {}
        },
        "timeline_intelligence": {"momentum_shifts": shifts, "events": raw.get("events", [])},
        "player_stats": raw.get("player_stats", []),
        "raw_events": raw.get("events", []), "raw_momentum": raw.get("momentum", []), "raw_shotmap": raw.get("shotmap", []),
        "average_positions": raw.get("average_positions", {}),
        # Legacy compat
        "xg": {"home": xg[0], "away": xg[1]}, "possession": {"home": poss[0], "away": poss[1]},
        "shots": {"home": {"total": shots[0], "on_target": shots_on[0]}, "away": {"total": shots[1], "on_target": shots_on[1]}},
        "corners": {"home": corners[0], "away": corners[1]}, "fouls": {"home": fouls[0], "away": fouls[1]},
        "tactical_observations": obs
    }
    return summary