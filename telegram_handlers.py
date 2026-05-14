"""
Telegram bot command and conversation handlers – integrate with HF Space API.
"""
import logging
import json
import requests
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from utils import get_today_matches, get_cache, set_cache
from keyboard import matches_keyboard, main_menu_keyboard
import os

HF_SPACE_URL = os.getenv("HF_SPACE_URL", "https://your-space.hf.space/run")  # update in .env or hardcode

logger = logging.getLogger(__name__)

# Conversation states
ASK_QUESTION = 1

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *AI Football Tactical Intelligence*\n"
        "Choose an option:",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )

async def show_matches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        fixtures = get_today_matches()
        if not fixtures:
            await query.edit_message_text("No matches today.")
            return
        await query.edit_message_text(
            "⚽ *Today's Matches*:",
            parse_mode="Markdown",
            reply_markup=matches_keyboard(fixtures)
        )
    except Exception as e:
        await query.edit_message_text(f"Error fetching matches: {e}")

async def analyze_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data  # e.g., analyze_12345
    match_id = data.split("_")[1]
    await query.edit_message_text("🔄 Analyzing match... This may take a minute.")
    # Call HF Space API
    try:
        resp = requests.post(
            HF_SPACE_URL,
            json={"match_id": int(match_id)},
            timeout=60
        )
        resp.raise_for_status()
        result = resp.json()
        report = result.get("report", "No report generated.")
        insights = result.get("insights", [])
        # Send report as text
        await query.message.reply_text(report[:4000], parse_mode="Markdown")
        # Send visuals (base64 images)
        if "images" in result:
            for img_type, b64 in result["images"].items():
                # Decode and send as photo
                from io import BytesIO
                import base64
                img_data = base64.b64decode(b64)
                await query.message.reply_photo(photo=BytesIO(img_data), caption=img_type)
        # Send social insights
        if insights:
            ins_text = "\n".join([f"• {s}" for s in insights])
            await query.message.reply_text(f"📱 *Social Insights:*\n{ins_text}", parse_mode="Markdown")
        # Store match context for follow-up Q&A
        set_cache(f"context_{update.effective_user.id}", {"match_id": match_id, "report": report})
        await query.message.reply_text(
            "💬 You can ask tactical follow-up questions about this match. Just type your question.",
            reply_markup=main_menu_keyboard()
        )
    except Exception as e:
        await query.message.reply_text(f"❌ Analysis failed: {e}")

async def handle_followup_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context_data = get_cache(f"context_{user_id}")
    if not context_data:
        await update.message.reply_text("Please analyze a match first (/matches).")
        return
    question = update.message.text
    # Call HF Space for Q&A
    try:
        resp = requests.post(
            HF_SPACE_URL,
            json={"question": question, "match_context": context_data},
            timeout=30
        )
        resp.raise_for_status()
        answer = resp.json().get("answer", "Sorry, I couldn't answer that.")
        await update.message.reply_text(answer, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Q&A failed: {e}")

async def show_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    from news_engine import get_latest_news
    news = get_latest_news()
    if not news:
        await query.edit_message_text("No news available.")
        return
    text = "\n\n".join([f"*{n['title']}*\n{n['tactical_implication']}" for n in news[:5]])
    await query.edit_message_text(f"📰 *Football News Intelligence*\n{text[:4000]}", parse_mode="Markdown", reply_markup=main_menu_keyboard())

async def show_press(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    from press_conference_analyzer import fetch_press_quotes, analyze_quotes
    quotes = fetch_press_quotes()
    analyzed = analyze_quotes(quotes)
    text = ""
    for a in analyzed:
        text += f"*{a['coach']} ({a['team']})*: _{a['quote']}_\n→ {a['tactical_implication']}\n\n"
    await query.edit_message_text(f"🎙 *Press Conference Intelligence*\n{text[:4000]}", parse_mode="Markdown", reply_markup=main_menu_keyboard())

async def daily_digest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    from daily_digest import create_daily_digest
    try:
        digest = create_daily_digest()
        await query.edit_message_text(digest[:4000], parse_mode="Markdown", reply_markup=main_menu_keyboard())
    except Exception as e:
        await query.edit_message_text(f"Digest failed: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Commands:\n/start - Main menu\n/matches - Today's matches\n/analyze - Select match to analyze\n/news - Football news\n/daily_digest - Daily briefing\n/help - This help\n\n"
        "You can also ask tactical follow-up questions after analyzing a match."
    )