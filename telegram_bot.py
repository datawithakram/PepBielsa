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
    start, show_matches, show_all_matches, analyze_match,
    show_news, show_press,
    daily_digest_command, handle_followup_question, help_command,
    show_general_news, show_transfers, show_injuries, show_breaking,
    admin_reset_news,
)
from news_scheduler import register_jobs

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
    app.add_handler(CommandHandler("matches_all", show_all_matches))
    app.add_handler(CommandHandler("news", show_news))
    app.add_handler(CommandHandler("transfers", show_transfers))
    app.add_handler(CommandHandler("injuries", show_injuries))
    app.add_handler(CommandHandler("breaking", show_breaking))
    app.add_handler(CommandHandler("press", show_press))
    app.add_handler(CommandHandler("daily_digest", daily_digest_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("reset_news", admin_reset_news))

    # Register callback query handlers
    app.add_handler(CallbackQueryHandler(start,            pattern="^start$"))
    app.add_handler(CallbackQueryHandler(show_matches,     pattern="^matches$"))
    app.add_handler(CallbackQueryHandler(analyze_match,    pattern="^analyze_"))
    app.add_handler(CallbackQueryHandler(show_news,        pattern="^news$"))
    app.add_handler(CallbackQueryHandler(show_general_news, pattern="^news_general$"))
    app.add_handler(CallbackQueryHandler(show_transfers,   pattern="^news_transfers$"))
    app.add_handler(CallbackQueryHandler(show_press,       pattern="^news_press$"))
    app.add_handler(CallbackQueryHandler(show_injuries,    pattern="^news_injuries$"))
    app.add_handler(CallbackQueryHandler(show_breaking,    pattern="^news_breaking$"))
    app.add_handler(CallbackQueryHandler(show_press,       pattern="^press$"))
    app.add_handler(CallbackQueryHandler(daily_digest_command, pattern="^digest$"))
    app.add_handler(CallbackQueryHandler(help_command,     pattern="^help$"))
    
    # Register text message handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_followup_question))

    # 2. Initialize and start bot
    await app.initialize()
    await app.start()

    # Register scheduled news jobs
    register_jobs(app)
    
    if app.job_queue:
        await app.job_queue.start()
        logger.info("✅ JobQueue started")
    
    # ⭐ احذف أي رسائل قديمة معلقة قبل بدء الاستماع
    await app.bot.delete_webhook(drop_pending_updates=True)
    logger.info("✅ Cleared pending updates")
    
    # Start polling
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
        if app.job_queue:
            await app.job_queue.stop()
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())