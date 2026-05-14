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
    """Health check endpoint for UptimeRobot."""
    return web.Response(text="OK - PepBielsa Bot Running")

async def main():
    """Start both Telegram bot and health check server."""
    
    # 1. Initialize Telegram bot
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Register command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("matches", show_matches))
    app.add_handler(CommandHandler("news", show_news))
    app.add_handler(CommandHandler("daily_digest", daily_digest_command))
    app.add_handler(CommandHandler("help", help_command))
    
    # Register callback query handlers
    app.add_handler(CallbackQueryHandler(show_matches, pattern="^matches$"))
    app.add_handler(CallbackQueryHandler(analyze_match, pattern="^analyze_"))
    app.add_handler(CallbackQueryHandler(show_news, pattern="^news$"))
    app.add_handler(CallbackQueryHandler(show_press, pattern="^press$"))
    app.add_handler(CallbackQueryHandler(daily_digest_command, pattern="^digest$"))
    app.add_handler(CallbackQueryHandler(help_command, pattern="^help$"))
    
    # Register text message handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_followup_question))
    
    # 2. Initialize and start bot
    await app.initialize()
    await app.start()
    
    # Start polling (with await this time!)
    await app.updater.start_polling()
    
    # 3. Create health check web server
    web_app = web.Application()
    web_app.router.add_get('/', health_check)
    web_app.router.add_get('/health', health_check)
    
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    
    logger.info(f"✅ Bot started successfully on port {PORT}")
    logger.info(f"✅ Health check: http://0.0.0.0:{PORT}/health")
    
    # 4. Keep running forever
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())