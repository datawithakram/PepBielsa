"""
Telegram inline keyboards for match selection and actions.
"""
from datetime import datetime, timezone
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Dict

# Competition emoji map (API-Football league IDs)
LEAGUE_EMOJI = {
    2:   "🏆",   # UCL
    3:   "🏅",   # UEL
    848: "🌍",   # UECL
    1:   "🌏",   # World Cup
    4:   "🇪🇺",   # Euros
    9:   "🇺🇦",   # Copa America
    39:  "🗣️",   # Premier League
    140: "🐂",   # La Liga
    135: "🐍",   # Serie A
    78:  "🐔",   # Bundesliga
    61:  "🐓",   # Ligue 1
    169: "🇸🇦",   # Saudi Pro League
}

def _match_time_str(fixture: Dict) -> str:
    """Return HH:MM UTC string from fixture timestamp."""
    ts = fixture.get("fixture", {}).get("timestamp")
    if ts:
        try:
            dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
            return dt.strftime("%H:%M")
        except Exception:
            pass
    return "--:--"


def matches_keyboard(fixtures: List[Dict]) -> InlineKeyboardMarkup:
    """Build inline keyboard grouped by competition, showing time + teams."""
    if not fixtures:
        return InlineKeyboardMarkup([[InlineKeyboardButton(
            "🕑 No major matches today", callback_data="none"
        )]])

    buttons = []
    current_league = None

    for f in fixtures:
        league_id   = f["league"]["id"]
        league_name = f["league"]["name"]
        home        = f["teams"]["home"]["name"]
        away        = f["teams"]["away"]["name"]
        match_id    = f["fixture"]["id"]
        kick_off    = _match_time_str(f)
        emoji       = LEAGUE_EMOJI.get(league_id, "⚽")

        # Insert a non-clickable league header when competition changes
        if league_id != current_league:
            current_league = league_id
            buttons.append([InlineKeyboardButton(
                f"{emoji} {league_name}",
                callback_data="none"
            )])

        buttons.append([InlineKeyboardButton(
            f"🕑 {kick_off} UTC  •  {home} vs {away}",
            callback_data=f"analyze_{match_id}"
        )])

    return InlineKeyboardMarkup(buttons)

def main_menu_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("📅 Today's Matches", callback_data="matches")],
        [InlineKeyboardButton("📰 News", callback_data="news")],
        [InlineKeyboardButton("📊 Daily Digest", callback_data="digest")],
        [InlineKeyboardButton("❓ Help", callback_data="help")]
    ]
    return InlineKeyboardMarkup(buttons)

def news_menu_keyboard() -> InlineKeyboardMarkup:
    """Sub-menu for news categories."""
    buttons = [
        [InlineKeyboardButton("⚽ Football News", callback_data="news_general")],
        [InlineKeyboardButton("🔄 Transfer News", callback_data="news_transfers")],
        [InlineKeyboardButton("🎙 Press Conferences", callback_data="news_press")],
        [InlineKeyboardButton("🏥 Injury Updates", callback_data="news_injuries")],
        [InlineKeyboardButton("🚨 Breaking News", callback_data="news_breaking")],
        [InlineKeyboardButton("↩️ Back", callback_data="start")],
    ]
    return InlineKeyboardMarkup(buttons)