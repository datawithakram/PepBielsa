import os
import sys
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from io import BytesIO
from PIL import Image, ImageDraw, ImageOps
import numpy as np

sys.path.insert(0, r"C:\D\Bot Tele\PepBielsa")
from visuals import _get_player_photo

def test_bio_card():
    # 1. Fetch player photo
    player_id = 1023793 # Cole Palmer
    player_img = _get_player_photo(player_id)
    
    # 2. Create gradient background
    # width, height = 1080, 1080
    bg = Image.new('RGB', (1080, 1080), color='#110919')
    
    # Draw a subtle gradient from #1e1432 at top to #110919 at bottom
    draw = ImageDraw.Draw(bg)
    color1 = (30, 20, 50)  # #1e1432
    color2 = (17, 9, 25)   # #110919
    for y in range(1080):
        r = int(color1[0] + (color2[0] - color1[0]) * (y / 1080))
        g = int(color1[1] + (color2[1] - color1[1]) * (y / 1080))
        b = int(color1[2] + (color2[2] - color1[2]) * (y / 1080))
        draw.line([(0, y), (1080, y)], fill=(r, g, b))
        
    if player_img:
        # Resize player image to be larger, e.g. 550x550
        player_img = player_img.resize((550, 550), Image.Resampling.LANCZOS)
        # Paste in the upper half of the card, centered
        # x = (1080 - 550) // 2 = 265
        # y = 100 (leaving some space from the top)
        bg.paste(player_img, (265, 80), player_img)
        
    fig, ax = plt.subplots(figsize=(10, 10))
    fig.patch.set_facecolor('#110919')
    ax.axis('off')
    
    ax.imshow(bg, extent=[0, 1, 0, 1], zorder=1)
    
    # Add dark gradient/block at the bottom for readability
    ax.add_patch(mpatches.Rectangle((0, 0), 1, 0.55, facecolor='#110919', alpha=0.85, zorder=2))
    
    # Title
    ax.text(0.5, 0.52, "COLE PALMER'S FORM", color='#F9387F', fontsize=38, fontweight='black', ha='center', va='center', zorder=3)
    
    # Subtitle
    ax.text(0.5, 0.46, "LAST 10 COMPETITIVE APPEARANCES FOR CHELSEA", color='white', fontsize=16, fontweight='bold', ha='center', va='center', zorder=3)
    
    stats = {
        "APPEARANCES": "10",
        "MINUTES PLAYED": "763",
        "GOALS": "0",
        "EXPECTED GOALS (XG)": "3.42",
        "TOTAL SHOTS": "25",
        "ASSISTS": "0",
        "CHANCES CREATED": "11"
    }
    
    y_start = 0.38
    row_height = 0.038
    y_gap = 0.012
    
    # "TOTAL" Header
    ax.text(0.81, y_start + 0.035, "TOTAL", color='white', fontsize=12, fontweight='bold', ha='center', zorder=3)
    
    # Draw all rows
    n_rows = len(stats)
    total_height = n_rows * row_height + (n_rows - 1) * y_gap
    
    # 1. Draw white bars
    for i, (k, v) in enumerate(stats.items()):
        y = y_start - i * (row_height + y_gap)
        box = mpatches.FancyBboxPatch((0.15, y - row_height/2), 0.7, row_height,
                                      boxstyle="round,pad=0.01",
                                      facecolor='white', edgecolor='none', zorder=3)
        ax.add_patch(box)
        
    # 2. Draw dark vertical column
    col_bottom = y_start - (n_rows - 1) * (row_height + y_gap) - row_height/2 - 0.01
    col_height = total_height + 0.02
    ax.add_patch(mpatches.Rectangle((0.77, col_bottom), 0.08, col_height, facecolor='#201136', zorder=4))
    
    # 3. Draw texts
    for i, (k, v) in enumerate(stats.items()):
        y = y_start - i * (row_height + y_gap)
        # Key
        ax.text(0.25, y, k, color='black', fontsize=14, fontweight='black', va='center', ha='left', zorder=5)
        # Value
        ax.text(0.81, y, str(v), color='white', fontsize=16, fontweight='black', va='center', ha='center', zorder=5)
        
    plt.savefig(r'C:\D\Bot Tele\PepBielsa\outputs\test_bio_card.png', bbox_inches='tight', dpi=108, facecolor=fig.get_facecolor())
    print("Saved test_bio_card.png")

if __name__ == '__main__':
    test_bio_card()
