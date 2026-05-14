"""
Telegram Bot for PepBielsa - Runs on Render
"""
import os
import asyncio
import logging
from aiohttp import web
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from dotenv import load_dotenv
from telegram_handlers import (
    start, show_matches, analyze_match, show_news, show_press,
    daily_digest_command, handle_followup_question, help_command
)

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PORT = int(os.getenv("PORT", 10000))

async def health_check(request):
    return web.Response(text="OK")

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("matches", show_matches))
    app.add_handler(CommandHandler("news", show_news))
    app.add_handler(CommandHandler("daily_digest", daily_digest_command))
    app.add_handler(CommandHandler("help", help_command))
    
    # Callbacks
    app.add_handler(CallbackQueryHandler(show_matches, pattern="^matches$"))
    app.add_handler(CallbackQueryHandler(analyze_match, pattern="^analyze_"))
    app.add_handler(CallbackQueryHandler(show_news, pattern="^news$"))
    app.add_handler(CallbackQueryHandler(show_press, pattern="^press$"))
    app.add_handler(CallbackQueryHandler(daily_digest_command, pattern="^digest$"))
    app.add_handler(CallbackQueryHandler(help_command, pattern="^help$"))
    
    # Text
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_followup_question))
    
    await app.initialize()
    await app.start()
    app.updater.start_polling()
    
    # Health check server
    web_app = web.Application()
    web_app.router.add_get('/', health_check)
    web_app.router.add_get('/health', health_check)
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    
    logger.info(f"Bot started on port {PORT}")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())