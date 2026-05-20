"""
Telegram inline keyboards for match selection and actions. (Arabic Edition)
"""
from datetime import datetime, timezone
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Dict

# Competition emoji map (SofaScore league IDs)
LEAGUE_EMOJI = {
    1:   "🗣️",   # Premier League
    17:  "🐂",   # La Liga
    8:   "🐍",   # Serie A
    23:  "🐔",   # Bundesliga
    34:  "🐓",   # Ligue 1
    35:  "🇸🇦",   # Saudi Pro League
    7:   "🏆",   # Champions League
    679: "🏅",   # Europa League
}

def _match_status_str(f: Dict) -> str:
    """Return status string: Result if finished, Time if upcoming, 'Live' if active."""
    status_type = f.get("fixture", {}).get("status_type")
    home_score = f.get("goals", {}).get("home", 0)
    away_score = f.get("goals", {}).get("away", 0)
    
    if status_type == "finished":
        return f"{home_score} - {away_score} (FT)"
    elif status_type == "inprogress":
        return f"{home_score} - {away_score} (LIVE)"
    else:
        ts = f.get("fixture", {}).get("timestamp")
        if ts:
            dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
            return dt.strftime("%H:%M") + " UTC"
    return "Upcoming"


def matches_keyboard(fixtures: List[Dict], current_date: str = None) -> InlineKeyboardMarkup:
    """Build inline keyboard grouped by competition, showing time/result + teams."""
    if not current_date:
        current_date = datetime.now().strftime("%Y-%m-%d")
    
    # Date navigation
    from datetime import timedelta
    dt = datetime.strptime(current_date, "%Y-%m-%d")
    prev_date = (dt - timedelta(days=1)).strftime("%Y-%m-%d")
    next_date = (dt + timedelta(days=1)).strftime("%Y-%m-%d")

    buttons = []
    
    # Navigation row
    buttons.append([
        InlineKeyboardButton("◀️ Yesterday", callback_data=f"date_{prev_date}"),
        InlineKeyboardButton("📅 Today", callback_data=f"date_{datetime.now().strftime('%Y-%m-%d')}"),
        InlineKeyboardButton("Tomorrow ▶️", callback_data=f"date_{next_date}")
    ])

    if not fixtures:
        buttons.append([InlineKeyboardButton(
            "📅 No major matches on this date", callback_data="none"
        )])
    else:
        current_league = None
        for f in fixtures:
            league_id   = f["league"]["id"]
            league_name = f["league"]["name"]
            home        = f["teams"]["home"]["name"]
            away        = f["teams"]["away"]["name"]
            match_id    = f["fixture"]["id"]
            status_str  = _match_status_str(f)
            emoji       = LEAGUE_EMOJI.get(league_id, "⚽")

            if league_id != current_league:
                current_league = league_id
                buttons.append([InlineKeyboardButton(
                    f"{emoji} {league_name}",
                    callback_data="none"
                )])

            buttons.append([InlineKeyboardButton(
                f"● {status_str} | {home} - {away}",
                callback_data=f"analyze_{match_id}"
            )])

    buttons.append([InlineKeyboardButton("↩️ Back to Main Menu", callback_data="start")])
    return InlineKeyboardMarkup(buttons)

def main_menu_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("📅 Today's Matches", callback_data="matches")],
        [InlineKeyboardButton("📰 Football News", callback_data="news")],
        [InlineKeyboardButton("🎨 Custom Tactical Chart", callback_data="cust_home")],
        [InlineKeyboardButton("❓ Help", callback_data="help")]
    ]
    return InlineKeyboardMarkup(buttons)

def news_menu_keyboard() -> InlineKeyboardMarkup:
    """Sub-menu for news categories."""
    buttons = [
        [InlineKeyboardButton("⚽ General News", callback_data="news_general")],
        [InlineKeyboardButton("🔄 Transfers", callback_data="news_transfers")],
        [InlineKeyboardButton("🎙 Press Conferences", callback_data="news_press")],
        [InlineKeyboardButton("🏥 Injuries", callback_data="news_injuries")],
        [InlineKeyboardButton("🚨 Breaking News", callback_data="news_breaking")],
        [InlineKeyboardButton("↩️ Back", callback_data="start")],
    ]
    return InlineKeyboardMarkup(buttons)