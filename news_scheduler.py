"""
news_scheduler.py
Scheduled polling of football news feeds + Telegram dispatch.
Uses python-telegram-bot's built-in JobQueue (APScheduler under the hood).
No heavy dependencies — free-tier optimised.

Jobs registered:
  • fetch_and_send_news  – runs every POLL_INTERVAL_MINUTES (default 30)
  • breaking_news_check  – runs every BREAKING_INTERVAL_MINUTES (default 10)
"""
import logging
import os
import html
from typing import List, Optional

from telegram import Bot
from telegram.error import TelegramError

from feed_fetcher import fetch_all, fetch_breaking_alerts
from news_store import store

logger = logging.getLogger(__name__)

# ── config (override via environment) ────────────────────────────────────────
POLL_INTERVAL_MINUTES    = int(os.getenv("NEWS_POLL_MINUTES", 30))
BREAKING_INTERVAL_MINUTES = int(os.getenv("BREAKING_POLL_MINUTES", 10))
MAX_ITEMS_PER_CATEGORY   = int(os.getenv("NEWS_MAX_PER_CAT", 3))
MAX_BREAKING_ITEMS       = int(os.getenv("NEWS_MAX_BREAKING", 5))

CATEGORY_EMOJIS = {
    "general":          "⚽",
    "transfers":        "🔄",
    "press_conference": "🎙",
    "injuries":         "🏥",
    "breaking":         "🚨",
}

CATEGORY_LABELS = {
    "general":          "Football News",
    "transfers":        "Transfer News",
    "press_conference": "Press Conference",
    "injuries":         "Injury Update",
    "breaking":         "Breaking News",
}


# ── formatting helpers ────────────────────────────────────────────────────────

def _format_caption(item: dict, category: str) -> str:
    """
    Build the Telegram message text for one news item.
    Format:
      🚨 BREAKING NEWS
      📰 Title of the article

      🗞 Source  •  🕐 12:30 UTC
      🔗 Read more
    """
    emoji = CATEGORY_EMOJIS.get(category, "📰")
    label = CATEGORY_LABELS.get(category, category.replace("_", " ").title())

    # Human-readable time
    published_str = item.get("published", "")
    time_display = ""
    if published_str:
        try:
            from datetime import datetime, timezone
            dt = datetime.fromisoformat(published_str)
            time_display = dt.strftime("%d %b %H:%M UTC")
        except Exception:
            time_display = published_str[:16]

    title  = html.escape(item.get("title", "No title"))
    source = html.escape(item.get("source", "Unknown"))
    link   = item.get("link", "")

    lines = [
        f"{emoji} <b>{label}</b>",
        f"",
        f"📰 {title}",
        f"",
        f"🗞 {source}",
    ]
    if time_display:
        lines.append(f"🕐 {time_display}")
    if link:
        lines.append(f"🔗 <a href='{link}'>Read more</a>")

    return "\n".join(lines)


async def _send_item(bot: Bot, chat_id: int, item: dict, category: str):
    """Send a single news item to a Telegram chat (with or without image)."""
    caption = _format_caption(item, category)
    image_url = item.get("image")

    try:
        if image_url:
            await bot.send_photo(
                chat_id=chat_id,
                photo=image_url,
                caption=caption,
                parse_mode="HTML",
            )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text=caption,
                parse_mode="HTML",
                disable_web_page_preview=False,
            )
    except TelegramError as e:
        logger.warning(f"Telegram send failed (retrying without image): {e}")
        # Fallback: send text only
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=caption,
                parse_mode="HTML",
                disable_web_page_preview=False,
            )
        except TelegramError as e2:
            logger.error(f"Text fallback also failed: {e2}")


def _get_subscriber_chat_ids() -> List[int]:
    """
    Return the list of chat IDs that should receive news broadcasts.
    Primary: NEWS_CHANNEL_ID env var (a channel or group).
    Fallback: ADMIN_CHAT_ID (for personal testing).
    """
    ids = []
    channel = os.getenv("NEWS_CHANNEL_ID", "").strip()
    admin   = os.getenv("ADMIN_CHAT_ID", "").strip()

    if channel:
        try:
            ids.append(int(channel))
        except ValueError:
            ids.append(channel)  # string username like @mychannel

    if admin and admin not in [str(i) for i in ids]:
        try:
            ids.append(int(admin))
        except ValueError:
            pass

    return ids


# ── scheduled job callbacks ───────────────────────────────────────────────────

async def job_fetch_and_send_news(context):
    """
    APScheduler job: fetch all categories, filter duplicates, push to Telegram.
    Triggered every POLL_INTERVAL_MINUTES minutes.
    """
    bot: Bot = context.bot
    chat_ids = _get_subscriber_chat_ids()
    if not chat_ids:
        logger.info("No subscriber chat IDs configured — skipping news broadcast.")
        return

    logger.info("⏰ Running scheduled news fetch …")
    all_news = fetch_all(max_per_feed=MAX_ITEMS_PER_CATEGORY)

    for category, items in all_news.items():
        # Skip breaking here — handled by the faster job
        if category == "breaking":
            continue

        new_items = store.filter_new(items)
        if not new_items:
            continue

        for item in new_items[:MAX_ITEMS_PER_CATEGORY]:
            for cid in chat_ids:
                await _send_item(bot, cid, item, category)

    logger.info(f"✅ News fetch complete. Store size: {store.size()}")


async def job_breaking_news_check(context):
    """
    APScheduler job: fast-path check for breaking news keywords.
    Triggered every BREAKING_INTERVAL_MINUTES minutes.
    """
    bot: Bot = context.bot
    chat_ids = _get_subscriber_chat_ids()
    if not chat_ids:
        return

    logger.info("🚨 Checking for breaking news …")
    breaking_items = fetch_breaking_alerts(max_per_feed=10)
    new_breaking = store.filter_new(breaking_items)

    for item in new_breaking[:MAX_BREAKING_ITEMS]:
        for cid in chat_ids:
            await _send_item(bot, cid, item, "breaking")

    if new_breaking:
        logger.info(f"🚨 Sent {len(new_breaking)} breaking news item(s).")


# ── registration helper ───────────────────────────────────────────────────────

def register_jobs(app):
    """
    Register all scheduler jobs onto a python-telegram-bot Application.
    Call this once during bot startup.
    """
    jq = app.job_queue
    if jq is None:
        logger.error("JobQueue is None — install python-telegram-bot[job-queue]")
        return

    # Regular news: every POLL_INTERVAL_MINUTES, first run after 60s
    jq.run_repeating(
        job_fetch_and_send_news,
        interval=POLL_INTERVAL_MINUTES * 60,
        first=60,
        name="news_feed",
    )

    # Breaking news: every BREAKING_INTERVAL_MINUTES, first run after 30s
    jq.run_repeating(
        job_breaking_news_check,
        interval=BREAKING_INTERVAL_MINUTES * 60,
        first=30,
        name="breaking_news",
    )

    logger.info(
        f"✅ Jobs registered — news every {POLL_INTERVAL_MINUTES}m, "
        f"breaking every {BREAKING_INTERVAL_MINUTES}m"
    )
