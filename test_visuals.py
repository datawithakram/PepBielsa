import os
import sys
# Make sure we can import from the current directory
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from visuals import generate_all_graphics

# Dummy summary data
dummy_summary = {
    "home_team": "Manchester City",
    "away_team": "Arsenal",
    "home_score": 2,
    "away_score": 1,
    "home_team_id": 17,
    "away_team_id": 42,
    "match_stats": {
        "possession": {"home": 60, "away": 40},
        "xg": {"home": 2.4, "away": 0.8},
        "shots": {"home": {"total": 18}, "away": {"total": 7}},
        "corners": {"home": 8, "away": 3}
    },
    "tactical_intelligence": {
        "lineups_full": {
            "home": {
                "players": [
                    {"player": {"id": 123, "shortName": "Ederson"}, "avgPositions": {"grid": "5:1"}, "rating": 7.5},
                    {"player": {"id": 124, "shortName": "Dias"}, "avgPositions": {"grid": "5:3"}, "rating": 7.2},
                    {"player": {"id": 125, "shortName": "De Bruyne"}, "avgPositions": {"grid": "5:7"}, "rating": 8.5},
                    {"player": {"id": 126, "shortName": "Haaland"}, "avgPositions": {"grid": "5:9"}, "rating": 9.0}
                ]
            },
            "away": {
                "players": [
                    {"player": {"id": 223, "shortName": "Raya"}, "avgPositions": {"grid": "5:1"}, "rating": 6.5},
                    {"player": {"id": 224, "shortName": "Saliba"}, "avgPositions": {"grid": "5:3"}, "rating": 7.0},
                    {"player": {"id": 225, "shortName": "Odegaard"}, "avgPositions": {"grid": "5:7"}, "rating": 7.8},
                    {"player": {"id": 226, "shortName": "Saka"}, "avgPositions": {"grid": "5:9"}, "rating": 8.0}
                ]
            }
        }
    },
    "raw_momentum": [
        {"minute": m, "value": (m % 20) - 10 if m < 45 else (m % 15) - 5} for m in range(0, 95)
    ],
    "raw_events": [
        {"time": 15, "type": "goal", "isHome": True},
        {"time": 40, "type": "goal", "isHome": False},
        {"time": 75, "type": "goal", "isHome": True},
        {"time": 80, "type": "card", "cardType": "red", "isHome": False}
    ],
    "player_analytics": {
        "best_players": [
            {"player": {"id": 126, "name": "E. Haaland"}, "rating": 9.0},
            {"player": {"id": 225, "name": "M. Odegaard"}, "rating": 7.8}
        ],
        "worst_players": [
            {"player": {"id": 124, "name": "R. Dias"}, "rating": 6.2},
            {"player": {"id": 223, "name": "D. Raya"}, "rating": 5.0}
        ]
    }
}

os.makedirs("outputs", exist_ok=True)
print("Generating graphics...")
generate_all_graphics(dummy_summary, save_dir="outputs")
print("Done! Check the outputs directory.")
