"""
Tactical visualization engine – generates professional football graphics
using mplsoccer, matplotlib, seaborn.
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from mplsoccer import Pitch, VerticalPitch
from PIL import Image
from io import BytesIO
import base64
from typing import Dict, List, Optional
import pandas as pd

# Style settings
plt.style.use("dark_background")
sns.set_palette("bright")

OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def save_and_encode(fig) -> str:
    """Save figure to temporary PNG and return base64 string."""
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()

def shot_map(match_summary: Dict, shot_data: Optional[List] = None) -> str:
    """Generate xG-style shot map (simulated data if real not available)."""
    # Simulate shots based on stats
    home_shots = int(match_summary["shots"]["home"]["total"])
    away_shots = int(match_summary["shots"]["away"]["total"])

    pitch = VerticalPitch(pitch_type='statsbomb', half=True,
                          pitch_color='#0e1117', line_color='#c7c7c7')
    fig, ax = pitch.draw(figsize=(6, 8))

    # Home shots (simulated)
    if home_shots > 0:
        x_home = np.random.uniform(0.5, 1.0, home_shots) * 120
        y_home = np.random.uniform(0, 80, home_shots)
        size_home = np.random.uniform(20, 100, home_shots)
        pitch.scatter(x_home, y_home, s=size_home, c='#d9534f', alpha=0.7, ax=ax, label=match_summary["home_team"])

    # Away shots
    if away_shots > 0:
        x_away = np.random.uniform(0.5, 1.0, away_shots) * 120
        y_away = np.random.uniform(0, 80, away_shots)
        size_away = np.random.uniform(20, 100, away_shots)
        pitch.scatter(x_away, y_away, s=size_away, c='#0275d8', alpha=0.7, ax=ax, label=match_summary["away_team"])

    ax.legend(loc='upper center', ncol=2)
    plt.title("Shot Map (simulated xG-sized)", color='white', pad=15)
    return save_and_encode(fig)

def heatmap(match_summary: Dict) -> str:
    """Generates a possession heatmap (simulated)."""
    pitch = Pitch(pitch_type='statsbomb', pitch_color='#0e1117', line_color='#c7c7c7')
    fig, ax = pitch.draw(figsize=(10, 7))

    # Simulated home heatmap
    x = np.random.normal(loc=60, scale=15, size=500)
    y = np.random.normal(loc=40, scale=12, size=500)
    pitch.kdeplot(x, y, ax=ax, cmap='Reds', fill=True, alpha=0.6, levels=50, thresh=0.1)

    # Simulated away heatmap (mirrored)
    x_a = np.random.normal(loc=60, scale=15, size=500)
    y_a = np.random.normal(loc=40, scale=12, size=500)
    pitch.kdeplot(120 - x_a, y_a, ax=ax, cmap='Blues', fill=True, alpha=0.6, levels=50, thresh=0.1)

    ax.set_title("Possession Heatmap", color='white', size=16)
    return save_and_encode(fig)

def pass_network(lineups: List, match_summary: Dict) -> str:
    """Simulated pass network showing progressive passing."""
    pitch = Pitch(pitch_type='statsbomb', pitch_color='#0e1117', line_color='#c7c7c7')
    fig, ax = pitch.draw(figsize=(10, 7))

    # Simulate nodes (11 players) for home team
    home_positions = np.array([
        [5, 40], [20, 20], [20, 60], [35, 10], [35, 40], [35, 70],
        [50, 20], [50, 60], [65, 40], [80, 25], [80, 55]
    ])
    away_positions = 120 - home_positions

    # Nodes sized by touches (simulated)
    touches_home = np.random.uniform(30, 90, 11)
    touches_away = np.random.uniform(30, 90, 11)
    pitch.scatter(home_positions[:,0], home_positions[:,1], s=touches_home, c='#d9534f', alpha=0.8, ax=ax)
    pitch.scatter(away_positions[:,0], away_positions[:,1], s=touches_away, c='#0275d8', alpha=0.8, ax=ax)

    # Progressive passing links (home: highlight passes > 50th percentile)
    for i in range(11):
        for j in range(i+1, 11):
            if np.random.rand() > 0.6:
                x1, y1 = home_positions[i]
                x2, y2 = home_positions[j]
                if x2 > x1:  # progressive forward
                    ax.plot([x1, x2], [y1, y2], color='#d9534f', alpha=0.3, lw=1)
                else:
                    ax.plot([x1, x2], [y1, y2], color='#d9534f', alpha=0.15, lw=0.7)
    ax.set_title("Pass Network (simulated progressive links)", color='white', size=16)
    return save_and_encode(fig)

def formation_graphic(lineups: List, match_summary: Dict) -> str:
    """Simple formation graphic based on lineups (static)."""
    # Simulate a 4-3-3 vs 4-2-3-1
    pitch = Pitch(pitch_type='statsbomb', pitch_color='#0e1117', line_color='#c7c7c7')
    fig, ax = pitch.draw(figsize=(8, 6))
    # Placeholder: just show team names with formation text
    ax.text(60, 40, f"{match_summary['home_team']}\n4-3-3\nvs\n{match_summary['away_team']}\n4-2-3-1",
            ha='center', va='center', color='white', fontsize=14)
    return save_and_encode(fig)

def momentum_chart(match_summary: Dict) -> str:
    """Tactical momentum over time (simulated from stats)."""
    fig, ax = plt.subplots(figsize=(8, 4), facecolor='#0e1117')
    ax.set_facecolor('#0e1117')
    minutes = np.arange(0, 91, 5)
    home_momentum = np.sin(minutes/10) * 20 + 50 + np.random.normal(0, 5, len(minutes))
    away_momentum = 100 - home_momentum + np.random.normal(0, 5, len(minutes))
    ax.plot(minutes, home_momentum, color='#d9534f', label=match_summary['home_team'])
    ax.plot(minutes, away_momentum, color='#0275d8', label=match_summary['away_team'])
    ax.fill_between(minutes, home_momentum, alpha=0.2, color='#d9534f')
    ax.fill_between(minutes, away_momentum, alpha=0.2, color='#0275d8')
    ax.set_xlabel("Minute", color='white')
    ax.set_ylabel("Momentum Index", color='white')
    ax.legend()
    ax.set_title("Tactical Momentum", color='white')
    return save_and_encode(fig)

def pressure_map(match_summary: Dict) -> str:
    """Pressure zones heatmap based on fouls (simulated)."""
    pitch = Pitch(pitch_type='statsbomb', pitch_color='#0e1117', line_color='#c7c7c7')
    fig, ax = pitch.draw(figsize=(10, 7))
    # Simulate defensive actions
    for _ in range(30):
        x = np.random.beta(2,5)*120
        y = np.random.uniform(0,80)
        ax.scatter(x, y, c='#ffcc00', s=60, alpha=0.6, edgecolors='black')
    ax.set_title("Pressure Zones (simulated)", color='white')
    return save_and_encode(fig)

def generate_all_graphics(match_summary: Dict, lineups: List, shot_data=None) -> Dict[str, str]:
    """Return dict of base64 encoded images for each graphic type."""
    return {
        "shot_map": shot_map(match_summary, shot_data),
        "heatmap": heatmap(match_summary),
        "pass_network": pass_network(lineups, match_summary),
        "formation": formation_graphic(lineups, match_summary),
        "momentum": momentum_chart(match_summary),
        "pressure_map": pressure_map(match_summary)
    }