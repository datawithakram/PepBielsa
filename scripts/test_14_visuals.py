import os
import json
from visuals import generate_all_graphics

# Dummy Match Summary
dummy_summary = {
    "home_team": "Real Madrid",
    "away_team": "Barcelona",
    "home_score": 2,
    "away_score": 1,
    "match_info": {
        "teams": "Real Madrid vs Barcelona",
        "score": "2 - 1"
    },
    "match_stats": {
        "possession": {"home": 52, "away": 48},
        "xg": {"home": 2.15, "away": 1.45},
        "shots": {"home": {"total": 15, "on_target": 6}, "away": {"total": 12, "on_target": 4}},
        "passing": {"home": {"accuracy": 88}, "away": {"accuracy": 85}},
        "corners": {"home": 6, "away": 4},
        "fouls": {"home": 12, "away": 14},
        "big_chances": {"home": 3, "away": 2},
        "saves": {"home": 3, "away": 4},
        "yellow_cards": {"home": 2, "away": 3},
        "red_cards": {"home": 0, "away": 0},
        "dangerous_attacks": {"home": 45, "away": 38}
    },
    "tactical_intelligence": {
        "formations": {"home": "4-3-3", "away": "4-3-3"},
        "defensive_compactness": {"home": 0.85, "away": 0.75},
        "pressing_intensity": {"home": 12.5, "away": 14.2},
        "buildup_efficiency": {"home": 0.25, "away": 0.22},
        "field_tilt": 55.5
    },
    "timeline": {
        "momentum": [{"minute": i, "value": 10 if i % 10 == 0 else 0} for i in range(90)]
    }
}

output_dir = r"C:\D\Bot Tele\PepBielsa\outputs"
print(f"🚀 Generating 14 graphics to {output_dir}...")

graphics = generate_all_graphics(dummy_summary, save_dir=output_dir)

print("✅ Success! The following files were created:")
for filename in sorted(os.listdir(output_dir)):
    if filename.endswith(".png"):
        print(f" - {filename}")
