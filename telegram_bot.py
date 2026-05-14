"""
Main Telegram bot script – run this on Render.
"""
import os
import logging
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
from dotenv import load_dotenv
from telegram_handlers import (
    start, show_matches, analyze_match, show_news, show_press,
    daily_digest_command, handle_followup_question, help_command
)

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("matches", lambda u,c: show_matches(u,c)))
    app.add_handler(CommandHandler("news", lambda u,c: show_news(u,c)))
    app.add_handler(CommandHandler("daily_digest", lambda u,c: daily_digest_command(u,c)))
    app.add_handler(CommandHandler("help", help_command))

    # Callback query handlers
    app.add_handler(CallbackQueryHandler(show_matches, pattern="^matches$"))
    app.add_handler(CallbackQueryHandler(analyze_match, pattern="^analyze_"))
    app.add_handler(CallbackQueryHandler(show_news, pattern="^news$"))
    app.add_handler(CallbackQueryHandler(show_press, pattern="^press$"))
    app.add_handler(CallbackQueryHandler(daily_digest_command, pattern="^digest$"))
    app.add_handler(CallbackQueryHandler(help_command, pattern="^help$"))

    # Follow-up questions (any text message after analysis)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_followup_question))

    logger.info("Bot started, polling...")
    app.run_polling()

if __name__ == "__main__":
    main()