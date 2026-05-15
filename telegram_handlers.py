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
    await q.edit_message_text("🔄 Analyzing... (Fetching match data & generating AI report)")
    
    try:
        from utils import get_match_by_id, get_match_statistics, get_match_events, get_lineups
        from tactical_engine import compute_tactical_summary
        from ai_analysis import generate_tactical_report, generate_social_insights
        from visuals import generate_all_graphics
        import base64
        from io import BytesIO
        
        # 1. Fetch data
        match = get_match_by_id(int(match_id))
        if not match:
            await q.message.reply_text(f"❌ Match {match_id} not found.")
            return
            
        stats = get_match_statistics(int(match_id))
        events = get_match_events(int(match_id))
        lineups = get_lineups(int(match_id))
        
        # 2. Compute tactical summary
        summary = compute_tactical_summary(match, stats, events, lineups)
        
        # 3. AI Report
        report = generate_tactical_report(summary)
        
        # 4. Social insights
        try:
            insights = generate_social_insights(summary)
        except:
            insights = []
            
        # 5. Format the text for Telegram
        home = summary['home_team']
        away = summary['away_team']
        hs = summary['home_score']
        as_ = summary['away_score']
        
        text_message = f"⚽ *{home} {hs} - {as_} {away}*\n\n"
        text_message += f"📊 *Tactical Report*\n{report}\n\n"
        
        if insights:
            text_message += f"📱 *Social Insights*\n"
            for ins in insights:
                text_message += f"• {ins}\n"
                
        # Send text in chunks if it exceeds Telegram limits
        if len(text_message) > 4000:
            for i in range(0, len(text_message), 4000):
                await q.message.reply_text(text_message[i:i+4000], parse_mode="Markdown")
        else:
            await q.message.reply_text(text_message, parse_mode="Markdown")

        # 6. Generate and send graphics
        graphics = generate_all_graphics(summary, lineups, events=events)
        for name, b64 in graphics.items():
            try:
                photo_data = BytesIO(base64.b64decode(b64))
                await context.bot.send_photo(chat_id=update.effective_chat.id, photo=photo_data)
            except Exception as e:
                logger.error(f"Failed to send graphic {name}: {e}")

        # Store context for follow-ups
        set_cache(f"ctx_{update.effective_user.id}", json.dumps(summary))
        await q.message.reply_text("💬 Ask a follow-up question!", reply_markup=main_menu_keyboard())

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
        from ai_analysis import answer_followup
        
        ctx_data = json.loads(ctx)
        answer = answer_followup(update.message.text, ctx_data)
        
        await update.message.reply_text(f"💬 *Answer:*\n{answer}", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Followup failed: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)[:200]}")

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