"""
Daily Football Intelligence Digest – combines fixtures, news,
and tactical predictions into a morning briefing.
"""
from typing import List, Dict
from utils import get_today_matches
from news_engine import get_latest_news
from ai_analysis import generate_daily_briefing

def create_daily_digest() -> str:
    """Fetch today's matches and news, generate briefing."""
    # Today's matches from API
    fixtures_raw = get_today_matches()
    matches = []
    for f in fixtures_raw:
        matches.append({
            "home": f["teams"]["home"]["name"],
            "away": f["teams"]["away"]["name"],
            "league": f["league"]["name"],
            "time": f["fixture"]["date"]
        })
    # Latest news
    news_items = get_latest_news()
    news_titles = [n["title"] for n in news_items[:10]]
    # Generate briefing via Groq
    return generate_daily_briefing(matches, news_titles)