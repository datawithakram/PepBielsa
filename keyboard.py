"""
Telegram inline keyboards for match selection and actions.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Dict

def matches_keyboard(fixtures: List[Dict]) -> InlineKeyboardMarkup:
    """Create inline keyboard with today's matches."""
    buttons = []
    for f in fixtures:
        home = f["teams"]["home"]["name"]
        away = f["teams"]["away"]["name"]
        match_id = f["fixture"]["id"]
        buttons.append([InlineKeyboardButton(
            f"⚽ {home} vs {away}",
            callback_data=f"analyze_{match_id}"
        )])
    if not buttons:
        buttons.append([InlineKeyboardButton("No matches today", callback_data="none")])
    return InlineKeyboardMarkup(buttons)

def main_menu_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("📅 Today's Matches", callback_data="matches")],
        [InlineKeyboardButton("📰 Latest News", callback_data="news")],
        [InlineKeyboardButton("📊 Daily Digest", callback_data="digest")],
        [InlineKeyboardButton("🎙 Press Conferences", callback_data="press")],
        [InlineKeyboardButton("❓ Help", callback_data="help")]
    ]
    return InlineKeyboardMarkup(buttons)