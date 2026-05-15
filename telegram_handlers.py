"""
Handlers for Telegram bot
"""
import os
import json
import time
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import TelegramError

HF_SPACE_URL = os.getenv("HF_SPACE_URL", "https://thehnx-pepbielsa.hf.space")
logger = logging.getLogger(__name__)

from utils import get_today_matches, get_cache, set_cache
from keyboard import matches_keyboard, main_menu_keyboard, news_menu_keyboard
from feed_fetcher import fetch_category
from news_store import store

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(
            "🤖 *PepBielsa - AI Tactical Intelligence*\nSelect an option:",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
    elif update.callback_query:
        q = update.callback_query
        await q.answer()
        await q.edit_message_text(
            "🤖 *PepBielsa - AI Tactical Intelligence*\nSelect an option:",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )

async def show_matches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q: await q.answer()

    from datetime import date
    today_str = date.today().strftime("%d %b %Y")

    try:
        fixtures = get_today_matches(major_only=True)
        count    = len(fixtures)

        if not fixtures:
            txt = (
                f"📅 *{today_str}*\n\n"
                "⏳ No major matches today in the top competitions.\n"
                "Use /matches\\_all to see all leagues."
            )
            if q: await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=main_menu_keyboard())
            else: await update.message.reply_text(txt, parse_mode="Markdown", reply_markup=main_menu_keyboard())
            return

        header = (
            f"📅 *{today_str} — Major Matches*\n"
            f"🏆 {count} match{'es' if count != 1 else ''} across top competitions\n"
            "_Tap a match to get the full tactical analysis_"
        )
        if q:
            await q.edit_message_text(header, parse_mode="Markdown", reply_markup=matches_keyboard(fixtures))
        else:
            await update.message.reply_text(header, parse_mode="Markdown", reply_markup=matches_keyboard(fixtures))

    except Exception as e:
        err = f"❌ Error fetching matches: {e}"
        if q: await q.edit_message_text(err)
        else: await update.message.reply_text(err)


async def show_all_matches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show ALL today's matches without the major-league filter."""
    q = update.callback_query
    if q: await q.answer()

    from datetime import date
    today_str = date.today().strftime("%d %b %Y")

    try:
        fixtures = get_today_matches(major_only=False)
        count    = len(fixtures)

        if not fixtures:
            txt = f"📅 *{today_str}*\n\nNo matches found at all today."
            if q: await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=main_menu_keyboard())
            else: await update.message.reply_text(txt, parse_mode="Markdown", reply_markup=main_menu_keyboard())
            return

        header = (
            f"📅 *{today_str} — All Matches*\n"
            f"⚽ {count} matches (all leagues)\n"
            "_Tap a match to analyse it_"
        )
        if q:
            await q.edit_message_text(header, parse_mode="Markdown", reply_markup=matches_keyboard(fixtures))
        else:
            await update.message.reply_text(header, parse_mode="Markdown", reply_markup=matches_keyboard(fixtures))

    except Exception as e:
        err = f"❌ Error: {e}"
        if q: await q.edit_message_text(err)
        else: await update.message.reply_text(err)

async def analyze_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    match_id = q.data.split("_")[1]
    await q.edit_message_text("🔄 Analyzing... (may take 30-60s for cold start)")
    
    try:
        api_url = f"{HF_SPACE_URL}/gradio_api/call/run_tactical_analysis"
        resp = requests.post(api_url, json={"data": [int(match_id), None, None, None]}, timeout=180)
        
        if resp.status_code != 200:
            await q.message.reply_text(f"❌ API Error {resp.status_code}")
            return
        
        data = resp.json()
        event_id = data.get("event_id")
        
        if event_id:
            time.sleep(3)
            # Poll for result
            for _ in range(20):
                r2 = requests.get(f"{api_url}/{event_id}", timeout=60)
                if r2.status_code == 200:
                    result = r2.text
                    if len(result) > 4000:
                        for i in range(0, len(result), 4000):
                            await q.message.reply_text(result[i:i+4000], parse_mode="HTML")
                    else:
                        await q.message.reply_text(result, parse_mode="HTML")
                    
                    set_cache(f"ctx_{update.effective_user.id}", json.dumps({"match_id": match_id}))
                    await q.message.reply_text("💬 Ask follow-up questions!", reply_markup=main_menu_keyboard())
                    return
                time.sleep(2)
        
        await q.message.reply_text("❌ Analysis timed out. Try again.")
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        await q.message.reply_text(f"❌ Error: {str(e)[:200]}")

async def handle_followup_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    ctx = get_cache(f"ctx_{update.effective_user.id}")
    if not ctx:
        await update.message.reply_text("Analyze a match first (/matches)", reply_markup=main_menu_keyboard())
        return
    
    await update.message.reply_text("🤔 Thinking...")
    try:
        api_url = f"{HF_SPACE_URL}/gradio_api/call/run_tactical_analysis"
        resp = requests.post(api_url, json={"data": [0, None, update.message.text, ctx]}, timeout=120)
        
        if resp.status_code == 200:
            data = resp.json()
            eid = data.get("event_id")
            if eid:
                time.sleep(2)
                r2 = requests.get(f"{api_url}/{eid}", timeout=60)
                if r2.status_code == 200:
                    await update.message.reply_text(r2.text[:4000], parse_mode="HTML")
                    return
        await update.message.reply_text("Could not process question.")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

# ── shared helper ────────────────────────────────────────────────────────────

async def _send_news_card(bot, chat_id: int, item: dict, category: str):
    """Send a single news card (photo + caption or text fallback)."""
    from news_scheduler import _format_caption
    caption = _format_caption(item, category)
    image_url = item.get("image")
    try:
        if image_url:
            await bot.send_photo(
                chat_id=chat_id,
                photo=image_url,
                caption=caption,
                parse_mode="Markdown",
            )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text=caption,
                parse_mode="Markdown",
                disable_web_page_preview=False,
            )
    except TelegramError:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=caption,
                parse_mode="Markdown",
                disable_web_page_preview=False,
            )
        except TelegramError as e:
            logger.error(f"Card send failed: {e}")


async def show_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show news category menu."""
    q = update.callback_query
    if q:
        await q.answer()
        await q.edit_message_text(
            "📰 *Choose a news category:*",
            parse_mode="Markdown",
            reply_markup=news_menu_keyboard(),
        )
    else:
        await update.message.reply_text(
            "📰 *Choose a news category:*",
            parse_mode="Markdown",
            reply_markup=news_menu_keyboard(),
        )


async def _handle_news_category(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str, label: str):
    """Fetch and send news items for a given category."""
    q = update.callback_query
    chat_id = update.effective_chat.id
    bot = context.bot

    if q:
        await q.answer()
        await q.edit_message_text(f"⏳ Fetching {label}…")

    items = fetch_category(category, max_per_feed=5)
    if not items:
        txt = f"No {label} found right now. Try again later."
        await bot.send_message(chat_id=chat_id, text=txt, reply_markup=main_menu_keyboard())
        return

    await bot.send_message(
        chat_id=chat_id,
        text=f"📋 *Latest {label}* — top {min(len(items), 5)} articles:",
        parse_mode="Markdown",
    )
    for item in items[:5]:
        await _send_news_card(bot, chat_id, item, category)

    await bot.send_message(
        chat_id=chat_id,
        text="↩️ Back to menu:",
        reply_markup=main_menu_keyboard(),
    )


async def show_general_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _handle_news_category(update, context, "general", "Football News")


async def show_transfers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _handle_news_category(update, context, "transfers", "Transfer News")


async def show_press(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _handle_news_category(update, context, "press_conference", "Press Conferences")


async def show_injuries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _handle_news_category(update, context, "injuries", "Injury News")


async def show_breaking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _handle_news_category(update, context, "breaking", "Breaking News")


async def admin_reset_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: /reset_news — clears the dedup store."""
    admin_id = os.getenv("ADMIN_CHAT_ID", "")
    uid = str(update.effective_user.id)
    if admin_id and uid != admin_id:
        await update.message.reply_text("⛔ Not authorised.")
        return
    store.reset()
    await update.message.reply_text("✅ News dedup store cleared. All articles are now 'new' again.")

async def daily_digest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q: await q.answer()
    try:
        from daily_digest import create_daily_digest
        digest = create_daily_digest()
        if q: await q.edit_message_text(digest[:4000], parse_mode="Markdown", reply_markup=main_menu_keyboard())
        else: await update.message.reply_text(digest[:4000], parse_mode="Markdown", reply_markup=main_menu_keyboard())
    except Exception as e:
        err = f"Digest error: {e}"
        if q: await q.edit_message_text(err)
        else: await update.message.reply_text(err)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = (
        "🤖 *PepBielsa — Football Intelligence*\n\n"
        "*📅 Matches*\n"
        "/matches — Major competitions only\n"
        "/matches\\_all — All leagues today\n\n"
        "*📰 News Feed*\n"
        "/news — News category menu\n"
        "/transfers — Transfer news\n"
        "/injuries — Injury updates\n"
        "/breaking — Breaking news\n"
        "/press — Press conferences\n\n"
        "*📊 Digest*\n"
        "/daily\\_digest — Daily briefing\n\n"
        "*⚙️ Admin*\n"
        "/reset\\_news — Clear news dedup store\n"
        "/help — This message"
    )
    if update.message:
        await update.message.reply_text(txt, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    elif update.callback_query:
        q = update.callback_query
        await q.answer()
        await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=main_menu_keyboard())