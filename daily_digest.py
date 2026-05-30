"""
daily_digest.py — Daily Football Intelligence Briefing
Combines today's SofaScore fixtures and live news into a morning briefing
sent automatically every day via the scheduled job system.
"""
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


def create_daily_digest() -> str:
    """
    Fetch today's major matches (via SofaScore) and latest news headlines,
    then format them as a clean Telegram-ready briefing message.
    Returns an HTML-formatted string for Telegram send_message.
    """
    # ── 1. Fetch Today's Matches ──────────────────────────────────────────────
    matches: List[Dict] = []
    try:
        from data_aggregator import aggregator
        fixtures = aggregator.get_daily_fixtures(major_only=True)
        for f in fixtures:
            home = f.get("home_team", "Home")
            away = f.get("away_team", "Away")
            league = f.get("league", "")
            time_str = f.get("time", "")
            status = f.get("status", "")
            matches.append({
                "home": home,
                "away": away,
                "league": league,
                "time": time_str,
                "status": status,
            })
    except Exception as e:
        logger.warning(f"[Digest] Could not fetch fixtures: {e}")

    # ── 2. Fetch Latest News Headlines ───────────────────────────────────────
    news_titles: List[str] = []
    try:
        from feed_fetcher import fetch_all
        all_news = fetch_all(max_per_feed=2)
        for category, items in all_news.items():
            for item in items[:2]:
                title = item.get("title", "")
                if title:
                    news_titles.append(title)
    except Exception as e:
        logger.warning(f"[Digest] Could not fetch news: {e}")

    # ── 3. Build the message ──────────────────────────────────────────────────
    lines = ["⚽ <b>PepBielsa Daily Digest</b>\n"]

    if matches:
        lines.append("🏟 <b>Today's Major Matches</b>")
        for m in matches[:8]:
            status_icon = "🟢" if m["status"] in ("inprogress", "live") else "🔜"
            time_part = f"  <code>{m['time']}</code>" if m["time"] else ""
            lines.append(
                f"{status_icon} <b>{m['home']}</b> vs <b>{m['away']}</b>"
                f"{time_part}  — {m['league']}"
            )
    else:
        lines.append("📅 No major matches scheduled today.")

    if news_titles:
        lines.append("\n📰 <b>Latest Headlines</b>")
        for title in news_titles[:6]:
            import html as html_lib
            lines.append(f"• {html_lib.escape(title)}")

    lines.append("\n<i>Powered by PepBielsa AI · SofaScore Data</i>")
    return "\n".join(lines)


def get_digest_text() -> str:
    """Alias kept for backward compatibility."""
    return create_daily_digest()