"""
Telegram bot command and conversation handlers – integrate with HF Space API.
"""
import logging
import json
import requests
from telegram import Update
from telegram.ext import ContextTypes
from utils import get_today_matches, get_cache, set_cache
from keyboard import matches_keyboard, main_menu_keyboard
import os

HF_SPACE_URL = os.getenv("HF_SPACE_URL", "https://thehnx-pepbielsa.hf.space")

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message with main menu."""
    if update.message:
        await update.message.reply_text(
            "🤖 *AI Football Tactical Intelligence*\n"
            "Choose an option:",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
    elif update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            "🤖 *AI Football Tactical Intelligence*\n"
            "Choose an option:",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )

async def show_matches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display today's matches."""
    query = update.callback_query
    if query:
        await query.answer()
    
    try:
        fixtures = get_today_matches()
        if not fixtures:
            text = "No matches today."
            if query:
                await query.edit_message_text(text)
            else:
                await update.message.reply_text(text)
            return
        
        if query:
            await query.edit_message_text(
                "⚽ *Today's Matches*:",
                parse_mode="Markdown",
                reply_markup=matches_keyboard(fixtures)
            )
        else:
            await update.message.reply_text(
                "⚽ *Today's Matches*:",
                parse_mode="Markdown",
                reply_markup=matches_keyboard(fixtures)
            )
    except Exception as e:
        error_text = f"Error fetching matches: {e}"
        if query:
            await query.edit_message_text(error_text)
        else:
            await update.message.reply_text(error_text)

async def analyze_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Analyze selected match via HF Space."""
    query = update.callback_query
    await query.answer()
    data = query.data
    match_id = data.split("_")[1]
    await query.edit_message_text("🔄 Analyzing match... This may take a minute.")
    
    try:
        # المسار الصحيح لـ Gradio 4+
        api_url = f"{HF_SPACE_URL}/gradio_api/call/run_tactical_analysis"
        
        # إرسال الطلب
        resp = requests.post(
            api_url,
            json={"data": [int(match_id), None, None, None]},
            timeout=120
        )
        
        if resp.status_code != 200:
            await query.message.reply_text(f"❌ API Error: {resp.status_code}")
            return
        
        # Gradio 4+ يرجع event_id
        result_data = resp.json()
        event_id = result_data.get("event_id")
        
        if event_id:
            # انتظر قليلاً ثم اجلب النتيجة
            import time
            time.sleep(5)
            
            result_resp = requests.get(
                f"{api_url}/{event_id}",
                timeout=120
            )
            
            if result_resp.status_code == 200:
                # النتيجة جاهزة
                final_result = result_resp.text
                
                # إرسال النتيجة للمستخدم
                if len(final_result) > 4000:
                    # تقسيم الرسائل الطويلة
                    for i in range(0, len(final_result), 4000):
                        await query.message.reply_text(
                            final_result[i:i+4000],
                            parse_mode="HTML"
                        )
                else:
                    await query.message.reply_text(final_result[:4000], parse_mode="HTML")
                
                # تخزين السياق للأسئلة المتابعة
                set_cache(f"context_{update.effective_user.id}", {
                    "match_id": match_id,
                    "analysis": "Match analyzed"
                })
                
                await query.message.reply_text(
                    "💬 You can ask tactical follow-up questions about this match. Just type your question.",
                    reply_markup=main_menu_keyboard()
                )
            else:
                await query.message.reply_text("❌ Analysis result not ready. Please try again.")
        else:
            # ربما النتيجة مباشرة
            await query.message.reply_text(str(result_data)[:4000])
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error: {e}")
        await query.message.reply_text(f"❌ Network error: {str(e)[:200]}")
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")
        await query.message.reply_text(f"❌ Analysis failed: {str(e)[:200]}")

async def handle_followup_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user's tactical follow-up questions."""
    if not update.message or not update.message.text:
        return
        
    user_id = update.effective_user.id
    context_data = get_cache(f"context_{user_id}")
    if not context_data:
        await update.message.reply_text(
            "Please analyze a match first. Use /matches to start.",
            reply_markup=main_menu_keyboard()
        )
        return
    
    question = update.message.text
    
    try:
        api_url = f"{HF_SPACE_URL}/gradio_api/call/run_tactical_analysis"
        resp = requests.post(
            api_url,
            json={"data": [0, None, question, context_data]},
            timeout=60
        )
        
        if resp.status_code == 200:
            result_data = resp.json()
            event_id = result_data.get("event_id")
            if event_id:
                import time
                time.sleep(3)
                result_resp = requests.get(f"{api_url}/{event_id}", timeout=60)
                answer = result_resp.text[:4000]
                await update.message.reply_text(answer, parse_mode="HTML")
                return
        
        await update.message.reply_text(
            "I couldn't process your question. Please try analyzing a match first.",
            reply_markup=main_menu_keyboard()
        )
    except Exception as e:
        logger.error(f"Q&A failed: {e}")
        await update.message.reply_text(
            "Q&A service unavailable. Please try again later.",
            reply_markup=main_menu_keyboard()
        )

async def show_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show latest football news."""
    query = update.callback_query
    if query:
        await query.answer()
    
    try:
        from news_engine import get_latest_news
        news = get_latest_news()
        if not news:
            text = "📰 No news available at the moment."
        else:
            text = "📰 *Football News Intelligence*\n\n"
            for n in news[:5]:
                text += f"• *{n['title']}*\n"
        
        if query:
            await query.edit_message_text(text[:4000], parse_mode="Markdown", reply_markup=main_menu_keyboard())
        else:
            await update.message.reply_text(text[:4000], parse_mode="Markdown", reply_markup=main_menu_keyboard())
    except Exception as e:
        error_text = f"❌ News unavailable: {str(e)[:200]}"
        if query:
            await query.edit_message_text(error_text)
        else:
            await update.message.reply_text(error_text)

async def show_press(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show press conference intelligence."""
    query = update.callback_query
    if query:
        await query.answer()
    
    try:
        from press_conference_analyzer import fetch_press_quotes, analyze_quotes
        quotes = fetch_press_quotes()
        analyzed = analyze_quotes(quotes)
        text = "🎙 *Press Conference Intelligence*\n\n"
        for a in analyzed:
            text += f"*{a['coach']}*: _{a['quote']}_\n\n"
        
        if query:
            await query.edit_message_text(text[:4000], parse_mode="Markdown", reply_markup=main_menu_keyboard())
        else:
            await update.message.reply_text(text[:4000], parse_mode="Markdown", reply_markup=main_menu_keyboard())
    except Exception as e:
        error_text = f"❌ Press analysis unavailable: {str(e)[:200]}"
        if query:
            await query.edit_message_text(error_text)
        else:
            await update.message.reply_text(error_text)

async def daily_digest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show daily football intelligence digest."""
    query = update.callback_query
    if query:
        await query.answer()
    
    try:
        from daily_digest import create_daily_digest
        digest = create_daily_digest()
        
        if query:
            await query.edit_message_text(digest[:4000], parse_mode="Markdown", reply_markup=main_menu_keyboard())
        else:
            await update.message.reply_text(digest[:4000], parse_mode="Markdown", reply_markup=main_menu_keyboard())
    except Exception as e:
        error_text = f"❌ Digest generation failed: {str(e)[:200]}"
        if query:
            await query.edit_message_text(error_text)
        else:
            await update.message.reply_text(error_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help message."""
    help_text = (
        "🤖 *PepBielsa - AI Football Tactical Intelligence*\n\n"
        "*Commands:*\n"
        "/start - Main menu\n"
        "/matches - Today's matches\n"
        "/news - Football news\n"
        "/daily_digest - Daily briefing\n"
        "/help - This help\n\n"
        "*How to use:*\n"
        "1. Use /matches to see today's games\n"
        "2. Select a match for analysis\n"
        "3. Ask follow-up questions after analysis"
    )
    
    if update.message:
        await update.message.reply_text(help_text, parse_mode="Markdown")
    elif update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(help_text, parse_mode="Markdown", reply_markup=main_menu_keyboard())