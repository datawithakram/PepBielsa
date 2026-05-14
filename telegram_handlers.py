"""
Handlers for Telegram bot
"""
import os
import json
import time
import logging
import requests
from telegram import Update
from telegram.ext import ContextTypes

HF_SPACE_URL = os.getenv("HF_SPACE_URL", "https://thehnx-pepbielsa.hf.space")
logger = logging.getLogger(__name__)

from utils import get_today_matches, get_cache, set_cache
from keyboard import matches_keyboard, main_menu_keyboard

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
    try:
        fixtures = get_today_matches()
        if not fixtures:
            txt = "No matches today."
            if q: await q.edit_message_text(txt)
            else: await update.message.reply_text(txt)
            return
        if q:
            await q.edit_message_text("⚽ *Today's Matches*:", parse_mode="Markdown", reply_markup=matches_keyboard(fixtures))
        else:
            await update.message.reply_text("⚽ *Today's Matches*:", parse_mode="Markdown", reply_markup=matches_keyboard(fixtures))
    except Exception as e:
        err = f"Error: {e}"
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

async def show_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q: await q.answer()
    try:
        from news_engine import get_latest_news
        news = get_latest_news()
        if not news:
            txt = "No news available."
        else:
            txt = "📰 *Latest News*\n\n" + "\n".join([f"• {n['title']}" for n in news[:5]])
        if q: await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=main_menu_keyboard())
        else: await update.message.reply_text(txt, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    except Exception as e:
        err = f"News error: {e}"
        if q: await q.edit_message_text(err)
        else: await update.message.reply_text(err)

async def show_press(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q: await q.answer()
    try:
        from press_conference_analyzer import fetch_press_quotes, analyze_quotes
        quotes = fetch_press_quotes()
        analyzed = analyze_quotes(quotes)
        txt = "🎙 *Press Conference*\n\n" + "\n".join([f"*{a['coach']}*: _{a['quote']}_" for a in analyzed])
        if q: await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=main_menu_keyboard())
        else: await update.message.reply_text(txt, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    except Exception as e:
        err = f"Press error: {e}"
        if q: await q.edit_message_text(err)
        else: await update.message.reply_text(err)

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
    txt = "🤖 *PepBielsa*\n/matches - Today's games\n/news - Latest news\n/daily_digest - Daily briefing\n/help - Help"
    if update.message:
        await update.message.reply_text(txt, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    elif update.callback_query:
        q = update.callback_query
        await q.answer()
        await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=main_menu_keyboard())