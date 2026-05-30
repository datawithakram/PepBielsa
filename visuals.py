import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as path_effects
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from PIL import Image, ImageDraw, ImageOps
from mplsoccer import Pitch, VerticalPitch
from io import BytesIO
import base64
import logging
from typing import Dict, List, Optional, Tuple, Any
from curl_cffi import requests

logger = logging.getLogger(__name__)

# ─── PepBielsa Visual Identity ─────────────────────────────────────────────
BG          = "#111827"
MAIN_GREEN  = "#00A86B"
GOLD        = "#F4B400"
RED         = "#FF5A5F"
TEXT_MAIN   = "#F9FAFB"
TEXT_SEC    = "#9CA3AF"
PITCH_LINE  = "#1F2937"
GRID_LINE   = "#1F2937"

HOME_CLR    = MAIN_GREEN
AWAY_CLR    = GOLD

plt.rcParams.update({
    "figure.facecolor":  BG,
    "axes.facecolor":    BG,
    "axes.edgecolor":    GRID_LINE,
    "axes.labelcolor":   TEXT_SEC,
    "text.color":        TEXT_MAIN,
    "xtick.color":       TEXT_SEC,
    "ytick.color":       TEXT_SEC,
    "grid.color":        GRID_LINE,
    "grid.linewidth":    0.6,
    "font.family":       "sans-serif",
    "font.sans-serif":   ["Space Grotesk", "Inter", "Arial", "sans-serif"],
})

# ─── Utils ────────────────────────────────────────────────────────────────
def _fmt(val):
    """Format numbers with max 1 decimal place"""
    if val is None:
        return "0"
    if isinstance(val, (int, float)):
        if isinstance(val, float) and val.is_integer():
            return str(int(val))
        if isinstance(val, float):
            return f"{val:.1f}"
        return str(val)
    return str(val)

def _draw_hex_texture(ax, alpha=0.04):
    from matplotlib.patches import RegularPolygon
    for r in range(-2, 15):
        for c in range(-1, 12):
            x = c * 0.12 + (0.06 if r % 2 else 0)
            y = r * 0.10
            ax.add_patch(RegularPolygon((x, y), numVertices=6, radius=0.045, orientation=0, edgecolor=MAIN_GREEN, facecolor='none', linewidth=0.4, alpha=alpha, transform=ax.transAxes, clip_on=True))

def _add_opta_header(fig, main_title, subtitle):
    fig.text(0.05, 0.94, main_title, fontsize=24, fontweight='900', color=TEXT_MAIN, ha='left')
    fig.text(0.05, 0.91, subtitle, fontsize=11, color=TEXT_SEC, ha='left')
    fig.text(0.95, 0.94, "PepBielsa", fontsize=16, fontweight='900', color=MAIN_GREEN, ha='right')
    fig.text(0.95, 0.91, "Analyst", fontsize=11, color=TEXT_SEC, ha='right')

def _add_team_legend(fig, summary, h_color, a_color, y_pos=0.05):
    fig.text(0.3, y_pos, f"■ {summary.get('home_team', 'Home')}", color=h_color, fontsize=12, fontweight='bold', ha='right')
    fig.text(0.7, y_pos, f"■ {summary.get('away_team', 'Away')}", color=a_color, fontsize=12, fontweight='bold', ha='left')

SESSION = requests.Session()

def _get_image(url: str) -> Optional[Image.Image]:
    try:
        resp = SESSION.get(url, impersonate="chrome124", timeout=10)
        if resp.status_code == 200: 
            return Image.open(BytesIO(resp.content)).convert("RGBA")
    except Exception: pass
    return None

def _get_team_logo(team_id: int) -> Optional[Image.Image]:
    if not team_id: return None
    return _get_image(f"https://api.sofascore.app/api/v1/team/{team_id}/image")

def _get_player_photo(player_id: int) -> Optional[Image.Image]:
    if not player_id: return None
    return _get_image(f"https://api.sofascore.app/api/v1/player/{player_id}/image")

def _get_manager_photo(manager_id: int) -> Optional[Image.Image]:
    if not manager_id: return None
    return _get_image(f"https://api.sofascore.app/api/v1/manager/{manager_id}/image")

# ─── Twemoji PNG Caches for OS Font Emoji Rendering Safety ──────────────────
EMOJI_BALL = None
EMOJI_STAR = None
EMOJI_SUB = None

def _get_emoji_ball():
    global EMOJI_BALL
    if EMOJI_BALL is None:
        EMOJI_BALL = _get_image("https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/26bd.png")
    return EMOJI_BALL

def _get_emoji_star():
    global EMOJI_STAR
    if EMOJI_STAR is None:
        EMOJI_STAR = _get_image("https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/2b50.png")
    return EMOJI_STAR

def _get_emoji_sub():
    global EMOJI_SUB
    if EMOJI_SUB is None:
        EMOJI_SUB = _get_image("https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f504.png")
    return EMOJI_SUB

def _circular_image(img: Image.Image, size=(100, 100), border_color=None, border_width=4) -> Image.Image:
    img = img.convert("RGBA").resize(size, Image.Resampling.LANCZOS)
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0) + size, fill=255)
    output = ImageOps.fit(img, mask.size, centering=(0.5, 0.5))
    output.putalpha(mask)
    if border_color:
        final = Image.new("RGBA", (size[0]+border_width*2, size[1]+border_width*2), (0,0,0,0))
        draw_f = ImageDraw.Draw(final)
        draw_f.ellipse((0, 0, size[0]+border_width*2, size[1]+border_width*2), fill=border_color)
        final.paste(output, (border_width, border_width), output)
        return final
    return output

def _get_dominant_color(image: Optional[Image.Image], default_color: str) -> str:
    if not image: return default_color
    try:
        img = image.convert("RGB").resize((50, 50))
        colors = img.getcolors(2500)
        valid_colors = []
        for count, color in colors:
            # Ignore mostly white or mostly black backgrounds
            if all(c > 230 for c in color) or all(c < 25 for c in color): continue
            valid_colors.append((count, color))
        if valid_colors:
            valid_colors.sort(key=lambda x: x[0], reverse=True)
            return '#%02x%02x%02x' % valid_colors[0][1]
    except Exception:
        pass
    return default_color

def _encode(fig, save_path: str = None) -> str:
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=160, bbox_inches="tight", facecolor=BG, edgecolor="none")
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        fig.savefig(save_path, format="png", dpi=160, bbox_inches="tight", facecolor=BG, edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()

# ─── Specific Graphics ──────────────────────────────────────────────────────

# Image 1: Overview
# Image 1: Overview
def overview_map(summary: Dict, save_path=None) -> str:
    pitch = Pitch(pitch_type='opta', pitch_color=BG, line_color=PITCH_LINE, linewidth=1.5)
    fig, ax = pitch.draw(figsize=(12, 8))
    fig.patch.set_facecolor(BG)
    h_color = summary.get('home_color', HOME_CLR)
    a_color = summary.get('away_color', AWAY_CLR)
    
    hp = summary.get('home_penalties')
    ap = summary.get('away_penalties')
    score_str = f"{summary.get('home_team', '')} {_fmt(summary.get('home_score', 0))} - {_fmt(summary.get('away_score', 0))} {summary.get('away_team', '')}"
    if hp is not None and ap is not None:
        subtitle = f"{summary.get('league', 'Match Overview')} | Penalties: {hp} - {ap}"
    else:
        subtitle = summary.get('league', 'Match Overview')
        
    _add_opta_header(fig, score_str, subtitle)
    
    hl = _get_team_logo(summary.get("home_team_id"))
    al = _get_team_logo(summary.get("away_team_id"))
    if hl: ax.add_artist(AnnotationBbox(OffsetImage(hl.resize((60,60))), (35, 80), frameon=False))
    if al: ax.add_artist(AnnotationBbox(OffsetImage(al.resize((60,60))), (65, 80), frameon=False))
    
    ax.text(35, 70, summary.get('home_team', ''), ha='center', fontsize=12, fontweight='bold', color=TEXT_MAIN)
    ax.text(65, 70, summary.get('away_team', ''), ha='center', fontsize=12, fontweight='bold', color=TEXT_MAIN)
    
    if hp is not None and ap is not None:
        ax.text(50, 78, f"Penalties\n{hp} - {ap}", ha='center', va='center', fontsize=11, fontweight='bold', color=TEXT_SEC)
    
    stats = [
        ("GOALS", summary.get('home_score', 0), summary.get('away_score', 0)),
        ("xG", summary.get('match_stats', {}).get('xg', {}).get('home', 0), summary.get('match_stats', {}).get('xg', {}).get('away', 0)),
        ("SHOTS", summary.get('match_stats', {}).get('shots', {}).get('home', {}).get('total', 0), summary.get('match_stats', {}).get('shots', {}).get('away', {}).get('total', 0)),
        ("ON TARGET",
            summary.get('match_stats', {}).get('shots', {}).get('home', {}).get('on_target',
            summary.get('match_stats', {}).get('shots', {}).get('home', {}).get('ongoal', 0)),
            summary.get('match_stats', {}).get('shots', {}).get('away', {}).get('on_target',
            summary.get('match_stats', {}).get('shots', {}).get('away', {}).get('ongoal', 0))),
        ("POSSESSION", summary.get('match_stats', {}).get('possession', {}).get('home', 0), summary.get('match_stats', {}).get('possession', {}).get('away', 0))
    ]
    
    y_start = 55
    y_step = -10
    for i, (label, h, a) in enumerate(stats):
        y = y_start + (i * y_step)
        ax.add_patch(mpatches.Rectangle((37, y-3.5), 12, 7, color=h_color, alpha=0.7))
        ax.add_patch(mpatches.Rectangle((51, y-3.5), 12, 7, color=a_color, alpha=0.7))
        
        val_h = f"{_fmt(h)}%" if label == "POSSESSION" else _fmt(h)
        val_a = f"{_fmt(a)}%" if label == "POSSESSION" else _fmt(a)
        
        ax.text(43, y, val_h, ha='center', va='center', fontsize=12, fontweight='bold', color=TEXT_MAIN)
        ax.text(50, y, label, ha='center', va='center', fontsize=10, fontweight='bold', color=TEXT_MAIN)
        ax.text(57, y, val_a, ha='center', va='center', fontsize=12, fontweight='bold', color=TEXT_MAIN)

    shots = summary.get('raw_shotmap', [])
    for shot in shots:
        is_goal = shot.get("shotType") == "goal"
        if not is_goal:
            continue
            
        is_home = shot.get("isHome", True)
        color = h_color if is_home else a_color
        x = shot.get("playerCoordinates", {}).get("x", 0)
        y = shot.get("playerCoordinates", {}).get("y", 0)
        
        xg = shot.get("xg", 0.1)
        s = 50 + (xg * 500)
        
        if is_home:
            rx = x
            ry = 100.0 - y
        else:
            rx = 100.0 - x
            ry = y
            
        pitch.scatter(rx, ry, ax=ax, color=color, s=s, edgecolors=BG, zorder=5)

    return _encode(fig, save_path)

# Image 2: Efficiency (Double shot map)
def efficiency_chart(summary: Dict, save_path=None) -> str:
    pitch = Pitch(pitch_type='opta', pitch_color=BG, line_color=PITCH_LINE, linewidth=1.5)
    fig, ax = pitch.draw(figsize=(10, 7))
    fig.patch.set_facecolor(BG)
    h_color = summary.get('home_color', HOME_CLR)
    a_color = summary.get('away_color', AWAY_CLR)
    
    _add_opta_header(fig, "Shot Map Dashboard", f"{summary.get('home_team', '')} vs {summary.get('away_team', '')}")
    
    hl = _get_team_logo(summary.get("home_team_id"))
    al = _get_team_logo(summary.get("away_team_id"))
    if hl: ax.add_artist(AnnotationBbox(OffsetImage(hl.resize((60,60))), (15, 85), frameon=False, zorder=10))
    if al: ax.add_artist(AnnotationBbox(OffsetImage(al.resize((60,60))), (85, 85), frameon=False, zorder=10))

    shots = summary.get('raw_shotmap', [])
    for shot in shots:
        is_home = shot.get("isHome", True)
        color = h_color if is_home else a_color
        x = shot.get("playerCoordinates", {}).get("x", 0)
        y = shot.get("playerCoordinates", {}).get("y", 0)
        
        if is_home:
            rx = x
            ry = 100.0 - y
        else:
            rx = 100.0 - x
            ry = y
            
        is_goal = shot.get("shotType") == "goal"
        xg = shot.get("xg", 0.1)
        s = 50 + (xg * 500)
        
        if is_goal:
            pitch.scatter(rx, ry, ax=ax, color=color, s=s, edgecolors=BG, zorder=5)
        else:
            pitch.scatter(rx, ry, ax=ax, color='none', s=s, edgecolors=color, linewidth=1.5, zorder=4)
            
    ax.scatter([], [], color=h_color, s=100, label=summary.get('home_team', 'Home'))
    ax.scatter([], [], color=a_color, s=100, label=summary.get('away_team', 'Away'))
    ax.scatter([], [], color='none', edgecolors=TEXT_SEC, linewidth=1.5, s=100, label='Shot (Miss/Save)')
    ax.scatter([], [], color=TEXT_SEC, edgecolors=BG, s=100, label='Goal')
    ax.scatter([], [], color=TEXT_SEC, s=50, label='Low xG')
    ax.scatter([], [], color=TEXT_SEC, s=300, label='High xG')
    
    ax.legend(loc='lower center', ncol=3, frameon=False, labelcolor=TEXT_MAIN, bbox_to_anchor=(0.5, -0.15), fontsize=10, columnspacing=2)
    return _encode(fig, save_path)

# Image 3: xG Flow Chart
def xg_flow_chart(summary: Dict, save_path=None) -> str:
    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    
    h_score = summary.get('home_score', 0)
    a_score = summary.get('away_score', 0)
    hp = summary.get('home_penalties')
    ap = summary.get('away_penalties')
    
    if h_score > a_score:
        winner = 'home'
    elif a_score > h_score:
        winner = 'away'
    elif hp is not None and ap is not None and hp > ap:
        winner = 'home'
    elif hp is not None and ap is not None and ap > hp:
        winner = 'away'
    else:
        winner = 'home'
        
    w_team = summary.get(f'{winner}_team', 'Winner')
    w_color = summary.get(f'{winner}_color', HOME_CLR if winner == 'home' else AWAY_CLR)
    
    loser = 'away' if winner == 'home' else 'home'
    l_team = summary.get(f'{loser}_team', 'Opponent')
    l_color = summary.get(f'{loser}_color', AWAY_CLR if loser == 'away' else HOME_CLR)
    
    # Compact two-line header to avoid text overlap with chart area
    fig.text(0.05, 0.96, f"{w_team}  |  Match Flow", fontsize=19, fontweight='900', color=TEXT_MAIN, ha='left', va='top')
    fig.text(0.05, 0.91, "Rolling 15-min xG — Attacking Threat Over Time", fontsize=10, color=TEXT_SEC, ha='left', va='top')
    fig.text(0.95, 0.96, "PepBielsa", fontsize=14, fontweight='900', color=MAIN_GREEN, ha='right', va='top')
    fig.text(0.95, 0.91, "Analyst", fontsize=10, color=TEXT_SEC, ha='right', va='top')

    # Tighten top margin so chart doesn't overlap title
    plt.subplots_adjust(top=0.84, bottom=0.12, left=0.09, right=0.97)
    
    shots = summary.get('raw_shotmap', [])
    shots.sort(key=lambda x: x.get('time', 0))
    
    minutes = np.arange(1, 100)
    xg_for = np.zeros(99)
    xg_ag = np.zeros(99)
    
    for s in shots:
        t = s.get('time', 1)
        if t >= 99: t = 98
        if t < 1: t = 1
        xg = s.get('xg', 0.0)
        is_home = s.get('isHome', True)
        
        if (winner == 'home' and is_home) or (winner == 'away' and not is_home):
            xg_for[t] += xg
        else:
            xg_ag[t] += xg
            
    window = 15
    roll_for = np.zeros(99)
    roll_ag = np.zeros(99)
    
    for i in range(1, 99):
        start = max(1, i - window + 1)
        roll_for[i] = np.sum(xg_for[start:i+1])
        roll_ag[i] = np.sum(xg_ag[start:i+1])
        
    try:
        from scipy.ndimage import gaussian_filter1d
        smooth_for = gaussian_filter1d(roll_for, sigma=1.5)
        smooth_ag = gaussian_filter1d(roll_ag, sigma=1.5)
    except ImportError:
        smooth_for = roll_for
        smooth_ag = roll_ag
    
    ax.plot(minutes, smooth_for, color=w_color, lw=3, label=f"xG For ({w_team})")
    ax.plot(minutes, smooth_ag, color=l_color, lw=3, label=f"xG Against ({l_team})")
    
    ax.fill_between(minutes, smooth_for, alpha=0.2, color=w_color)
    ax.fill_between(minutes, smooth_ag, alpha=0.2, color=l_color)
    
    ax.set_xlim(0, 95)
    max_y = max(np.max(smooth_for), np.max(smooth_ag))
    if max_y == 0: max_y = 1
    ax.set_ylim(0, max_y * 1.1)
    
    ax.grid(axis='y', color=GRID_LINE, linestyle='-', alpha=0.5)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color(GRID_LINE)
    ax.spines['bottom'].set_color(GRID_LINE)
    ax.tick_params(colors=TEXT_SEC)
    
    ax.set_xlabel("Minute", color=TEXT_SEC, fontweight='bold')
    ax.set_ylabel("Rolling xG (15 min)", color=TEXT_SEC, fontweight='bold')
    
    ax.legend(loc='upper right', frameon=False, labelcolor=TEXT_MAIN)
    
    return _encode(fig, save_path)

# Image 4: Formation
def formation_graphic(summary: Dict, save_path=None) -> str:
    pitch = Pitch(pitch_type="opta", pitch_color=BG, line_color=PITCH_LINE, linewidth=1.2)
    fig, ax = pitch.draw(figsize=(14, 10))
    fig.patch.set_facecolor(BG)
    h_color = summary.get('home_color', HOME_CLR)
    a_color = summary.get('away_color', AWAY_CLR)
    
    _add_opta_header(fig, "Tactical Dispositions", f"{summary.get('home_team', '')} vs {summary.get('away_team', '')}")

    ti = summary.get("tactical_intelligence", {})
    form_h = ti.get("formations", {}).get("home", "")
    form_a = ti.get("formations", {}).get("away", "")
    mgr_h = summary.get("managers", {}).get("home", "Unknown")
    mgr_a = summary.get("managers", {}).get("away", "Unknown")
    
    mgr_h_id = summary.get("managers", {}).get("home_id")
    mgr_a_id = summary.get("managers", {}).get("away_id")
    
    photo_h = _get_manager_photo(mgr_h_id)
    photo_a = _get_manager_photo(mgr_a_id)
    
    fig.text(0.38, 0.05, f"Manager: {mgr_h}\nFormation: {form_h}", ha='center', va='bottom', fontsize=12, color=TEXT_MAIN)
    fig.text(0.62, 0.05, f"Manager: {mgr_a}\nFormation: {form_a}", ha='center', va='bottom', fontsize=12, color=TEXT_MAIN)

    logo_h = _get_team_logo(summary.get("home_team_id"))
    logo_a = _get_team_logo(summary.get("away_team_id"))
    
    if logo_h:
        ax_l_h = fig.add_axes([0.15, 0.03, 0.07, 0.07])
        ax_l_h.imshow(logo_h.resize((60, 60)))
        ax_l_h.axis('off')
    if photo_h:
        ax_pm_h = fig.add_axes([0.23, 0.03, 0.07, 0.07])
        ax_pm_h.imshow(_circular_image(photo_h))
        ax_pm_h.axis('off')
        
    if photo_a:
        ax_pm_a = fig.add_axes([0.70, 0.03, 0.07, 0.07])
        ax_pm_a.imshow(_circular_image(photo_a))
        ax_pm_a.axis('off')
    if logo_a:
        ax_l_a = fig.add_axes([0.78, 0.03, 0.07, 0.07])
        ax_l_a.imshow(logo_a.resize((60, 60)))
        ax_l_a.axis('off')

    lineups = ti.get("lineups_full", {})

    def _draw_jersey(ax, cx, cy, color, number, name, is_gk=False):
        """Draw a football jersey shape with number and player name."""
        import matplotlib.patches as mp
        # Use yellow for GK, team color otherwise
        shirt_color = "#f4c430" if is_gk else color
        # Determine text color: white if dark shirt, dark if light shirt
        try:
            r, g, b = int(shirt_color[1:3], 16), int(shirt_color[3:5], 16), int(shirt_color[5:7], 16)
            luminance = 0.299*r + 0.587*g + 0.114*b
            txt_color = "#111827" if luminance > 140 else "#ffffff"
        except Exception:
            txt_color = "#ffffff"

        W, H = 6.5, 7.5   # jersey body width / height in opta units
        sw, sh = 2.8, 2.0  # shoulder tab width / height

        # Jersey body (main rectangle with rounded corners via FancyBboxPatch)
        body = mp.FancyBboxPatch(
            (cx - W/2, cy - H/2), W, H,
            boxstyle="round,pad=0.3",
            facecolor=shirt_color, edgecolor="white", linewidth=0.8, zorder=5
        )
        ax.add_patch(body)

        # Left shoulder tab
        ls = mp.FancyBboxPatch(
            (cx - W/2 - sw + 0.5, cy + H/2 - sh + 0.3), sw, sh,
            boxstyle="round,pad=0.2",
            facecolor=shirt_color, edgecolor="white", linewidth=0.8, zorder=4
        )
        ax.add_patch(ls)

        # Right shoulder tab
        rs = mp.FancyBboxPatch(
            (cx + W/2 - 0.5, cy + H/2 - sh + 0.3), sw, sh,
            boxstyle="round,pad=0.2",
            facecolor=shirt_color, edgecolor="white", linewidth=0.8, zorder=4
        )
        ax.add_patch(rs)

        # Collar (small neck cutout)
        collar = mp.Ellipse((cx, cy + H/2 - 0.2), 2.2, 1.2,
                            facecolor=BG, edgecolor="white", linewidth=0.5, zorder=6)
        ax.add_patch(collar)

        # Number text
        ax.text(cx, cy + 0.5, str(number), ha='center', va='center',
                fontsize=11, fontweight='black', color=txt_color, zorder=7)

        # Player name below jersey
        ax.text(cx, cy - H/2 - 1.5, name, ha='center', va='top',
                fontsize=7.5, fontweight='bold', color=TEXT_MAIN, zorder=7,
                bbox=dict(facecolor=BG, alpha=0.72, edgecolor='none', pad=0.8))

    def _draw_team(side_data, is_home, color, formation_str):
        players = side_data.get("players", [])[:11]
        
        if not formation_str: formation_str = "4-4-2"
        try:
            lines = [1] + [int(x) for x in str(formation_str).split('-')]
        except:
            lines = [1, 4, 4, 2]
        if sum(lines) != 11: lines = [1, 4, 4, 2]
        
        row_positions = np.linspace(1, 9, len(lines))
        coords = []
        for r_val, count in zip(row_positions, lines):
            if count == 1: cols = [5]
            elif count == 2: cols = [6.5, 3.5] if is_home else [3.5, 6.5]
            elif count == 3: cols = [7.5, 5, 2.5] if is_home else [2.5, 5, 7.5]
            elif count == 4: cols = [8, 6, 4, 2] if is_home else [2, 4, 6, 8]
            elif count == 5: cols = [8.5, 6.75, 5, 3.25, 1.5] if is_home else [1.5, 3.25, 5, 6.75, 8.5]
            else: cols = np.linspace(8.5, 1.5, count) if is_home else np.linspace(1.5, 8.5, count)
            for c_val in cols:
                coords.append((r_val, c_val))
                
        # Identify GK (first player in home lineup = row_index 0)
        gk_index = 0

        for i, p in enumerate(players):
            p_obj = p.get("player", {}) if "player" in p else p
            
            grid = p.get("avgPositions", {}).get("grid") or p.get("grid")
            if grid:
                try:
                    row, col = map(float, grid.split(":"))
                except:
                    row, col = coords[i] if i < len(coords) else (5, 5)
            else:
                row, col = coords[i] if i < len(coords) else (5, 5)
                
            try:
                px = 8 + (row * 4.0) if is_home else 92 - (row * 4.0)
                py = (col - 1) * 11 + 6
                px = max(6, min(px, 94))
                py = max(6, min(py, 94))
                
                number = p.get("shirtNumber", "")
                name_full = p_obj.get("shortName", p_obj.get("name", ""))
                # Shorten name: keep first letter of first name + last name
                parts = name_full.split()
                short_name = (parts[0][0] + ". " + " ".join(parts[1:])) if len(parts) > 1 else name_full
                
                is_gk = (i == gk_index)
                _draw_jersey(ax, px, py, color, number, short_name, is_gk=is_gk)
            except Exception: pass

    if lineups.get("home"): _draw_team(lineups["home"], True, h_color, form_h)
    if lineups.get("away"): _draw_team(lineups["away"], False, a_color, form_a)
    return _encode(fig, save_path)

# Image 5: Goal Post Map
def goal_post_map(summary: Dict, save_path=None) -> str:
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.patch.set_facecolor(BG)
    
    _add_opta_header(fig, "Goal Mouth Analysis", "Shot Placement & Outcomes")
    
    h_color = summary.get('home_color', HOME_CLR)
    a_color = summary.get('away_color', AWAY_CLR)
    
    shots = summary.get('raw_shotmap', [])
    
    def _draw_goal(ax, title, team_color, is_home):
        ax.set_facecolor(BG)
        ax.set_title(title, color=TEXT_MAIN, fontsize=14, fontweight='bold', pad=20)
        
        # Real Goal dimensions in meters
        post_l = -3.66
        post_r = 3.66
        crossbar = 2.44
        
        # Draw Grass line
        ax.plot([-6, 6], [0, 0], color='#1e3f20', lw=3, zorder=1)
        
        # Draw Goal Frame
        ax.plot([post_l, post_l], [0, crossbar], color='white', lw=6, zorder=3)
        ax.plot([post_r, post_r], [0, crossbar], color='white', lw=6, zorder=3)
        ax.plot([post_l, post_r], [crossbar, crossbar], color='white', lw=6, zorder=3)
        
        # Draw Net
        for i in np.linspace(post_l, post_r, 15):
            ax.plot([i, i], [0, crossbar], color='white', lw=0.5, alpha=0.3, zorder=2)
        for i in np.linspace(0, crossbar, 6):
            ax.plot([post_l, post_r], [i, i], color='white', lw=0.5, alpha=0.3, zorder=2)
            
        # Draw Top Corner targets
        theta1 = np.linspace(-np.pi/2, 0, 50)
        ax.plot(-3.66 + 0.6*np.cos(theta1), 2.44 + 0.6*np.sin(theta1), color=GOLD, linestyle='--', lw=1, alpha=0.6, zorder=2)
        theta2 = np.linspace(np.pi, 1.5*np.pi, 50)
        ax.plot(3.66 + 0.6*np.cos(theta2), 2.44 + 0.6*np.sin(theta2), color=GOLD, linestyle='--', lw=1, alpha=0.6, zorder=2)
            
        ax.set_aspect('equal')
        # Wider xlim so goal posts appear larger and well-proportioned
        ax.set_xlim(-5.8, 5.8)
        ax.set_ylim(-0.8, 4.2)
        ax.axis('off')
        
        team_shots = [s for s in shots if s.get('isHome', True) == is_home and 'goalMouthCoordinates' in s]
        
        goals_count = len([s for s in team_shots if s.get('shotType') == 'goal'])
        saves_count = len([s for s in team_shots if s.get('shotType') == 'save'])
        misses_count = len([s for s in team_shots if s.get('shotType') not in ['goal', 'save']])
        
        xgot_vals = [s.get('xgot') for s in team_shots if s.get('xgot') is not None]
        avg_xgot = sum(xgot_vals)/len(xgot_vals) if xgot_vals else 0.0
        
        # Display Stats card
        stats_text = (
            f"Shots: {len(team_shots)}\n"
            f"Goals: {goals_count}\n"
            f"Saves: {saves_count}\n"
            f"Misses: {misses_count}\n"
            f"Avg xGOT: {avg_xgot:.2f}"
        )
        # Positioned stats card in the bottom-left corner below the ground to avoid top-90 overlap
        ax.text(-3.5, 3, stats_text, color=TEXT_SEC, fontsize=9, va='bottom', ha='left',
                bbox=dict(facecolor=BG, alpha=0.8, edgecolor=GRID_LINE, boxstyle='round,pad=0.5'))
        
        for s in team_shots:
            coords = s.get('goalMouthCoordinates', {})
            y = coords.get('y', 50)
            z = coords.get('z', 0)
            stype = s.get('shotType', '')
            
            # Convert SofaScore coordinates to meters
            y_m = (y - 50) * 0.68
            z_m = z * (2.44 / 38.0)
            plot_x = -y_m 
            
            if stype == 'goal':
                marker, color, size, zorder = 'o', team_color, 150, 5
                
                # Annotate goal scorer
                name = s.get('player', {}).get('shortName', s.get('player', {}).get('name', ''))
                time = s.get('time', 0)
                ax.text(plot_x, z_m + 0.15, f"{name} {time}'", color=TEXT_MAIN, fontsize=8, fontweight='bold',
                        ha='center', va='bottom', bbox=dict(facecolor=BG, alpha=0.7, edgecolor='none', pad=0.5), zorder=6)
            elif stype == 'save':
                marker, color, size, zorder = 'o', '#1f77b4', 100, 4
            else:
                marker, color, size, zorder = 'X', '#d62728', 80, 3
                
            ax.scatter(plot_x, z_m, marker=marker, color=color, s=size, edgecolors='white', lw=1, zorder=zorder)

        # Legend
        import matplotlib.lines as mlines
        l_goal = mlines.Line2D([], [], color=team_color, marker='o', linestyle='None', markersize=10, label='Goal')
        l_save = mlines.Line2D([], [], color='#1f77b4', marker='o', linestyle='None', markersize=8, label='Saved')
        l_miss = mlines.Line2D([], [], color='#d62728', marker='X', linestyle='None', markersize=8, label='Miss/Woodwork')
        ax.legend(handles=[l_goal, l_save, l_miss], loc='lower center', bbox_to_anchor=(0.5, -0.15), ncol=3, frameon=False, labelcolor=TEXT_SEC)

    _draw_goal(axes[0], summary.get('home_team', 'Home'), h_color, True)
    _draw_goal(axes[1], summary.get('away_team', 'Away'), a_color, False)
    
    return _encode(fig, save_path)

# Image 6: Assists Map
def assist_map(summary: Dict, save_path=None) -> str:
    events = summary.get('timeline_intelligence', {}).get('events', [])
    if not events:
        events = summary.get('raw_events', [])
        
    assists = []
    for ev in events:
        if ev.get('incidentType') == 'goal' and ev.get('incidentClass') != 'penalty' and ev.get('situation') != 'shootout':
            actions = ev.get('footballPassingNetworkAction', [])
            if actions:
                passes = [a for a in actions if a.get('eventType') == 'pass']
                if passes:
                    last_pass = passes[-1]
                    scorer = ev.get('player', {}).get('shortName', ev.get('player', {}).get('name', ''))
                    assists.append({
                        'is_home': ev.get('isHome', True),
                        'provider': last_pass.get('player', {}).get('shortName', last_pass.get('player', {}).get('name', 'Unknown')),
                        'start_x': last_pass.get('playerCoordinates', {}).get('x', 0),
                        'start_y': last_pass.get('playerCoordinates', {}).get('y', 0),
                        'end_x': last_pass.get('passEndCoordinates', {}).get('x', 0),
                        'end_y': last_pass.get('passEndCoordinates', {}).get('y', 0),
                        'scorer': scorer,
                        'time': ev.get('time', 0)
                    })
                    
    if not assists:
        if save_path and os.path.exists(save_path):
            try:
                os.remove(save_path)
            except Exception:
                pass
        return ""
        
    pitch = Pitch(pitch_type='opta', pitch_color=BG, line_color=PITCH_LINE, linewidth=1.5)
    fig, ax = pitch.draw(figsize=(12, 8))
    fig.patch.set_facecolor(BG)
    
    h_color = summary.get('home_color', HOME_CLR)
    a_color = summary.get('away_color', AWAY_CLR)
    
    _add_opta_header(fig, "Assist Map", "Chances Created Leading to Goals")
    
    for a in assists:
        color = h_color if a['is_home'] else a_color
        
        # SofaScore coordinates are absolute (0 to 100)
        # Opta coordinates are 100 x 100
        x1 = a['start_x']
        y1 = 100.0 - a['start_y']
        x2 = a['end_x']
        y2 = 100.0 - a['end_y']
        
        # Draw pass arrow
        pitch.arrows(x1, y1, x2, y2, ax=ax, width=3, headwidth=6, color=color, zorder=2, alpha=0.8)
        
        # Start dot (Assist provider)
        pitch.scatter(x1, y1, ax=ax, color=color, s=150, zorder=3, edgecolors='white', lw=1)
        ax.text(x1, y1 - 2.5, f"{a['provider']}", ha='center', va='bottom', fontsize=10, fontweight='bold', color=TEXT_MAIN,
                bbox=dict(facecolor=BG, alpha=0.6, edgecolor='none', pad=1))
                
        # End dot (Scorer position)
        pitch.scatter(x2, y2, ax=ax, color=color, s=250, marker='*', zorder=4, edgecolors='white', lw=1)
        ax.text(x2, y2 + 2.5, f"{a['scorer']} {a['time']}'", ha='center', va='top', fontsize=9, fontweight='bold', color=TEXT_SEC,
                bbox=dict(facecolor=BG, alpha=0.6, edgecolor='none', pad=1))
                
    # Add Legend
    import matplotlib.lines as mlines
    l_prov = mlines.Line2D([], [], color=GOLD, marker='o', linestyle='None', markersize=8, label='Assist Provider')
    l_arrow = mlines.Line2D([], [], color=GOLD, marker='>', linestyle='-', markersize=8, label='Key Pass')
    l_score = mlines.Line2D([], [], color=GOLD, marker='*', linestyle='None', markersize=10, label='Goal Scorer')
    ax.legend(handles=[l_prov, l_arrow, l_score], loc='lower center', bbox_to_anchor=(0.5, -0.08), ncol=3, frameon=False, labelcolor=TEXT_SEC)
    
    return _encode(fig, save_path)

# Image 7: Defensive Actions
def most_defensive_chart(summary: Dict, save_path=None) -> str:
    h_best = None; a_best = None
    h_max = -1; a_max = -1
    
    for p in summary.get('player_stats', []):
        st = p.get('stats', {})
        def_actions = (st.get('totalTackle', 0) + 
                       st.get('interceptionWon', 0) + 
                       st.get('totalClearance', 0) + 
                       st.get('blockedScoringAttempt', 0) + 
                       st.get('outfielderBlock', 0))
        if p.get('team') == 'home':
            if def_actions > h_max: h_max = def_actions; h_best = p
        else:
            if def_actions > a_max: a_max = def_actions; a_best = p
                
    fig, ax = plt.subplots(figsize=(12, 8))
    fig.patch.set_facecolor(BG); ax.set_facecolor(BG); ax.axis('off')
    
    # Enable coordinates 0 to 1 on axes for exact placement
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    
    h_color = summary.get('home_color', HOME_CLR)
    a_color = summary.get('away_color', AWAY_CLR)
    
    _add_opta_header(fig, "Defensive Rocks", "Most Defensive Actions & Defensive Stats")
    
    def _draw_p(p, x_pos, color):
        if not p: return
        p_id = p.get("id")
        name = p.get("name", "Unknown")
        st = p.get("stats", {})
        
        # Player Photo (Large Circular)
        photo = _get_player_photo(p_id)
        if photo:
            circ = _circular_image(photo, size=(180, 180), border_color=color)
            ax.add_artist(AnnotationBbox(OffsetImage(circ, zoom=0.9), (x_pos, 0.76), frameon=False))
            
        # Player Name
        ax.text(x_pos, 0.48, name, ha='center', fontsize=16, fontweight='900', color=TEXT_MAIN)
        
        # Match Rating Badge (Plain text "Rating: X.X")
        rating = p.get("rating", "N/A")
        try:
            rating_str = f"{float(rating):.1f}"
        except Exception:
            rating_str = str(rating)
            
        rating_label = f"Rating: {rating_str}"
        ax.text(x_pos, 0.41, rating_label, ha='center', va='center', fontsize=11, fontweight='bold', color=GOLD,
                bbox=dict(facecolor='#1c1917', alpha=0.9, edgecolor=GOLD, boxstyle='round,pad=0.3', lw=1.0), zorder=4)
                
        # Detailed Stats
        stats_lines = [
            f"Tackles Won: {int(st.get('wonTackle', 0))}/{int(st.get('totalTackle', 0))}",
            f"Interceptions: {int(st.get('interceptionWon', 0))}",
            f"Clearances: {int(st.get('totalClearance', 0))}",
            f"Blocked Shots: {int(st.get('outfielderBlock', 0))}",
            f"Duels Won: {int(st.get('duelWon', 0))}/{int(st.get('duelWon', 0)+st.get('duelLost', 0))}",
            f"Ball Recoveries: {int(st.get('ballRecovery', 0))}"
        ]
        
        y_offset = 0.32
        for line in stats_lines:
            key, val = line.split(": ")
            ax.text(x_pos - 0.18, y_offset, key, color=TEXT_SEC, fontsize=11, ha='left', fontweight='semibold')
            ax.text(x_pos + 0.18, y_offset, val, color=color, fontsize=12, ha='right', fontweight='bold')
            y_offset -= 0.04

    _draw_p(h_best, 0.25, h_color)
    _draw_p(a_best, 0.75, a_color)
    
    # Vertical divider line
    ax.axvline(0.5, color=GRID_LINE, lw=1, ymin=0.15, ymax=0.85)
    _add_team_legend(fig, summary, h_color, a_color)
    
    return _encode(fig, save_path)

# Image 8: Most Shots
def most_shots_chart(summary: Dict, save_path=None) -> str:
    h_best = None; a_best = None
    h_max = -1; a_max = -1
    
    for p in summary.get('player_stats', []):
        st = p.get('stats', {})
        shots = st.get('shotOffTarget', 0) + st.get('onTargetScoringAttempt', 0) + st.get('blockedScoringAttempt', 0)
        if p.get('team') == 'home':
            if shots > h_max: h_max = shots; h_best = p
        else:
            if shots > a_max: a_max = shots; a_best = p
                
    fig, ax = plt.subplots(figsize=(12, 8))
    fig.patch.set_facecolor(BG); ax.set_facecolor(BG); ax.axis('off')
    
    # Enable coordinates 0 to 1 on axes for exact placement
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    
    h_color = summary.get('home_color', HOME_CLR)
    a_color = summary.get('away_color', AWAY_CLR)
    
    _add_opta_header(fig, "Attacking Threats", "Most Shots & Shooting Stats")
    
    def _draw_p(p, total_shots, x_pos, color):
        if not p: return
        p_id = p.get("id")
        name = p.get("name", "Unknown")
        st = p.get("stats", {})
        
        # Player Photo (Large Circular)
        photo = _get_player_photo(p_id)
        if photo:
            circ = _circular_image(photo, size=(180, 180), border_color=color)
            ax.add_artist(AnnotationBbox(OffsetImage(circ, zoom=0.9), (x_pos, 0.76), frameon=False))
            
        # Player Name
        ax.text(x_pos, 0.48, name, ha='center', fontsize=16, fontweight='900', color=TEXT_MAIN)
        
        # Total Shots Badge (On Top)
        ax.text(x_pos, 0.41, f"Total Shots: {total_shots}", ha='center', fontsize=11, fontweight='bold', color=GOLD,
                bbox=dict(facecolor='#1c1917', alpha=0.9, edgecolor=GOLD, boxstyle='round,pad=0.3'))
                
        # Detailed Stats
        rating = p.get("rating", "N/A")
        try:
            rating_str = f"{float(rating):.1f}"
        except Exception:
            rating_str = str(rating)
            
        stats_lines = [
            f"On Target: {int(st.get('onTargetScoringAttempt', 0))}",
            f"Off Target: {int(st.get('shotOffTarget', 0))}",
            f"Blocked Shots: {int(st.get('blockedScoringAttempt', 0))}",
            f"Match Rating: {rating_str}"
        ]
        
        y_offset = 0.32
        for line in stats_lines:
            key, val = line.split(": ")
            ax.text(x_pos - 0.18, y_offset, key, color=TEXT_SEC, fontsize=11, ha='left', fontweight='semibold')
            ax.text(x_pos + 0.18, y_offset, val, color=color, fontsize=12, ha='right', fontweight='bold')
            y_offset -= 0.04

    _draw_p(h_best, h_max, 0.25, h_color)
    _draw_p(a_best, a_max, 0.75, a_color)
    
    # Vertical divider line
    ax.axvline(0.5, color=GRID_LINE, lw=1, ymin=0.15, ymax=0.85)
    _add_team_legend(fig, summary, h_color, a_color)
    
    return _encode(fig, save_path)

# Image 9: Momentum
def momentum_chart(summary: Dict, save_path=None) -> str:
    def _make_transparent(img: Image.Image, alpha: float) -> Image.Image:
        if not img: return None
        img = img.convert("RGBA")
        r, g, b, a = img.split()
        a = a.point(lambda p: int(p * alpha))
        return Image.merge("RGBA", (r, g, b, a))

    momentum = summary.get("raw_momentum", [])
    if not momentum:
        return ""
        
    x = [m.get("minute", 0) for m in momentum]
    y = [m.get("value", 0) for m in momentum]
    
    # Split into first half and second half
    x_fh, y_fh = [], []
    x_sh, y_sh = [], []
    for mi, val in zip(x, y):
        if mi <= 45:
            x_fh.append(mi)
            y_fh.append(val)
        else:
            x_sh.append(mi)
            y_sh.append(val)
            
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 7), sharey=True)
    fig.patch.set_facecolor(BG)
    
    # Tight spacing with a subtle gap in the middle
    plt.subplots_adjust(wspace=0.08, top=0.82, bottom=0.15, left=0.15, right=0.95)
    
    h_color = summary.get('home_color', HOME_CLR)
    a_color = summary.get('away_color', AWAY_CLR)
    
    _add_opta_header(fig, "Match Momentum", f"{summary.get('home_team', '')} vs {summary.get('away_team', '')}")
    
    # Setup subplots properties
    max_min = max(x_sh) if x_sh else 90
    max_min = max(max_min, 90)
    
    ax1.set_facecolor(BG)
    ax1.set_xlim(0, 45)
    ax1.set_xticks([0, 15, 30, 45])
    ax1.set_xticklabels(["0'", "15'", "30'", "45'"], color=TEXT_SEC, fontsize=10, fontweight='bold')
    ax1.title.set_text("FIRST HALF")
    ax1.title.set_color(TEXT_SEC)
    ax1.title.set_fontsize(12)
    ax1.title.set_fontweight('bold')
    
    ax2.set_facecolor(BG)
    ax2.set_xlim(45, max_min)
    if max_min > 95:
        ax2.set_xticks([45, 60, 75, 90, 105, 120])
        ax2.set_xticklabels(["45'", "60'", "75'", "90'", "105'", "120'"], color=TEXT_SEC, fontsize=10, fontweight='bold')
    else:
        ax2.set_xticks([45, 60, 75, 90])
        ax2.set_xticklabels(["45'", "60'", "75'", "90'"], color=TEXT_SEC, fontsize=10, fontweight='bold')
    ax2.title.set_text("SECOND HALF")
    ax2.title.set_color(TEXT_SEC)
    ax2.title.set_fontsize(12)
    ax2.title.set_fontweight('bold')
    
    # Add vertical gridlines at 15-minute intervals
    ax1.axvline(15, color=GRID_LINE, linestyle=':', alpha=0.3, zorder=1)
    ax1.axvline(30, color=GRID_LINE, linestyle=':', alpha=0.3, zorder=1)
    ax2.axvline(60, color=GRID_LINE, linestyle=':', alpha=0.3, zorder=1)
    ax2.axvline(75, color=GRID_LINE, linestyle=':', alpha=0.3, zorder=1)
    if max_min >= 90:
        ax2.axvline(90, color=GRID_LINE, linestyle=':', alpha=0.3, zorder=1)
    if max_min >= 105:
        ax2.axvline(105, color=GRID_LINE, linestyle=':', alpha=0.3, zorder=1)
        
    for ax_sub in [ax1, ax2]:
        ax_sub.set_ylim(-100, 100)
        ax_sub.grid(False)
        ax_sub.axhline(0, color=GRID_LINE, lw=1.5, zorder=1)
        for spine in ax_sub.spines.values():
            spine.set_visible(False)
            
    # Draw descriptors on ax1 (strictly no emojis/symbols to avoid Windows font squares)
    ax1.text(-2, 0, "Balanced", color=TEXT_SEC, fontsize=9, ha='right', va='center', clip_on=False)
    ax1.text(-2, 60, f"{summary.get('home_team', 'Home')}\n   more threatening", color=h_color, fontsize=9, ha='right', va='center', fontweight='bold', clip_on=False)
    ax1.text(-2, -60, f"{summary.get('away_team', 'Away')}\n   more threatening", color=a_color, fontsize=9, ha='right', va='center', fontweight='bold', clip_on=False)
    
    # Y-axis vertical title label
    fig.text(0.04, 0.5, "Attacking Threat", rotation=90, color=TEXT_MAIN, fontsize=12, fontweight='bold', va='center', ha='center')
    
    # Fetch team logos and apply watermark transparency
    hl = _get_team_logo(summary.get("home_team_id"))
    al = _get_team_logo(summary.get("away_team_id"))
    hl_watermark = _make_transparent(hl, 0.08) if hl else None
    al_watermark = _make_transparent(al, 0.08) if al else None
    
    # Place Logo Watermarks behind the curves
    if hl_watermark:
        ax1.add_artist(AnnotationBbox(OffsetImage(hl_watermark.resize((150, 150))), (22.5, 50), frameon=False, zorder=0))
        ax2.add_artist(AnnotationBbox(OffsetImage(hl_watermark.resize((150, 150))), ((45 + max_min)/2, 50), frameon=False, zorder=0))
    if al_watermark:
        ax1.add_artist(AnnotationBbox(OffsetImage(al_watermark.resize((150, 150))), (22.5, -50), frameon=False, zorder=0))
        ax2.add_artist(AnnotationBbox(OffsetImage(al_watermark.resize((150, 150))), ((45 + max_min)/2, -50), frameon=False, zorder=0))
        
    # Plot curves and fills
    if x_fh:
        ax1.plot(x_fh, y_fh, color=TEXT_SEC, lw=1.2, alpha=0.8, zorder=2)
        ax1.fill_between(x_fh, y_fh, 0, where=(np.array(y_fh) >= 0), color=h_color, alpha=0.65, interpolate=True, zorder=2)
        ax1.fill_between(x_fh, y_fh, 0, where=(np.array(y_fh) < 0), color=a_color, alpha=0.65, interpolate=True, zorder=2)
    if x_sh:
        ax2.plot(x_sh, y_sh, color=TEXT_SEC, lw=1.2, alpha=0.8, zorder=2)
        ax2.fill_between(x_sh, y_sh, 0, where=(np.array(y_sh) >= 0), color=h_color, alpha=0.65, interpolate=True, zorder=2)
        ax2.fill_between(x_sh, y_sh, 0, where=(np.array(y_sh) < 0), color=a_color, alpha=0.65, interpolate=True, zorder=2)
        
    # Incidents annotations (Goals & Substitutions)
    events = summary.get("raw_events", [])
    goals_to_draw = []
    subs_to_draw = []
    
    for ev in events:
        itype = ev.get("incidentType")
        time = ev.get("time", 0)
        is_home = ev.get("isHome", True)
        
        # Include penalty goals that occurred during regular match time (excluding shootout situations)
        if itype == "goal" and ev.get("situation") != "shootout" and time <= 120:
            goals_to_draw.append((time, is_home))
        elif itype == "substitution":
            subs_to_draw.append((time, is_home))
            
    def _draw_events(ax_target, time, is_home, is_goal):
        color = h_color if is_home else a_color
        if is_goal:
            val = 0
            for mi, v in zip(x, y):
                if mi == time:
                    val = v
                    break
            y_target = 62 if is_home else -62
            ax_target.plot([time, time], [val, y_target], color=color, linestyle='--', lw=1.2, zorder=3)
            # Create a label with spaces on the left for the ball image
            goal_label = f"   {time}'"
            ax_target.text(time, y_target, goal_label, color='#ffffff', fontsize=8, fontweight='black',
                           ha='center', va='center', bbox=dict(facecolor=GOLD, alpha=0.95, edgecolor='none', boxstyle='round,pad=0.25'), zorder=4)
            ball_img = _get_emoji_ball()
            if ball_img:
                # Place the ball image exactly 11 points to the left of the goal text!
                ax_target.add_artist(AnnotationBbox(OffsetImage(ball_img.resize((12, 12)), zoom=1.0), (time, y_target),
                                                   xybox=(-11, 0), boxcoords="offset points", frameon=False, zorder=5))
        else:
            y_pos = 85 if is_home else -85
            # Clean floating Twemoji substitution image without any surrounding circle container
            sub_img = _get_emoji_sub()
            if sub_img:
                ax_target.add_artist(AnnotationBbox(OffsetImage(sub_img.resize((14, 14)), zoom=1.0), (time, y_pos), frameon=False, zorder=4))

    for time, is_home in goals_to_draw:
        if time <= 45:
            _draw_events(ax1, time, is_home, True)
        else:
            _draw_events(ax2, time, is_home, True)
            
    for time, is_home in subs_to_draw:
        if time <= 45:
            _draw_events(ax1, time, is_home, False)
        else:
            _draw_events(ax2, time, is_home, False)
            
    _add_team_legend(fig, summary, h_color, a_color, y_pos=0.04)
    return _encode(fig, save_path)

# Generic Player Comp for 10 & 11
def _player_comp(p1, p2, title, subtitle, summary, save_path=None):
    fig, ax = plt.subplots(figsize=(12, 8))
    fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
    ax.axis('off')
    _add_opta_header(fig, title, subtitle)
    
    # Coordinates from 0 to 1 for exact placement
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    
    h_color = summary.get('home_color', HOME_CLR)
    a_color = summary.get('away_color', AWAY_CLR)
    
    is_elite = "Elite" in title or "Highest" in subtitle
    
    def _draw_p(p, x_pos, color):
        if not p: return
        p_id = p.get("id") or p.get("player", {}).get("id")
        name = p.get("name") or p.get("player", {}).get("name", "Unknown")
        st = p.get("stats", {})
        rating = _fmt(p.get("rating", "—"))
        
        # Player Photo (Large Circular)
        photo = _get_player_photo(p_id)
        if photo:
            circ = _circular_image(photo, size=(180, 180), border_color=color)
            ax.add_artist(AnnotationBbox(OffsetImage(circ, zoom=0.9), (x_pos, 0.76), frameon=False))
            
        # Player Name
        ax.text(x_pos, 0.48, name, ha='center', fontsize=16, fontweight='900', color=TEXT_MAIN)
        
        # Match Rating Badge (strictly plain text "Rating: X.X", no emoji star!)
        rating_label = f"Rating: {rating}"
        ax.text(x_pos, 0.41, rating_label, ha='center', va='center', fontsize=11, fontweight='bold', color=color,
                bbox=dict(facecolor='#1c1917', alpha=0.9, edgecolor=color, boxstyle='round,pad=0.3', lw=1.0), zorder=4)
                
        # Detailed Stats for Player Comparison
        if is_elite:
            # Stats for Elite Performers (Image 11)
            stats_lines = [
                f"Goals: {int(st.get('goals', 0))}",
                f"Assists: {int(st.get('goalAssist', 0))}",
                f"Key Passes: {int(st.get('keyPass', 0))}",
                f"Total Shots: {int(st.get('totalShots', 0))}",
                f"Pass Accuracy: {int(st.get('accuratePass', 0))}/{int(st.get('totalPass', 0))}",
                f"Duels Won: {int(st.get('duelWon', 0))}/{int(st.get('duelWon', 0)+st.get('duelLost', 0))}"
            ]
        else:
            # Stats for Underperforming / Mistakes / Turnovers (Image 10)
            stats_lines = [
                f"Big Chances Missed: {int(st.get('bigChanceMissed', 0))}",
                f"Possession Lost: {int(st.get('possessionLostCtrl', 0))}",
                f"Unsuccessful Touches: {int(st.get('unsuccessfulTouch', 0))}",
                f"Dispossessed: {int(st.get('dispossessed', 0))}",
                f"Duels Lost: {int(st.get('duelLost', 0))}",
                f"Fouls Committed: {int(st.get('fouls', 0))}"
            ]
            
        y_offset = 0.32
        for line in stats_lines:
            if ": " in line:
                key, val = line.split(": ")
            else:
                key, val = line, ""
            ax.text(x_pos - 0.18, y_offset, key, color=TEXT_SEC, fontsize=11, ha='left', fontweight='semibold')
            ax.text(x_pos + 0.18, y_offset, val, color=color, fontsize=12, ha='right', fontweight='bold')
            y_offset -= 0.04

    _draw_p(p1, 0.25, h_color)
    _draw_p(p2, 0.75, a_color)
    
    # Vertical divider line
    ax.axvline(0.5, color=GRID_LINE, lw=1, ymin=0.15, ymax=0.85)
    _add_team_legend(fig, summary, h_color, a_color)
    return _encode(fig, save_path)

def star_players_chart(summary: Dict, save_path=None) -> str:
    pa = summary.get("player_analytics", {})
    return _player_comp(pa.get("best_home"), pa.get("best_away"), "Elite Performers", "Highest Rated Players", summary, save_path)

def big_chances_chart(summary: Dict, save_path=None) -> str:
    pa = summary.get("player_analytics", {})
    return _player_comp(pa.get("worst_home"), pa.get("worst_away"), "Match Struggles", "Lowest Rated Players", summary, save_path)

# Image 12: Heatmap Zones (32-Zone Team Territory Dominance Map)
def danger_chart(summary: Dict, save_path=None) -> str:
    pitch = Pitch(pitch_type="opta", pitch_color=BG, line_color=PITCH_LINE, linewidth=1.5)
    fig, ax = pitch.draw(figsize=(12, 8))
    fig.patch.set_facecolor(BG)
    _add_opta_header(fig, "Team Territory Map", "Pitch Dominance & Zone Control (32 Spatial Zones)")
    
    h_color = summary.get('home_color', HOME_CLR)
    a_color = summary.get('away_color', AWAY_CLR)
    
    cols, rows = 8, 4
    x_step = 100.0 / cols
    y_step = 100.0 / rows
    
    # Grid of home and away points count
    home_grid = np.zeros((rows, cols))
    away_grid = np.zeros((rows, cols))
    
    # 1. Base control from team possession
    h_poss = summary.get('possession', {}).get('home', 50)
    for r in range(rows):
        for c in range(cols):
            base_home = 3.0 * (h_poss / 50.0) if c < cols/2 else 0.8 * (h_poss / 50.0)
            base_away = 3.0 * ((100.0 - h_poss) / 50.0) if c >= cols/2 else 0.8 * ((100.0 - h_poss) / 50.0)
            home_grid[r, c] += base_home
            away_grid[r, c] += base_away
            
    # 2. Add player average touches/positions from heatmaps
    for p in summary.get('player_stats', []):
        team = p.get('team')
        pts = p.get('heatmap', [])
        if not pts: continue
        
        for pt in pts:
            x = pt.get('x', 50)
            y = pt.get('y', 50)
            
            # Map to absolute Opta pitch coordinates
            if team == 'home':
                abs_x = x
            else:
                abs_x = 100.0 - x
            abs_y = 100.0 - y
            
            c = int(abs_x / x_step)
            r = int(abs_y / y_step)
            c = max(0, min(c, cols - 1))
            r = max(0, min(r, rows - 1))
            
            if team == 'home':
                home_grid[r, c] += 1.5
            else:
                away_grid[r, c] += 1.5
                
    # Draw the zones and labels
    for r in range(rows):
        for c in range(cols):
            home_pts = home_grid[r, c]
            away_pts = away_grid[r, c]
            total_pts = home_pts + away_pts
            
            if total_pts > 0:
                home_pct = (home_pts / total_pts) * 100
            else:
                home_pct = 50.0
                
            if home_pct > 50:
                color = h_color
                alpha = min((home_pct - 50) * 0.018, 0.6)
                text_pct = f"{home_pct:.0f}%"
            else:
                color = a_color
                away_pct = 100.0 - home_pct
                alpha = min((away_pct - 50) * 0.018, 0.6)
                text_pct = f"{away_pct:.0f}%"
                
            # Draw the grid rectangle
            rect = mpatches.Rectangle((c * x_step, r * y_step), x_step, y_step, 
                                      facecolor=color, alpha=alpha, edgecolor=BG, lw=1.0, zorder=2)
            ax.add_patch(rect)
            
            # Draw the percentage text
            x_center = c * x_step + x_step / 2
            y_center = r * y_step + y_step / 2
            ax.text(x_center, y_center, text_pct, color='#ffffff', fontsize=10, ha='center', va='center', fontweight='bold', zorder=3)
            
    return _encode(fig, save_path)
def buildup_chart(summary: Dict, save_path=None) -> str:
    # 1. Retrieve average positions and lineups
    avg_pos_data = summary.get("average_positions", {})
    home_raw = avg_pos_data.get("home", [])
    away_raw = avg_pos_data.get("away", [])
    
    # Support both raw SofaScore dictionary containing a "players" key and pre-parsed lists
    home_avg = home_raw.get("players", []) if isinstance(home_raw, dict) else (home_raw if isinstance(home_raw, list) else [])
    away_avg = away_raw.get("players", []) if isinstance(away_raw, dict) else (away_raw if isinstance(away_raw, list) else [])
    
    # Build lookup dictionaries normalized to match the expected format
    home_lookup = {}
    for item in home_avg:
        if not isinstance(item, dict):
            continue
        p_obj = item.get("player")
        p_id = p_obj.get("id") if isinstance(p_obj, dict) else item.get("player_id")
        if not p_id:
            continue
        avg_x = item.get("averageX") if item.get("averageX") is not None else item.get("avgX")
        avg_y = item.get("averageY") if item.get("averageY") is not None else item.get("avgY")
        pts = item.get("pointsCount") if item.get("pointsCount") is not None else item.get("pts", 30)
        home_lookup[p_id] = {
            "averageX": avg_x,
            "averageY": avg_y,
            "pointsCount": pts
        }
        
    away_lookup = {}
    for item in away_avg:
        if not isinstance(item, dict):
            continue
        p_obj = item.get("player")
        p_id = p_obj.get("id") if isinstance(p_obj, dict) else item.get("player_id")
        if not p_id:
            continue
        avg_x = item.get("averageX") if item.get("averageX") is not None else item.get("avgX")
        avg_y = item.get("averageY") if item.get("averageY") is not None else item.get("avgY")
        pts = item.get("pointsCount") if item.get("pointsCount") is not None else item.get("pts", 30)
        away_lookup[p_id] = {
            "averageX": avg_x,
            "averageY": avg_y,
            "pointsCount": pts
        }
        
    lineups = summary.get("tactical_intelligence", {}).get("lineups_full", {}) or summary.get("lineups_full", {})
    
    # Set up Pitch and side-by-side vertical layout
    pitch = VerticalPitch(pitch_type='opta', pitch_color=BG, line_color=PITCH_LINE, linewidth=1.5)
    fig, axes = plt.subplots(1, 2, figsize=(15, 10))
    fig.patch.set_facecolor(BG)
    
    h_color = summary.get('home_color', HOME_CLR)
    a_color = summary.get('away_color', AWAY_CLR)
    
    # Dual Opta-style title
    _add_opta_header(fig, "Passing Networks", "Tactical Shapes & Team Passing Links")
    
    # Draw pitches on each axis
    pitch.draw(ax=axes[0])
    pitch.draw(ax=axes[1])
    
    if not lineups:
        # Fallback to empty network message if no lineups
        axes[0].text(50, 50, "No passing network data available", ha='center', va='center', fontsize=16, color=TEXT_SEC)
        axes[1].text(50, 50, "No passing network data available", ha='center', va='center', fontsize=16, color=TEXT_SEC)
        _add_team_legend(fig, summary, h_color, a_color, y_pos=0.03)
        return _encode(fig, save_path)
        
    # 2. Extract Home Starters positions
    home_starters = []
    for i, p in enumerate(lineups.get("home", {}).get("players", [])[:11]):
        p_obj = p.get("player", {})
        p_id = p_obj.get("id")
        number = p.get("shirtNumber", "")
        name = p_obj.get("shortName", p_obj.get("name", "Starter"))
        
        avg_item = home_lookup.get(p_id)
        if avg_item:
            ax_val = avg_item.get("averageX", 50)
            ay_val = avg_item.get("averageY", 50)
            # Scale SofaScore (0-100) to Opta (100x100)
            px = ax_val
            py = 100.0 - ay_val
        else:
            # Fallback based on lineup index
            row_idx = i // 3 + 1
            col_idx = (i % 3) * 2 + 2
            px = 10 + row_idx * 12
            py = 100 - col_idx * 12
            
        home_starters.append({
            "id": p_id, "name": name, "number": number, "x": px, "y": py
        })
        
    # 3. Extract Away Starters positions (oriented bottom-to-top on their own pitch)
    away_starters = []
    for i, p in enumerate(lineups.get("away", {}).get("players", [])[:11]):
        p_obj = p.get("player", {})
        p_id = p_obj.get("id")
        number = p.get("shirtNumber", "")
        name = p_obj.get("shortName", p_obj.get("name", "Starter"))
        
        avg_item = away_lookup.get(p_id)
        if avg_item:
            ax_val = avg_item.get("averageX", 50)
            ay_val = avg_item.get("averageY", 50)
            # Scale SofaScore (0-100) to Opta (100x100)
            px = ax_val
            py = 100.0 - ay_val
        else:
            row_idx = i // 3 + 1
            col_idx = (i % 3) * 2 + 2
            px = 10 + row_idx * 12
            py = 100 - col_idx * 12
            
        away_starters.append({
            "id": p_id, "name": name, "number": number, "x": px, "y": py
        })
        
    def _draw_vertical_network(ax, starters, lookup, color):
        n = len(starters)
        # Draw edges (passing lines)
        for i in range(n):
            for j in range(i+1, n):
                p1 = starters[i]
                p2 = starters[j]
                
                dx = p1["x"] - p2["x"]
                dy = p1["y"] - p2["y"]
                dist = np.sqrt(dx*dx + dy*dy)
                
                if i == 0:  # GK only connects to CBs / FBs within 28 yards
                    if dist > 28.0:
                        continue
                        
                item1 = lookup.get(p1["id"], {})
                item2 = lookup.get(p2["id"], {})
                pts1 = item1.get("pointsCount", 30)
                pts2 = item2.get("pointsCount", 30)
                
                if 5.0 < dist < 35.0:
                    weight = (pts1 + pts2) / (dist + 5.0) * 0.45
                    weight = max(0.5, min(weight, 5.0))
                    alpha = max(0.15, min(weight / 5.0 * 0.7, 0.75))
                    pitch.plot([p1["x"], p2["x"]], [p1["y"], p2["y"]], ax=ax, color=color, lw=weight, alpha=alpha, zorder=3)
                    
        # Draw nodes and labels
        for p in starters:
            px, py = p["x"], p["y"]
            number = p["number"]
            name = p["name"]
            
            item = lookup.get(p["id"], {})
            pts = item.get("pointsCount", 30)
            
            radius = 2.0 + (pts / 120.0) * 1.5
            radius = max(2.2, min(radius, 4.0))
            
            s_val = 180 + (pts / 120.0) * 200
            s_val = max(200, min(s_val, 480))
            
            # Nodes
            pitch.scatter(px, py, ax=ax, color=color, s=s_val, edgecolors='#ffffff', linewidths=1.5, zorder=5)
            # Numbers
            pitch.annotate(str(number), (px, py), ax=ax, ha='center', va='center', fontsize=9, fontweight='black', color='#ffffff', zorder=7)
            # Names
            name_offset_x = px - radius - 1.8
            pitch.annotate(name, (name_offset_x, py), ax=ax, ha='center', va='top', fontsize=8, fontweight='bold', color=TEXT_MAIN,
                           bbox=dict(facecolor=BG, alpha=0.85, edgecolor='none', pad=1), zorder=8)

    # Draw both team networks
    _draw_vertical_network(axes[0], home_starters, home_lookup, h_color)
    _draw_vertical_network(axes[1], away_starters, away_lookup, a_color)
    
    # Add Team Logos and Names at the top (opponent box area inside 100x100 space)
    logo_h = _get_team_logo(summary.get("home_team_id"))
    if logo_h:
        axes[0].add_artist(AnnotationBbox(OffsetImage(logo_h.resize((50, 50))), (50, 85), frameon=False, zorder=10))
    axes[0].text(50, 94, summary.get('home_team', '').upper(), color=TEXT_MAIN, fontsize=14, fontweight='900', ha='center', va='center', zorder=10)
    
    logo_a = _get_team_logo(summary.get("away_team_id"))
    if logo_a:
        axes[1].add_artist(AnnotationBbox(OffsetImage(logo_a.resize((50, 50))), (50, 85), frameon=False, zorder=10))
    axes[1].text(50, 94, summary.get('away_team', '').upper(), color=TEXT_MAIN, fontsize=14, fontweight='900', ha='center', va='center', zorder=10)
    
    _add_team_legend(fig, summary, h_color, a_color, y_pos=0.03)
    return _encode(fig, save_path)

# Image 14: Cumulative xG Race
# Image 14: Attack Zones
def cumulative_xg_chart(summary: Dict, save_path=None) -> str:
    fig = plt.figure(figsize=(12, 8))
    fig.patch.set_facecolor(BG)
    _add_opta_header(fig, "Attack Zones", "Offensive Focus & Flank Penetration (%)")
    
    h_color = summary.get('home_color', HOME_CLR)
    a_color = summary.get('away_color', AWAY_CLR)
    
    # 1. Calculate actual attack side percentages from player heatmaps
    home_attack = {"left": 0, "center": 0, "right": 0}
    away_attack = {"left": 0, "center": 0, "right": 0}
    
    for p in summary.get('player_stats', []):
        team = p.get('team')
        pts = p.get('heatmap', [])
        if not pts: continue
        
        for pt in pts:
            x = pt.get('x', 50)
            y = pt.get('y', 50)
            
            # SofaScore normalized heatmaps: x > 50 is the attacking half
            if x > 50:
                if y < 33.3:
                    if team == 'home': home_attack["right"] += 1
                    else: away_attack["right"] += 1
                elif y < 66.6:
                    if team == 'home': home_attack["center"] += 1
                    else: away_attack["center"] += 1
                else:
                    if team == 'home': home_attack["left"] += 1
                    else: away_attack["left"] += 1
                    
    def _get_pcts(attack_dict):
        total = sum(attack_dict.values())
        if total > 0:
            return {
                "left": attack_dict["left"] / total * 100,
                "center": attack_dict["center"] / total * 100,
                "right": attack_dict["right"] / total * 100
            }
        return {"left": 35.0, "center": 30.0, "right": 35.0}
        
    h_pcts = _get_pcts(home_attack)
    a_pcts = _get_pcts(away_attack)
    
    # Draw side-by-side vertical half-pitches
    pitch = VerticalPitch(pitch_type='opta', pitch_color=BG, line_color=PITCH_LINE, linewidth=1.5, half=True)
    
    # Create axes raised up a lot (bottom coordinate changed from 0.15 to 0.28, height is 0.58)
    ax_h = fig.add_axes([0.08, 0.28, 0.40, 0.58])
    ax_a = fig.add_axes([0.52, 0.28, 0.40, 0.58])
    
    pitch.draw(ax=ax_h)
    pitch.draw(ax=ax_a)
    
    def _draw_team_zones(ax_obj, pcts, color):
        zones = [
            ("left", 0, 33.3, "LEFT FLANK"),
            ("center", 33.3, 66.6, "CENTER"),
            ("right", 66.6, 100, "RIGHT FLANK")
        ]
        
        max_side = max(pcts, key=pcts.get)
        
        for side, y_min, y_max, label in zones:
            pct = pcts[side]
            is_max = (side == max_side)
            
            # Opacity represents intensity of attack focus
            alpha = 0.35 if is_max else 0.16
            edgecolor = color if is_max else 'none'
            lw = 1.5 if is_max else 0
            
            # Rectangle: min_y, min_x, width_y, height_x
            rect = mpatches.Rectangle((y_min, 50), y_max - y_min, 50, facecolor=color, alpha=alpha, edgecolor=edgecolor, lw=lw, zorder=2)
            ax_obj.add_patch(rect)
            
            # Draw labels & percentages
            y_center = y_min + (y_max - y_min) / 2
            ax_obj.text(y_center, 78, f"{pct:.0f}%", color='#ffffff', fontsize=22, ha='center', va='center', fontweight='black', zorder=4)
            ax_obj.text(y_center, 68, label, color=TEXT_SEC, fontsize=9, ha='center', va='center', fontweight='bold', alpha=0.8, zorder=4)
            
    _draw_team_zones(ax_h, h_pcts, h_color)
    _draw_team_zones(ax_a, a_pcts, a_color)
    
    # 2. Draw team logos and names BELOW the raised pitches (untouched and clean)
    hl = _get_team_logo(summary.get("home_team_id"))
    al = _get_team_logo(summary.get("away_team_id"))
    
    h_mgr = summary.get("managers", {}).get("home", "Manager")
    a_mgr = summary.get("managers", {}).get("away", "Manager")
    
    h_team = summary.get("home_team", "Home")
    a_team = summary.get("away_team", "Away")
    
    # Home branding below pitch
    if hl:
        ax_logo_h = fig.add_axes([0.24, 0.16, 0.08, 0.08])
        ax_logo_h.imshow(hl.resize((60, 60)))
        ax_logo_h.axis('off')
    fig.text(0.28, 0.11, h_team.upper(), color=h_color, fontsize=14, ha='center', va='top', fontweight='black')
    fig.text(0.28, 0.075, f"Manager: {h_mgr}", color=TEXT_SEC, fontsize=9.5, ha='center', va='top', style='italic')
    
    # Away branding below pitch
    if al:
        ax_logo_a = fig.add_axes([0.68, 0.16, 0.08, 0.08])
        ax_logo_a.imshow(al.resize((60, 60)))
        ax_logo_a.axis('off')
    fig.text(0.72, 0.11, a_team.upper(), color=a_color, fontsize=14, ha='center', va='top', fontweight='black')
    fig.text(0.72, 0.075, f"Manager: {a_mgr}", color=TEXT_SEC, fontsize=9.5, ha='center', va='top', style='italic')
    
    return _encode(fig, save_path)

# Main Generator
def generate_all_graphics(summary: Dict, save_dir: str = None) -> Dict[str, str]:
    # Use default identity colors
    summary['home_color'] = MAIN_GREEN
    summary['away_color'] = GOLD

    if 'raw_shotmap' in summary:
        summary['raw_shotmap'] = [s for s in summary['raw_shotmap'] if s.get('situation') != 'shootout']

    funcs = {
        "1-Match_Overview": overview_map, 
        "2-Shot_Map": efficiency_chart, 
        "3-xG_Flow": xg_flow_chart,
        "4-Tactical_Formations": formation_graphic, 
        "5-Goalpost_Map": goal_post_map, 
        "6-Assist_Map": assist_map,
        "7-Struggling_Players": most_defensive_chart, 
        "8-Match_Performers": most_shots_chart, 
        "9-Momentum": momentum_chart,
        "10-Chances_and_Mistakes": big_chances_chart, 
        "11-Stars_of_the_Match": star_players_chart, 
        "12-Territory_Map": danger_chart,
        "13-Passing_Networks": buildup_chart, 
        "14-Attack_Zones": cumulative_xg_chart
    }
    plots = {}
    for k, f in funcs.items():
        path = os.path.join(save_dir, f"{k}.png") if save_dir else None
        try: 
            plots[k] = f(summary, save_path=path)
        except Exception as e: 
            logger.error(f"Error {k}: {e}")
            print(f"Error {k}: {e}")
    return plots