import os
import json
from visuals import generate_all_graphics

# Realistic Dummy Match Summary (SofaScore Style)
dummy_summary = {
    "home_team": "Real Madrid",
    "away_team": "Barcelona",
    "home_team_id": 2829, # Real Madrid
    "away_team_id": 2817, # Barcelona
    "home_score": 3,
    "away_score": 2,
    "match_info": {
        "teams": "Real Madrid vs Barcelona",
        "score": "3 - 2",
        "league": "LaLiga",
        "date": 1713726000
    },
    "match_stats": {
        "possession": {"home": 54, "away": 46},
        "xg": {"home": 2.45, "away": 1.82},
        "shots": {"home": {"total": 18, "on_target": 8}, "away": {"total": 14, "on_target": 6}},
        "passing": {"home": {"accurate": 450, "total": 510, "accuracy": 88}, "away": {"accurate": 380, "total": 450, "accuracy": 84}},
        "corners": {"home": 7, "away": 5},
        "fouls": {"home": 11, "away": 13},
        "big_chances": {"home": 4, "away": 3},
        "saves": {"home": 4, "away": 5},
        "yellow_cards": {"home": 2, "away": 3},
        "red_cards": {"home": 0, "away": 0},
        "dangerous_attacks": {"home": 55, "away": 48}
    },
    "tactical_intelligence": {
        "formations": {"home": "4-3-3", "away": "4-3-3"},
        "lineups_full": {
            "home": {
                "players": [
                    {"player": {"id": 826131, "name": "Vinícius Júnior", "shortName": "Vinícius Jr."}, "rating": 8.5, "avgPositions": {"grid": "9:5"}},
                    {"player": {"id": 1058252, "name": "Jude Bellingham", "shortName": "Bellingham"}, "rating": 8.2, "avgPositions": {"grid": "7:5"}},
                    {"player": {"id": 35492, "name": "Toni Kroos", "shortName": "Kroos"}, "rating": 7.9, "avgPositions": {"grid": "6:3"}}
                ]
            },
            "away": {
                "players": [
                    {"player": {"id": 1157814, "name": "Robert Lewandowski", "shortName": "Lewandowski"}, "rating": 7.8, "avgPositions": {"grid": "9:5"}},
                    {"player": {"id": 1234567, "name": "Lamine Yamal", "shortName": "Yamal"}, "rating": 8.4, "avgPositions": {"grid": "8:8"}}
                ]
            }
        }
    },
    "player_analytics": {
        "best_players": [
            {"player": {"id": 826131, "name": "Vinícius Jr."}, "rating": 8.5},
            {"player": {"id": 1234567, "name": "Lamine Yamal"}, "rating": 8.4}
        ],
        "worst_players": [
            {"player": {"id": 35492, "name": "Toni Kroos"}, "rating": 7.9},
            {"player": {"id": 1157814, "name": "Robert Lewandowski"}, "rating": 7.8}
        ]
    },
    "raw_momentum": [{"minute": i, "value": 30 if i < 30 else -20 if i < 60 else 40} for i in range(91)],
    "raw_events": [
        {"time": 18, "type": "goal", "isHome": True},
        {"time": 32, "type": "goal", "isHome": False},
        {"time": 75, "type": "card", "cardType": "red", "isHome": False}
    ]
}

output_dir = r"C:\D\Bot Tele\PepBielsa\outputs"
print(f"Generating Ultra-Premium graphics to {output_dir}...")

graphics = generate_all_graphics(dummy_summary, save_dir=output_dir)

print("Success! Check the outputs folder for the new designs.")
