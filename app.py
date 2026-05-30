"""
app.py — PepBielsa Health Check Server
Provides a lightweight HTTP server for uptime monitoring (UptimeRobot / BetterStack).
The actual Telegram bot runs via telegram_bot.py.
This file exposes /health and / endpoints so the server stays "awake" on free hosts.
"""
import os
import logging
from aiohttp import web

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PORT = int(os.getenv("PORT", 10000))


async def health_check(request):
    """Health check endpoint — used by UptimeRobot to keep the server alive."""
    return web.Response(
        text=(
            "✅ PepBielsa Bot — Online\n"
            "Tactical AI Engine: Running\n"
            "Data Source: SofaScore\n"
            "Status: Polling active"
        ),
        content_type="text/plain",
    )


async def index(request):
    """Root index page with basic bot info."""
    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>PepBielsa Bot — Status</title>
  <style>
    body { background: #111827; color: #F9FAFB; font-family: Inter, sans-serif;
           display: flex; align-items: center; justify-content: center;
           min-height: 100vh; margin: 0; }
    .card { background: #1F2937; border-radius: 16px; padding: 48px 56px;
            max-width: 520px; text-align: center; border: 1px solid #374151; }
    h1 { color: #00A86B; font-size: 2rem; margin: 0 0 8px; }
    .badge { display: inline-block; background: #065F46; color: #6EE7B7;
             border-radius: 999px; padding: 4px 16px; font-size: 0.85rem;
             font-weight: 600; margin-bottom: 24px; }
    p { color: #9CA3AF; line-height: 1.7; }
    .stat { display: flex; justify-content: space-between;
            border-top: 1px solid #374151; padding: 10px 0; font-size: 0.9rem; }
    .stat-label { color: #6B7280; }
    .stat-value { color: #F4B400; font-weight: 700; }
  </style>
</head>
<body>
  <div class="card">
    <h1>⚽ PepBielsa AI</h1>
    <div class="badge">● Online</div>
    <p>Elite Football Tactical Intelligence Bot — powered by SofaScore data and Gemini AI.</p>
    <div class="stat"><span class="stat-label">Data Source</span><span class="stat-value">SofaScore</span></div>
    <div class="stat"><span class="stat-label">AI Engine</span><span class="stat-value">Gemini 2.5 Flash</span></div>
    <div class="stat"><span class="stat-label">Sections / Match</span><span class="stat-value">14 Sections</span></div>
    <div class="stat"><span class="stat-label">Custom Visuals</span><span class="stat-value">9 Chart Types</span></div>
    <div class="stat"><span class="stat-label">Mode</span><span class="stat-value">Long Polling</span></div>
  </div>
</body>
</html>"""
    return web.Response(text=html, content_type="text/html")


def create_app() -> web.Application:
    """Create and configure the aiohttp web application."""
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/health", health_check)
    return app


if __name__ == "__main__":
    # Standalone run (for local testing only — normally called from telegram_bot.py)
    web.run_app(create_app(), host="0.0.0.0", port=PORT)