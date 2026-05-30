"""
telegram_handlers.py — SofaScore Automated Edition
Fully detached from API-Football. Uses SofaScore scraping for all data.
"""
import os
import json
import logging
import asyncio
import base64
import html
from io import BytesIO
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

from utils import get_cache, set_cache
from keyboard import matches_keyboard, main_menu_keyboard, news_menu_keyboard
from data_aggregator import aggregator
from tactical_engine import compute_tactical_summary_from_scraping
from ai_analysis import generate_full_match_report, format_report_for_telegram, generate_social_insights, answer_followup
from visuals import generate_all_graphics

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🤖 *PepBielsa AI — Elite Football Intelligence*\n\n"
        "Upgraded to rely entirely on **SofaScore** deep data.\n"
        "Professional tactical analysis, heatmaps, and 14-section reports.\n\n"
        "Select an option to begin:"
    )
    reply_markup = main_menu_keyboard()
    if update.message:
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(msg, parse_mode="Markdown", reply_markup=reply_markup)

async def show_matches(update: Update, context: ContextTypes.DEFAULT_TYPE, date_str: str = None):
    q = update.callback_query
    if q: await q.answer()
    
    try:
        fixtures = aggregator.get_daily_fixtures(date_str=date_str, major_only=True)
        if not fixtures and not date_str:
            txt = "📅 *No major matches found today on SofaScore.*"
            await (q.edit_message_text(txt, parse_mode="Markdown", reply_markup=main_menu_keyboard()) if q else update.message.reply_text(txt, parse_mode="Markdown"))
            return

        header = f"📅 *Matches for {date_str if date_str else 'Today'} (SofaScore Data)*"
        reply_markup = matches_keyboard(fixtures, current_date=date_str)
        if q: await q.edit_message_text(header, parse_mode="Markdown", reply_markup=reply_markup)
        else: await update.message.reply_text(header, parse_mode="Markdown", reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"SofaScore fixtures failed: {e}")
        await update.effective_message.reply_text("❌ Error fetching matches.")

async def handle_date_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    date_str = q.data.split("_")[1]
    await show_matches(update, context, date_str=date_str)

async def show_all_matches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q: await q.answer()
    try:
        fixtures = aggregator.get_daily_fixtures(major_only=False)
        header = f"📅 *All Today's Matches ({len(fixtures)})*"
        reply_markup = matches_keyboard(fixtures)
        if q: await q.edit_message_text(header, parse_mode="Markdown", reply_markup=reply_markup)
        else: await update.message.reply_text(header, parse_mode="Markdown", reply_markup=reply_markup)
    except Exception as e:
        await update.effective_message.reply_text(f"❌ Error: {e}")

async def analyze_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    match_id = q.data.split("_")[1]
    
    status_msg = await q.edit_message_text("🔄 *Scraping Tactical Intelligence from SofaScore...*\nAnalyzing movements, passing lanes, and heatmaps.", parse_mode="Markdown")
    
    try:
        # 1. SofaScore Scraping (blocking I/O → thread)
        import asyncio as _aio
        raw_data = await _aio.to_thread(aggregator.get_match_all_data, int(match_id))
        
        if not raw_data.get("stats_groups"):
            await q.message.reply_text("⚠️ *Data Not Ready:* Match statistics are not yet available.")
            return

        # 2. Tactical Preprocessing
        await status_msg.edit_text("🧠 *Processing Data & Building Tactical Model...*", parse_mode="Markdown")
        summary = await _aio.to_thread(compute_tactical_summary_from_scraping, raw_data)
        
        await status_msg.edit_text("🤖 *Generating Professional 14-Section Report...*\n_(~60–90 sec)_", parse_mode="Markdown")
        full_report     = await _aio.to_thread(generate_full_match_report, summary)
        social_insights = await _aio.to_thread(generate_social_insights, summary)
        
        # 4. Visuals
        await status_msg.edit_text("🎨 *Generating Advanced Tactical Graphics...*", parse_mode="Markdown")
        graphics = await _aio.to_thread(generate_all_graphics, summary)
        
        await status_msg.delete()
        
        # Send Report & Graphics Interspersed
        report_chunks = format_report_for_telegram(full_report, summary)
        
        # Mapping: Index in report_chunks (Header is 0, Section 1 is 1...)
        # We match Section 1-14 with graphics 1-14
        mapping = {
            1: "1-Match_Overview",
            2: "2-Shot_Map",
            3: "3-xG_Flow",
            4: "4-Tactical_Formations",
            5: "5-Goalpost_Map",
            6: "6-Assist_Map",
            7: "7-Struggling_Players",
            8: "8-Match_Performers",
            9: "9-Momentum",
            10: "10-Chances_and_Mistakes",
            11: "11-Stars_of_the_Match",
            12: "12-Territory_Map",
            13: "13-Passing_Networks",
            14: "14-Attack_Zones"
        }

        for i, chunk in enumerate(report_chunks):
            try:
                await context.bot.send_message(chat_id=update.effective_chat.id, text=chunk, parse_mode="HTML")
            except Exception as ce:
                logger.warning(f"Chunk {i} HTML failed ({ce}), sending as plain text")
                plain = chunk.replace("<b>","").replace("</b>","").replace("<i>","").replace("</i>","")
                try:
                    await context.bot.send_message(chat_id=update.effective_chat.id, text=plain[:4000])
                except Exception:
                    pass

            # Send paired graphic
            g_key = mapping.get(i)
            if g_key and graphics.get(g_key):
                try:
                    photo_bytes = BytesIO(base64.b64decode(graphics[g_key]))
                    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=photo_bytes)
                except Exception as eg:
                    logger.warning(f"Graphic {g_key} failed: {eg}")

        # Send Social
        if social_insights:
            txt = "📱 <b>Tactical Insights</b>\n\n" + "\n".join([f"• {html.escape(i)}" for i in social_insights])
            await context.bot.send_message(chat_id=update.effective_chat.id, text=txt, parse_mode="HTML")

        set_cache(f"ctx_{update.effective_user.id}", summary)
        await context.bot.send_message(chat_id=update.effective_chat.id, text="💬 Ask anything about this match!", reply_markup=main_menu_keyboard())

    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        await q.message.reply_text(f"❌ *Tactical Analysis Error:* {str(e)[:200]}")

async def handle_followup_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    
    # ─── Stateful Input Capture for Broadcast Quote/Bio Cards ───
    state = context.user_data.get("custom_state")
    if state == "waiting_quote_text":
        text = update.message.text
        parts = [p.strip() for p in text.split("|")]
        if len(parts) < 3:
            await update.message.reply_text("⚠️ *Invalid format.*\n\nPlease use the exact format:\n`[Name] | [Role/Team] | [Quote Text]`")
            return
        context.user_data["quote_data"] = {"name": parts[0], "sub": parts[1], "text": parts[2]}
        context.user_data["custom_state"] = "quote_waiting_photo"
        await update.message.reply_text("📸 *Perfect! Now send the photo of the player/coach!*")
        return
        
    elif state == "waiting_bio_text":
        text = update.message.text
        parts = [p.strip() for p in text.split("|")]
        if len(parts) < 3:
            await update.message.reply_text("⚠️ *Invalid format.*\n\nPlease use the exact format:\n`[Player Name] | [Season/Match] | [Stat1: Val1, Stat2: Val2]`")
            return
            
        stats_str = parts[2]
        stats_dict = {}
        try:
            for pair in stats_str.split(","):
                k, v = pair.split(":")
                stats_dict[k.strip()] = v.strip()
        except:
            await update.message.reply_text("⚠️ *Failed to parse statistics.* Make sure to separate them with commas and use colons, like: `Goals: 32, Assists: 8`")
            return
            
        context.user_data["bio_data"] = {"name": parts[0], "sub": parts[1], "stats": stats_dict}
        context.user_data["custom_state"] = "bio_waiting_photo"
        await update.message.reply_text("📸 *Perfect! Now send the photo of the player!*")
        return
        
    summary = get_cache(f"ctx_{update.effective_user.id}")
    if not summary: return
    
    thinking = await update.message.reply_text("🤔 *Analyzing question...*", parse_mode="Markdown")
    try:
        answer = answer_followup(update.message.text, summary)
        await thinking.edit_text(f"💬 *Tactical Response:*\n\n{answer}", parse_mode="Markdown")
    except Exception as e:
        await thinking.edit_text(f"❌ Error: {e}")

# News Handlers
async def show_news(update, context):
    q = update.callback_query
    if q: await q.answer()
    await (q.edit_message_text("📰 *Select Category:*", parse_mode="Markdown", reply_markup=news_menu_keyboard()) if q else update.message.reply_text("📰 *Select Category:*", parse_mode="Markdown", reply_markup=news_menu_keyboard()))

async def _handle_news_category(update, context, cat, label):
    from feed_fetcher import fetch_category
    from news_scheduler import _format_caption
    items = fetch_category(cat, max_per_feed=3)
    for item in items:
        caption = _format_caption(item, cat)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=caption, parse_mode="Markdown")
    await context.bot.send_message(chat_id=update.effective_chat.id, text="↩️ Back to Main Menu:", reply_markup=main_menu_keyboard())

async def show_general_news(update, context): await _handle_news_category(update, context, "general", "News")
async def show_transfers(update, context): await _handle_news_category(update, context, "transfers", "Transfers")
async def show_press(update, context): await _handle_news_category(update, context, "press_conference", "Press")
async def show_injuries(update, context): await _handle_news_category(update, context, "injuries", "Injuries")
async def show_breaking(update, context): await _handle_news_category(update, context, "breaking", "Breaking")
async def help_command(update, context):
    help_text = (
        "🤖 <b>PepBielsa AI — Command Guide</b>\n\n"
        "<b>📊 Match Analysis</b>\n"
        "• <b>Show Matches</b> → Pick any live/finished match\n"
        "• Bot delivers 14-section tactical report + visuals\n"
        "• Ask follow-up questions after any analysis\n\n"
        "<b>🎨 Custom Drawing System</b>\n"
        "• <b>Territory Map</b> — 32-zone dominance heatmap\n"
        "• <b>Shot Map</b> — Team & player shots with xG\n"
        "• <b>Heatmap</b> — Individual player movement\n"
        "• <b>Pass Map</b> — Accurate/key passes visualized\n"
        "• <b>Goalkeeper Saves</b> — Frame-accurate save map\n"
        "• <b>Attack Flanks</b> — Left/Center/Right % breakdown\n\n"
        "<b>🏆 Standings Cards</b>\n"
        "• Live standings with your custom photo (32+ leagues)\n"
        "• Round-range standings (Opta style) for any gameweek\n\n"
        "<b>🎴 Social Media Cards</b>\n"
        "• <b>Quote Card</b> → Name | Role | Quote + photo\n"
        "• <b>Player Bio</b> → Name | Season | Stats + photo\n\n"
        "<b>📰 News Engine</b>\n"
        "• /news — Browse all categories\n"
        "• /transfers — Latest transfer news\n"
        "• /injuries — Injury & absence updates\n"
        "• /breaking — Breaking alerts\n"
        "• /press — Press conference summaries\n\n"
        "<b>📋 Other Commands</b>\n"
        "• /start — Main menu\n"
        "• /daily_digest — Today's match briefing\n"
        "• /custom — Custom drawing system\n"
        "• /help — This guide\n"
    )
    q = update.callback_query
    if q:
        await q.answer()
        await q.edit_message_text(help_text, parse_mode="HTML", reply_markup=main_menu_keyboard())
    else:
        await update.message.reply_text(help_text, parse_mode="HTML", reply_markup=main_menu_keyboard())
async def admin_status(update, context): await update.message.reply_text("System: Online (SofaScore Mode)")
async def daily_digest_command(update, context):
    q = update.callback_query
    if q: await q.answer()
    chat_id = update.effective_chat.id
    status = await (q.edit_message_text("⏳ *Preparing Daily Digest...*", parse_mode="Markdown") if q else update.message.reply_text("⏳ *Preparing Daily Digest...*", parse_mode="Markdown"))
    try:
        import asyncio as _aio
        from daily_digest import create_daily_digest
        text = await _aio.to_thread(create_daily_digest)
        await status.delete()
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML", reply_markup=main_menu_keyboard())
    except Exception as e:
        logger.error(f"Daily digest failed: {e}")
        await status.edit_text(f"❌ Failed to generate digest: {e}")

async def admin_reset_news(update, context): await update.message.reply_text("News cache has been reset.")

# ── Custom Tactical Drawing System ───────────────────────────────────────────

from custom_visuals import (
    generate_custom_player_heatmap,
    generate_custom_player_shotmap,
    generate_custom_player_passmap,
    generate_custom_team_shotmap,
    generate_custom_team_territory,
    generate_custom_team_flanks,
    generate_goalkeeper_saves_map,
    generate_league_standings_card,
    generate_quote_card,
    generate_player_bio_card,
    generate_league_standings_round_range_card
)

COUNTRIES = {
    "england": {"label": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 England"},
    "spain": {"label": "🇪🇸 Spain"},
    "italy": {"label": "🇮🇹 Italy"},
    "germany": {"label": "🇩🇪 Germany"},
    "france": {"label": "🇫🇷 France"},
    "saudi": {"label": "🇸🇦 Saudi Arabia"},
}

LEAGUES = {
    "england": [
        {"name": "Premier League", "id": 17, "label": "🥇 Premier League"},
        {"name": "Championship", "id": 18, "label": "🥈 Championship"},
        {"name": "League One", "id": 108, "label": "🥉 League One"},
    ],
    "spain": [
        {"name": "La Liga", "id": 8, "label": "🥇 La Liga"},
        {"name": "Segunda División", "id": 54, "label": "🥈 Segunda División"},
    ],
    "italy": [
        {"name": "Serie A", "id": 23, "label": "🥇 Serie A"},
        {"name": "Serie B", "id": 53, "label": "🥈 Serie B"},
    ],
    "germany": [
        {"name": "Bundesliga", "id": 35, "label": "🥇 Bundesliga"},
        {"name": "2. Bundesliga", "id": 44, "label": "🥈 2. Bundesliga"},
    ],
    "france": [
        {"name": "Ligue 1", "id": 34, "label": "🥇 Ligue 1"},
        {"name": "Ligue 2", "id": 182, "label": "🥈 Ligue 2"},
    ],
    "saudi": [
        {"name": "Saudi Pro League", "id": 350, "label": "🥇 Saudi Pro League"},
    ]
}

async def custom_drawing_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "🎨 *Custom Tactical Drawing System*\n\nSelect a custom standings generator, browse leagues and teams, or choose a broadcast quote/bio card creator below:"
    buttons = [
        [InlineKeyboardButton("🏆 Standings by Round Range (Opta Style)", callback_data="cust_st_start")]
    ]
    keys = list(COUNTRIES.keys())
    for i in range(0, len(keys), 2):
        row = []
        row.append(InlineKeyboardButton(COUNTRIES[keys[i]]["label"], callback_data=f"cust_co_{keys[i]}"))
        if i + 1 < len(keys):
            row.append(InlineKeyboardButton(COUNTRIES[keys[i+1]]["label"], callback_data=f"cust_co_{keys[i+1]}"))
        buttons.append(row)
        
    # Quote Card & Player Bio Card options directly
    buttons.append([
        InlineKeyboardButton("🎙️ Quote Card Creator", callback_data="cust_opt_quote"),
        InlineKeyboardButton("👤 Player Bio Stats Card", callback_data="cust_opt_bio")
    ])
    buttons.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="start")])
    
    q = update.callback_query
    if q:
        await q.answer()
        await q.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")
    else:
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

async def custom_country_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    country = q.data.split("_")[2]
    
    leagues = LEAGUES.get(country, [])
    msg = f"🏆 *Select Division for {COUNTRIES[country]['label']}:*"
    
    buttons = []
    for l in leagues:
        buttons.append([InlineKeyboardButton(l["label"], callback_data=f"cust_le_{l['id']}_{l['name']}")])
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="cust_home")])
    
    await q.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

async def custom_league_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("_")
    league_id = int(parts[2])
    league_name = parts[3]
    
    # Show loading status
    status = await q.edit_message_text("🔄 *Fetching standings and teams from SofaScore...*", parse_mode="Markdown")
    
    # Run in thread executor
    def _fetch_teams():
        from curl_cffi import requests
        # SofaScore unique tournament standings endpoint fetches all standings rows
        url = f"https://api.sofascore.com/api/v1/unique-tournament/{league_id}/seasons"
        resp = requests.get(url, impersonate="chrome124", timeout=10)
        if resp.status_code != 200: return []
        seasons = resp.json().get("seasons", [])
        if not seasons: return []
        season_id = seasons[0]["id"]
        
        t_url = f"https://api.sofascore.com/api/v1/unique-tournament/{league_id}/season/{season_id}/standings/total"
        resp_t = requests.get(t_url, impersonate="chrome124", timeout=10)
        if resp_t.status_code != 200: return []
        standings = resp_t.json().get("standings", [])
        if not standings: return []
        rows = standings[0].get("rows", [])
        
        teams = []
        for r in rows:
            t = r.get("team", {})
            teams.append({"name": t.get("name"), "id": t.get("id")})
        # Sort alphabetically
        teams.sort(key=lambda x: x["name"])
        return teams

    teams = await asyncio.to_thread(_fetch_teams)
    
    if not teams:
        await status.edit_text("❌ *Failed to fetch teams.* Live tournament data currently unavailable.", 
                               reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cust_home")]]))
        return
        
    msg = "🛡️ *Select a Team to Analyze, or choose Live Standings Table Card:*"
    
    # Standings Table Card shortcut button at the top
    buttons = [[InlineKeyboardButton("🏆 Standings Table Card", callback_data=f"cust_opt_standings_{league_id}")]]
    
    for i in range(0, len(teams), 2):
        row = []
        row.append(InlineKeyboardButton(teams[i]["name"], callback_data=f"cust_te_{teams[i]['id']}_{teams[i]['name'][:15]}"))
        if i + 1 < len(teams):
            row.append(InlineKeyboardButton(teams[i+1]["name"], callback_data=f"cust_te_{teams[i+1]['id']}_{teams[i+1]['name'][:15]}"))
        buttons.append(row)
        
    buttons.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cust_home")])
    await status.edit_text(msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

async def custom_team_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("_")
    team_id = int(parts[2])
    team_name = parts[3]
    
    msg = f"📊 *Choose Custom Analysis Type for {team_name}:*"
    buttons = [
        [InlineKeyboardButton("👥 Analyze Team (Territory/Shots/Flanks)", callback_data=f"cust_opt_team_{team_id}_{team_name}")],
        [InlineKeyboardButton("👤 Analyze Individual Player", callback_data=f"cust_opt_player_{team_id}_{team_name}")],
        [InlineKeyboardButton("🔙 Back", callback_data="cust_home")]
    ]
    await q.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

async def custom_option_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    
    if data == "cust_opt_quote":
        context.user_data["custom_state"] = "waiting_quote_text"
        await q.edit_message_text(
            "🎙️ *Player/Coach Quote Card Mode*\n\n"
            "Please type the quote details in this exact format:\n"
            "`[Name] | [Role/Team] | [Quote Text]`\n\n"
            "*Example:*\n"
            "`Pep Guardiola | Man City Manager | We played with amazing passion and deserved the victory today.`",
            parse_mode="Markdown"
        )
        return
        
    elif data == "cust_opt_bio":
        context.user_data["custom_state"] = "waiting_bio_text"
        await q.edit_message_text(
            "👤 *Player Bio Stats Card Mode*\n\n"
            "Please type the player details and statistics in this exact format:\n"
            "`[Player Name] | [Season/Match] | [Stat1: Val1, Stat2: Val2]`\n\n"
            "*Example:*\n"
            "`Erling Haaland | Premier League 2025/26 | Goals: 32, Assists: 8, Shots: 94, Rating: 8.2`",
            parse_mode="Markdown"
        )
        return
        
    elif data.startswith("cust_opt_standings_"):
        league_id = int(data.split("_")[3])
        context.user_data["custom_league_id"] = league_id
        context.user_data["custom_state"] = "standings_waiting_photo"
        await q.edit_message_text(
            "🏆 *Standings Table Card Mode*\n\n"
            "We will dynamically fetch the live standings table from SofaScore.\n\n"
            "📸 *Please send the custom match photo you want to display next to the standings table!*",
            parse_mode="Markdown"
        )
        return

    parts = data.split("_")
    opt_type = parts[2]
    team_id = int(parts[3])
    team_name = parts[4]
    
    if opt_type == "team":
        # Draw team visual menu
        msg = f"👥 *Select Team Tactical Chart for {team_name}:*"
        buttons = [
            [InlineKeyboardButton("🥅 Team Shot Map", callback_data=f"cust_ch_team_{team_id}_shotmap")],
            [InlineKeyboardButton("🗺️ Territory Dominance Map (32 Zones)", callback_data=f"cust_ch_team_{team_id}_territory")],
            [InlineKeyboardButton("🏹 Attack Focus Flanks", callback_data=f"cust_ch_team_{team_id}_flanks")],
            [InlineKeyboardButton("🔙 Back", callback_data=f"cust_te_{team_id}_{team_name}")]
        ]
        await q.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")
        
    elif opt_type == "player":
        # Show positions sub-menu
        msg = f"👤 *Select Roster Category for {team_name}:*"
        buttons = [
            [InlineKeyboardButton("🧤 Goalkeepers", callback_data=f"cust_pos_G_{team_id}_{team_name}")],
            [InlineKeyboardButton("🛡️ Defenders", callback_data=f"cust_pos_D_{team_id}_{team_name}")],
            [InlineKeyboardButton("⚙️ Midfielders", callback_data=f"cust_pos_M_{team_id}_{team_name}")],
            [InlineKeyboardButton("🔥 Forwards", callback_data=f"cust_pos_F_{team_id}_{team_name}")],
            [InlineKeyboardButton("🔙 Back", callback_data=f"cust_te_{team_id}_{team_name}")]
        ]
        await q.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

async def custom_player_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("_")
    pos_code = parts[2]
    team_id = int(parts[3])
    team_name = parts[4]
    
    status = await q.edit_message_text("🔄 *Fetching roster squad...*", parse_mode="Markdown")
    
    def _fetch_roster():
        from curl_cffi import requests
        url = f"https://api.sofascore.com/api/v1/team/{team_id}/players"
        resp = requests.get(url, impersonate="chrome124", timeout=10)
        if resp.status_code != 200: return []
        players = resp.json().get("players", [])
        
        # Position grouping map
        pos_map = {
            "G": ["G"],
            "D": ["D"],
            "M": ["M"],
            "F": ["F"]
        }
        
        target_positions = pos_map.get(pos_code, [])
        filtered = []
        for p in players:
            pl = p.get("player", {})
            pos = pl.get("position", "")
            if pos in target_positions:
                filtered.append({
                    "name": pl.get("name"),
                    "short": pl.get("shortName", pl.get("name")),
                    "id": pl.get("id")
                })
        filtered.sort(key=lambda x: x["name"])
        return filtered

    players = await asyncio.to_thread(_fetch_roster)
    
    if not players:
        await status.edit_text("❌ *No players found for this category.*", 
                               reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"cust_opt_player_{team_id}_{team_name}")]]))
        return
        
    msg = f"👥 *Select Player from {team_name}:*"
    buttons = []
    for i in range(0, len(players), 2):
        row = []
        row.append(InlineKeyboardButton(players[i]["short"], callback_data=f"cust_pl_{team_id}_{players[i]['id']}_{players[i]['short'][:15]}"))
        if i + 1 < len(players):
            row.append(InlineKeyboardButton(players[i+1]["short"], callback_data=f"cust_pl_{team_id}_{players[i+1]['id']}_{players[i+1]['short'][:15]}"))
        buttons.append(row)
        
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"cust_opt_player_{team_id}_{team_name}")])
    await status.edit_text(msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

async def custom_player_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("_")
    team_id = int(parts[2])
    player_id = int(parts[3])
    player_name = parts[4]
    
    msg = f"🎨 *Select Chart for {player_name}:*"
    buttons = [
        [InlineKeyboardButton("🌡️ Player Heatmap", callback_data=f"cust_ch_player_{team_id}_{player_id}_{player_name}_heatmap")],
        [InlineKeyboardButton("🎯 Player Passing Map", callback_data=f"cust_ch_player_{team_id}_{player_id}_{player_name}_passmap")],
        [InlineKeyboardButton("⚽ Player Shot Map", callback_data=f"cust_ch_player_{team_id}_{player_id}_{player_name}_shotmap")],
        [InlineKeyboardButton("🧤 Goalkeeper Saves Map", callback_data=f"cust_ch_player_{team_id}_{player_id}_{player_name}_saves")],
        [InlineKeyboardButton("🔙 Back", callback_data="cust_home")]
    ]
    await q.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

async def custom_chart_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("_")
    target = parts[2] # team or player
    
    if target == "team":
        team_id = int(parts[3])
        chart_type = parts[4]
        # cust_sc_{target}_{team_id}_{chart_type}_{scope}
        msg = "🗓️ *Select Scope / Match Frequency:* \nWe will aggregate spatial coordinates dynamically."
        buttons = [
            [InlineKeyboardButton("⚽ Last Match", callback_data=f"cust_sc_team_{team_id}_{chart_type}_1")],
            [InlineKeyboardButton("🗓️ Last 5 Matches (Recommended)", callback_data=f"cust_sc_team_{team_id}_{chart_type}_5")],
            [InlineKeyboardButton("🏆 Last 10 Matches (Deep Trends)", callback_data=f"cust_sc_team_{team_id}_{chart_type}_10")],
            [InlineKeyboardButton("🔙 Back", callback_data="cust_home")]
        ]
    else: # player
        team_id = int(parts[3])
        player_id = int(parts[4])
        player_name = parts[5]
        chart_type = parts[6]
        msg = f"🗓️ *Select Scope / Match Frequency for {player_name}:*"
        buttons = [
            [InlineKeyboardButton("⚽ Last Match", callback_data=f"cust_sc_player_{team_id}_{player_id}_{player_name}_{chart_type}_1")],
            [InlineKeyboardButton("🗓️ Last 5 Matches (Recommended)", callback_data=f"cust_sc_player_{team_id}_{player_id}_{player_name}_{chart_type}_5")],
            [InlineKeyboardButton("🏆 Last 10 Matches (Deep Trends)", callback_data=f"cust_sc_player_{team_id}_{player_id}_{player_name}_{chart_type}_10")],
            [InlineKeyboardButton("🔙 Back", callback_data="cust_home")]
        ]
        
    await q.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

async def custom_generate_chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("_")
    target = parts[2]
    
    status = await q.edit_message_text("🚀 *Aggregating coordinates and drawing premium chart...* \nThis might take a few seconds.", parse_mode="Markdown")
    
    # Parameters extraction
    if target == "team":
        team_id = int(parts[3])
        chart_type = parts[4]
        match_count = int(parts[5])
        player_id = None
        player_name = ""
    else:
        team_id = int(parts[3])
        player_id = int(parts[4])
        player_name = parts[5]
        chart_type = parts[6]
        match_count = int(parts[7])
        
    def _fetch_and_draw():
        from curl_cffi import requests
        # Step 1: Fetch team last match IDs
        url = f"https://api.sofascore.com/api/v1/team/{team_id}/events/last/0"
        resp = requests.get(url, impersonate="chrome124", timeout=10)
        if resp.status_code != 200: return None
        events = resp.json().get("events", [])
        
        # Filter football events only
        football_events = [e for e in events if e.get("sportEventStatus", {}).get("type") == "finished" and e.get("customId")]
        target_events = football_events[:match_count]
        
        if not target_events: return None
        
        team_name = target_events[0].get("homeTeam", {}).get("name") if target_events[0].get("homeTeam", {}).get("id") == team_id else target_events[0].get("awayTeam", {}).get("name")
        scope_label = "Last Match" if match_count == 1 else f"Last {match_count} Matches"
        
        try:
            if target == "player":
                if chart_type == "heatmap":
                    points = []
                    total_touches = 0
                    ratings = []
                    for ev in target_events:
                        ev_id = ev["id"]
                        
                        # 1. Fetch Heatmap
                        hm_url = f"https://api.sofascore.com/api/v1/event/{ev_id}/player/{player_id}/heatmap"
                        resp_hm = requests.get(hm_url, impersonate="chrome124", timeout=8)
                        if resp_hm.status_code == 200:
                            points.extend(resp_hm.json().get("heatmap", []))
                            
                        # 2. Fetch Player Statistics
                        stats_url = f"https://api.sofascore.com/api/v1/event/{ev_id}/player/{player_id}/statistics"
                        resp_stats = requests.get(stats_url, impersonate="chrome124", timeout=8)
                        if resp_stats.status_code == 200:
                            stats_data = resp_stats.json().get("statistics", {})
                            
                            t_val = stats_data.get("touches", 0)
                            if isinstance(t_val, (int, float)):
                                total_touches += int(t_val)
                            
                            r_val = stats_data.get("rating")
                            if r_val:
                                try:
                                    ratings.append(float(r_val))
                                except (ValueError, TypeError):
                                    pass
                                    
                    avg_rating = sum(ratings) / len(ratings) if ratings else None
                    if total_touches == 0:
                        total_touches = len(points)
                        
                    tournament_name = "Tournament"
                    if target_events:
                        tournament_name = target_events[0].get("tournament", {}).get("name", "Tournament")
                        
                    img_b64 = generate_custom_player_heatmap(
                        player_name, team_name, points, scope_label,
                        player_id=player_id, num_matches=len(target_events),
                        total_touches=total_touches, avg_rating=avg_rating,
                        tournament=tournament_name
                    )
                    
                    rating_caption = f" | Avg Rating: {avg_rating:.2f}" if avg_rating else ""
                    return {"type": "photo", "b64": img_b64, "caption": f"🌡️ <b>Player Touch Heatmap</b> for <b>{player_name}</b> ({team_name})\nScope: {scope_label}\nTournament: {tournament_name}\nTouches: {total_touches}{rating_caption}"}
                    
                elif chart_type == "shotmap":
                    shots = []
                    for ev in target_events:
                        ev_id = ev["id"]
                        sm_url = f"https://api.sofascore.com/api/v1/event/{ev_id}/shotmap"
                        resp_sm = requests.get(sm_url, impersonate="chrome124", timeout=8)
                        if resp_sm.status_code == 200:
                            for s in resp_sm.json().get("shotmap", []):
                                p_id = s.get("player", {}).get("id")
                                if p_id == player_id:
                                    stype = "Goal" if s.get("shotType") == "goal" else ("SavedShot" if s.get("shotType") == "save" else ("Block" if s.get("shotType") == "block" else "Miss"))
                                    shots.append({
                                        "x": s.get("playerCoordinates", {}).get("x", 0),
                                        "y": s.get("playerCoordinates", {}).get("y", 0),
                                        "xg": s.get("xg", 0.0),
                                        "shot_type": stype
                                    })
                    img_b64 = generate_custom_player_shotmap(player_name, team_name, shots, scope_label, player_id=player_id, num_matches=len(target_events))
                    return {"type": "photo", "b64": img_b64, "caption": f"⚽ <b>Player Shot Map</b> for <b>{player_name}</b> ({team_name})\nScope: {scope_label}\nShots taken: {len(shots)} | Goals: {len([x for x in shots if x['shot_type'] == 'Goal'])}"}
                    
                elif chart_type == "saves":
                    saves = []
                    for ev in target_events:
                        ev_id = ev["id"]
                        sm_url = f"https://api.sofascore.com/api/v1/event/{ev_id}/shotmap"
                        resp_sm = requests.get(sm_url, impersonate="chrome124", timeout=8)
                        if resp_sm.status_code == 200:
                            for s in resp_sm.json().get("shotmap", []):
                                is_home_shot = s.get("isHome")
                                shot_type = s.get("shotType")
                                ev_home_id = ev.get("homeTeam", {}).get("id")
                                is_our_gk_facing = (ev_home_id == team_id and not is_home_shot) or (ev_home_id != team_id and is_home_shot)
                                if is_our_gk_facing and shot_type in ["save", "goal"]:
                                    saves.append({
                                        "y": s.get("goalMouthCoordinates", {}).get("y", 50),
                                        "z": s.get("goalMouthCoordinates", {}).get("z", 0),
                                        "outcome": "Goal" if shot_type == "goal" else "Saved",
                                        "xgot": s.get("xgot", 0.0)
                                    })
                    img_b64 = generate_goalkeeper_saves_map(player_name, team_name, saves, scope_label, player_id=player_id)
                    return {"type": "photo", "b64": img_b64, "caption": f"🧤 <b>Goalkeeper Saves Map</b> for <b>{player_name}</b> ({team_name})\nScope: {scope_label}\nSaves plotted: {len([x for x in saves if x['outcome'] == 'Saved'])} | Conceded: {len([x for x in saves if x['outcome'] == 'Goal'])}"}
                    
                elif chart_type == "passmap":
                    points = []
                    total_passes = 0
                    accurate_passes = 0
                    key_passes = 0
                    total_long_balls = 0
                    accurate_long_balls = 0
                    total_crosses = 0
                    accurate_crosses = 0
                    
                    for ev in target_events:
                        ev_id = ev["id"]
                        
                        # 1. Fetch Heatmap points for start coordinates
                        hm_url = f"https://api.sofascore.com/api/v1/event/{ev_id}/player/{player_id}/heatmap"
                        resp_hm = requests.get(hm_url, impersonate="chrome124", timeout=8)
                        if resp_hm.status_code == 200:
                            points.extend(resp_hm.json().get("heatmap", []))
                            
                        # 2. Fetch Player Statistics for exact pass numbers
                        stats_url = f"https://api.sofascore.com/api/v1/event/{ev_id}/player/{player_id}/statistics"
                        resp_stats = requests.get(stats_url, impersonate="chrome124", timeout=8)
                        if resp_stats.status_code == 200:
                            stats_data = resp_stats.json().get("statistics", {})
                            
                            total_passes += int(stats_data.get("totalPass", 0))
                            accurate_passes += int(stats_data.get("accuratePass", 0))
                            key_passes += int(stats_data.get("keyPass", 0))
                            total_long_balls += int(stats_data.get("totalLongBalls", 0))
                            accurate_long_balls += int(stats_data.get("accurateLongBalls", 0))
                            total_crosses += int(stats_data.get("totalCrosses", 0))
                            accurate_crosses += int(stats_data.get("accurateCrosses", 0))
                            
                    tournament_name = "Tournament"
                    if target_events:
                        tournament_name = target_events[0].get("tournament", {}).get("name", "Tournament")
                        
                    img_b64 = generate_custom_player_passmap(
                        player_name, team_name, points, scope_label,
                        player_id=player_id, num_matches=len(target_events),
                        total_passes=total_passes, accurate_passes=accurate_passes,
                        key_passes=key_passes, total_long_balls=total_long_balls,
                        accurate_long_balls=accurate_long_balls, total_crosses=total_crosses,
                        accurate_crosses=accurate_crosses, tournament=tournament_name
                    )
                    
                    pass_pct = (accurate_passes / total_passes * 100.0) if total_passes > 0 else 0.0
                    return {"type": "photo", "b64": img_b64, "caption": f"🎯 <b>Player Passing Map</b> for <b>{player_name}</b> ({team_name})\nScope: {scope_label}\nTournament: {tournament_name}\nPasses: {accurate_passes}/{total_passes} ({pass_pct:.1f}%) | Key Passes: {key_passes}"}
                    
            else: # team
                if chart_type == "shotmap":
                    shots = []
                    for ev in target_events:
                        ev_id = ev["id"]
                        sm_url = f"https://api.sofascore.com/api/v1/event/{ev_id}/shotmap"
                        resp_sm = requests.get(sm_url, impersonate="chrome124", timeout=8)
                        if resp_sm.status_code == 200:
                            for s in resp_sm.json().get("shotmap", []):
                                is_home_shot = s.get("isHome")
                                ev_home_id = ev.get("homeTeam", {}).get("id")
                                is_our_shot = (ev_home_id == team_id and is_home_shot) or (ev_home_id != team_id and not is_home_shot)
                                
                                if is_our_shot:
                                    stype = "Goal" if s.get("shotType") == "goal" else ("SavedShot" if s.get("shotType") == "save" else ("Block" if s.get("shotType") == "block" else "Miss"))
                                    shots.append({
                                        "x": s.get("playerCoordinates", {}).get("x", 0),
                                        "y": s.get("playerCoordinates", {}).get("y", 0),
                                        "xg": s.get("xg", 0.0),
                                        "shot_type": stype
                                    })
                    img_b64 = generate_custom_team_shotmap(team_name, shots, scope_label)
                    return {"type": "photo", "b64": img_b64, "caption": f"🥅 <b>Team Shot Map</b> for <b>{team_name}</b>\nScope: {scope_label}\nShots created: {len(shots)} | Goals scored: {len([x for x in shots if x['shot_type'] == 'Goal'])}"}
                    
                elif chart_type == "territory":
                    points = []
                    for ev in target_events:
                        ev_id = ev["id"]
                        # Fetch all tactical heatmaps to aggregate spatial team control
                        url_t = f"https://api.sofascore.com/api/v1/event/{ev_id}/team/{team_id}/heatmap"
                        resp_t = requests.get(url_t, impersonate="chrome124", timeout=8)
                        if resp_t.status_code == 200:
                            points.extend(resp_t.json().get("heatmap", []))
                    img_b64 = generate_custom_team_territory(team_name, points, scope_label)
                    return {"type": "photo", "b64": img_b64, "caption": f"🗺️ <b>Territory Dominance Map</b> for <b>{team_name}</b>\nScope: {scope_label}\nAggregated touches plotted: {len(points)}"}
                    
                elif chart_type == "flanks":
                    points = []
                    for ev in target_events:
                        ev_id = ev["id"]
                        url_t = f"https://api.sofascore.com/api/v1/event/{ev_id}/team/{team_id}/heatmap"
                        resp_t = requests.get(url_t, impersonate="chrome124", timeout=8)
                        if resp_t.status_code == 200:
                            points.extend(resp_t.json().get("heatmap", []))
                    img_b64 = generate_custom_team_flanks(team_name, points, scope_label)
                    return {"type": "photo", "b64": img_b64, "caption": f"🏹 <b>Attack Focus Flanks</b> for <b>{team_name}</b>\nScope: {scope_label}\nTotal flank actions aggregated: {len(points)}"}
                    
        except Exception as ex:
            logger.error(f"Failed to generate custom chart: {ex}", exc_info=True)
            return None

    res = await asyncio.to_thread(_fetch_and_draw)
    
    await status.delete()
    
    if not res:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ *Failed to generate tactical graphics.* Data coordinates missing for selected matches.")
        return
        
    try:
        photo_bytes = BytesIO(base64.b64decode(res["b64"]))
        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=photo_bytes, caption=res["caption"], parse_mode="HTML")
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ Failed to send graphic: {e}")

async def handle_photo_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Stateful handler to compile premium visual cards instantly upon user photo upload.
    """
    if not update.message or not update.message.photo: return
    
    state = context.user_data.get("custom_state")
    if not state: return
    
    status = await update.message.reply_text("🔄 *Processing image and compiling broadcast-grade graphic...*", parse_mode="Markdown")
    
    try:
        # Download user photo
        photo_file = await context.bot.get_file(update.message.photo[-1].file_id)
        scratch_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scratch")
        os.makedirs(scratch_dir, exist_ok=True)
        img_path = os.path.join(scratch_dir, f"user_upload_{update.effective_user.id}.jpg")
        await photo_file.download_to_drive(img_path)
        
        if state == "quote_waiting_photo":
            q_data = context.user_data.get("quote_data", {})
            
            def _draw_quote():
                return generate_quote_card(q_data["name"], q_data["sub"], q_data["text"], img_path)
                
            img_b64 = await asyncio.to_thread(_draw_quote)
            
            photo_bytes = BytesIO(base64.b64decode(img_b64))
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=photo_bytes,
                caption=f"🎙️ <b>Player/Coach Quote Card</b>\nAuthor: <b>{q_data['name']}</b>",
                parse_mode="HTML"
            )
            
        elif state == "bio_waiting_photo":
            b_data = context.user_data.get("bio_data", {})
            
            def _draw_bio():
                return generate_player_bio_card(b_data["name"], b_data["sub"], b_data["stats"], img_path)
                
            img_b64 = await asyncio.to_thread(_draw_bio)
            
            photo_bytes = BytesIO(base64.b64decode(img_b64))
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=photo_bytes,
                caption=f"👤 <b>Player Bio Stats Card</b>\nPlayer: <b>{b_data['name']}</b>",
                parse_mode="HTML"
            )
            
        elif state == "standings_waiting_photo":
            league_id = context.user_data.get("custom_league_id", 17)
            
            def _draw_standings():
                from curl_cffi import requests
                # Fetch Standing from SofaScore
                s_url = f"https://api.sofascore.com/api/v1/unique-tournament/{league_id}/seasons"
                resp_s = requests.get(s_url, impersonate="chrome124", timeout=10)
                if resp_s.status_code != 200: return None
                seasons = resp_s.json().get("seasons", [])
                if not seasons: return None
                season_id = seasons[0]["id"]
                league_name = seasons[0].get("name", "League")
                
                st_url = f"https://api.sofascore.com/api/v1/unique-tournament/{league_id}/season/{season_id}/standings/total"
                resp_t = requests.get(st_url, impersonate="chrome124", timeout=10)
                if resp_t.status_code != 200: return None
                standings = resp_t.json().get("standings", [])
                if not standings: return None
                rows = standings[0].get("rows", [])
                
                standings_rows = []
                for r in rows:
                    standings_rows.append({
                        "position": r.get("position"),
                        "team_name": r.get("team", {}).get("name"),
                        "played": r.get("played"),
                        "gd": r.get("gd"),
                        "points": r.get("points")
                    })
                return generate_league_standings_card(league_name, standings_rows, img_path)
                
            img_b64 = await asyncio.to_thread(_draw_standings)
            
            if img_b64:
                photo_bytes = BytesIO(base64.b64decode(img_b64))
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=photo_bytes,
                    caption=f"🏆 <b>League Standings Leaderboard Card</b>",
                    parse_mode="HTML"
                )
            else:
                await update.message.reply_text("❌ *Failed to fetch live standings data from SofaScore.*")
                
        elif state == "standings_round_range_waiting_photo":
            st_build = context.user_data.get("st_build", {})
            league_id = st_build.get("league_id", 17)
            season_id = st_build.get("season_id", 76986)
            start_round = st_build.get("start_round", 1)
            end_round = st_build.get("end_round", 5)
            league_name = st_build.get("league_name", "League")
            season_name = st_build.get("season_name", "2025/2026")
            
            def _draw_round_range_standings():
                rows = _fetch_and_calculate_standings(league_id, season_id, start_round, end_round)
                return generate_league_standings_round_range_card(
                    league_name=league_name,
                    season_name=season_name,
                    standings_rows=rows,
                    user_image_path=img_path,
                    start_round=start_round,
                    end_round=end_round
                )
                
            img_b64 = await asyncio.to_thread(_draw_round_range_standings)
            
            if img_b64:
                photo_bytes = BytesIO(base64.b64decode(img_b64))
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=photo_bytes,
                    caption=f"🏆 <b>Custom League Standings Card</b>\nLeague: <b>{league_name}</b>\nRange: <b>Rounds {start_round} to {end_round}</b> ({season_name})",
                    parse_mode="HTML"
                )
            else:
                await update.message.reply_text("❌ *Failed to fetch match rounds or calculate standings.*")
                
        # Clean up files & states
        try:
            if os.path.exists(img_path): os.remove(img_path)
        except: pass
        context.user_data["custom_state"] = None
        await status.delete()
        
    except Exception as e:
        logger.error(f"Image compilation failed: {e}", exc_info=True)
        await update.message.reply_text(f"❌ *Failed to compile card:* {str(e)}")
        await status.delete()

# ── Custom Standings Taxonomy & Wizard Callback Queries ──────────────────────

STANDINGS_GEOGRAPHY = {
    "europe": {
        "label": "🌍 Europe",
        "countries": {
            "england": {
                "label": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 England",
                "leagues": [
                    {"name": "Premier League", "id": 17, "label": "🥇 Premier League"},
                    {"name": "Championship", "id": 18, "label": "🥈 Championship"}
                ]
            },
            "spain": {
                "label": "🇪🇸 Spain",
                "leagues": [
                    {"name": "La Liga", "id": 8, "label": "🥇 La Liga"},
                    {"name": "Segunda División", "id": 54, "label": "🥈 Segunda División"}
                ]
            },
            "italy": {
                "label": "🇮🇹 Italy",
                "leagues": [
                    {"name": "Serie A", "id": 23, "label": "🥇 Serie A"},
                    {"name": "Serie B", "id": 53, "label": "🥈 Serie B"}
                ]
            },
            "germany": {
                "label": "🇩🇪 Germany",
                "leagues": [
                    {"name": "Bundesliga", "id": 35, "label": "🥇 Bundesliga"},
                    {"name": "2. Bundesliga", "id": 44, "label": "🥈 2. Bundesliga"}
                ]
            },
            "france": {
                "label": "🇫🇷 France",
                "leagues": [
                    {"name": "Ligue 1", "id": 34, "label": "🥇 Ligue 1"}
                ]
            },
            "portugal": {
                "label": "🇵🇹 Portugal",
                "leagues": [
                    {"name": "Primeira Liga", "id": 238, "label": "🥇 Primeira Liga"}
                ]
            },
            "netherlands": {
                "label": "🇳🇱 Netherlands",
                "leagues": [
                    {"name": "Eredivisie", "id": 37, "label": "🥇 Eredivisie"}
                ]
            }
        }
    },
    "southamerica": {
        "label": "🌎 South America",
        "countries": {
            "brazil": {
                "label": "🇧🇷 Brazil",
                "leagues": [
                    {"name": "Brasileirão Série A", "id": 325, "label": "🥇 Brasileirão Série A"}
                ]
            },
            "argentina": {
                "label": "🇦🇷 Argentina",
                "leagues": [
                    {"name": "Liga Profesional", "id": 155, "label": "🥇 Liga Profesional"}
                ]
            }
        }
    },
    "asia": {
        "label": "🌏 Asia",
        "countries": {
            "saudi": {
                "label": "🇸🇦 Saudi Arabia",
                "leagues": [
                    {"name": "Saudi Pro League", "id": 350, "label": "🥇 Saudi Pro League"}
                ]
            },
            "qatar": {
                "label": "🇶🇦 Qatar",
                "leagues": [
                    {"name": "Stars League", "id": 939, "label": "🥇 Stars League"}
                ]
            },
            "uae": {
                "label": "🇦🇪 UAE",
                "leagues": [
                    {"name": "Pro League", "id": 955, "label": "🥇 Pro League"}
                ]
            }
        }
    },
    "africa": {
        "label": "🌍 Africa",
        "countries": {
            "egypt": {
                "label": "🇪🇬 Egypt",
                "leagues": [
                    {"name": "Egyptian Premier League", "id": 1047, "label": "🥇 Premier League"}
                ]
            },
            "morocco": {
                "label": "🇲🇦 Morocco",
                "leagues": [
                    {"name": "Botola Pro", "id": 1098, "label": "🥇 Botola Pro"}
                ]
            }
        }
    },
    "northamerica": {
        "label": "🌎 North America",
        "countries": {
            "usa": {
                "label": "🇺🇸 USA",
                "leagues": [
                    {"name": "MLS", "id": 242, "label": "🥇 Major League Soccer"}
                ]
            },
            "mexico": {
                "label": "🇲🇽 Mexico",
                "leagues": [
                    {"name": "Liga MX", "id": 251, "label": "🥇 Liga MX"}
                ]
            }
        }
    },
    "intl": {
        "label": "🏆 Cup / International",
        "countries": {
            "intl": {
                "label": "🏆 Cups",
                "leagues": [
                    {"name": "UEFA Champions League", "id": 17, "label": "🏆 Champions League (Scraping ID)"},
                    {"name": "UEFA Europa League", "id": 679, "label": "🏅 Europa League"}
                ]
            }
        }
    }
}

def _fetch_and_calculate_standings(league_id: int, season_id: int, start_round: int, end_round: int) -> list:
    from curl_cffi import requests
    standings = {}

    for r in range(start_round, end_round + 1):
        url = f"https://api.sofascore.com/api/v1/unique-tournament/{league_id}/season/{season_id}/events/round/{r}"
        resp = requests.get(url, impersonate="chrome124", timeout=10)
        if resp.status_code != 200:
            logger.warning(f"Failed to fetch round {r} matches: status {resp.status_code}")
            continue
        events = resp.json().get("events", [])
        for ev in events:
            if ev.get("status", {}).get("type") != "finished":
                continue

            home_obj  = ev.get("homeTeam", {})
            away_obj  = ev.get("awayTeam", {})
            home_team = home_obj.get("name")
            away_team = away_obj.get("name")

            # Initialize team if not in standings — capture team_id for logo fetching
            for team, obj in [(home_team, home_obj), (away_team, away_obj)]:
                if team not in standings:
                    standings[team] = {
                        "team_id":   obj.get("id"),
                        "short_name": obj.get("shortName") or obj.get("name", team),
                        "played": 0, "won": 0, "drawn": 0, "lost": 0,
                        "gf": 0, "ga": 0, "gd": 0, "points": 0
                    }

            home_score = ev.get("homeScore", {}).get("current", 0)
            away_score = ev.get("awayScore", {}).get("current", 0)

            standings[home_team]["played"] += 1
            standings[away_team]["played"] += 1
            standings[home_team]["gf"] += home_score
            standings[home_team]["ga"] += away_score
            standings[away_team]["gf"] += away_score
            standings[away_team]["ga"] += home_score

            if home_score > away_score:
                standings[home_team]["won"]    += 1
                standings[home_team]["points"] += 3
                standings[away_team]["lost"]   += 1
            elif home_score < away_score:
                standings[away_team]["won"]    += 1
                standings[away_team]["points"] += 3
                standings[home_team]["lost"]   += 1
            else:
                standings[home_team]["drawn"]  += 1
                standings[home_team]["points"] += 1
                standings[away_team]["drawn"]  += 1
                standings[away_team]["points"] += 1

    # Convert to sorted list
    standings_list = []
    for team, stats in standings.items():
        stats["gd"]        = stats["gf"] - stats["ga"]
        stats["team_name"] = team
        standings_list.append(stats)

    # Sort: 1. Points (desc), 2. GD (desc), 3. GF (desc)
    standings_list.sort(key=lambda x: (x["points"], x["gd"], x["gf"]), reverse=True)

    # Add position rank
    for idx, stats in enumerate(standings_list):
        stats["position"] = idx + 1

    return standings_list


async def handle_standings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data
    await q.answer()
    
    import asyncio
    
    if data == "cust_st_start":
        context.user_data["st_build"] = {}
        
        msg = (
            "🏆 *Custom Standings by Round Range*\n\n"
            "Generate a professional, Opta-style standings table for a custom range of match rounds and overlay it on your preferred photo.\n\n"
            "Select a **Continent** to begin:"
        )
        buttons = [
            [
                InlineKeyboardButton("🌍 Europe", callback_data="cust_st_cont_europe"),
                InlineKeyboardButton("🌎 South America", callback_data="cust_st_cont_southamerica")
            ],
            [
                InlineKeyboardButton("🌏 Asia", callback_data="cust_st_cont_asia"),
                InlineKeyboardButton("🌍 Africa", callback_data="cust_st_cont_africa")
            ],
            [
                InlineKeyboardButton("🌎 North America", callback_data="cust_st_cont_northamerica"),
                InlineKeyboardButton("🏆 International / Cups", callback_data="cust_st_cont_intl")
            ],
            [
                InlineKeyboardButton("⚡ Instant Test: EPL 25/26 (Rounds 1-5)", callback_data="cust_st_test")
            ],
            [InlineKeyboardButton("🔙 Back to Custom Menu", callback_data="cust_home")]
        ]
        await q.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")
        return
        
    elif data == "cust_st_test":
        status = await q.edit_message_text(
            "🚀 *Running Standings Calculation Engine for EPL 25/26 (Rounds 1–5)...*\n"
            "Fetching SofaScore events and calculating live points...", 
            parse_mode="Markdown"
        )
        
        # EPL 2025/26
        league_id = 17
        season_id = 76986
        start_round = 1
        end_round = 5
        league_name = "English Premier League"
        season_name = "2025/2026"
        
        def _fetch_and_draw_test():
            rows = _fetch_and_calculate_standings(league_id, season_id, start_round, end_round)
            forlan_path = r"C:\D\Bot Tele\PepBielsa\assets\Forlan.jpg"
            return generate_league_standings_round_range_card(
                league_name=league_name,
                season_name=season_name,
                standings_rows=rows,
                user_image_path=forlan_path,
                start_round=start_round,
                end_round=end_round
            )
            
        try:
            img_b64 = await asyncio.to_thread(_fetch_and_draw_test)
            if img_b64:
                photo_bytes = BytesIO(base64.b64decode(img_b64))
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=photo_bytes,
                    caption=f"🏆 <b>EPL Standings Card (Rounds 1-5)</b>\nGenerated successfully in Opta Style!",
                    parse_mode="HTML"
                )
                await status.delete()
            else:
                await status.edit_text("❌ Failed to generate test standings card.")
        except Exception as e:
            logger.error(f"EPL standings test failed: {e}", exc_info=True)
            await status.edit_text(f"❌ Error: {e}")
        return

    elif data.startswith("cust_st_cont_"):
        cont = data.split("_")[3]
        if cont not in STANDINGS_GEOGRAPHY:
            await q.edit_message_text("⚠️ Invalid selection.")
            return
            
        context.user_data["st_build"] = {"continent": cont}
        
        msg = f"🌍 *Select a Country in {STANDINGS_GEOGRAPHY[cont]['label']}:*"
        buttons = []
        countries = STANDINGS_GEOGRAPHY[cont]["countries"]
        keys = list(countries.keys())
        for i in range(0, len(keys), 2):
            row = []
            row.append(InlineKeyboardButton(countries[keys[i]]["label"], callback_data=f"cust_st_coun_{keys[i]}"))
            if i + 1 < len(keys):
                row.append(InlineKeyboardButton(countries[keys[i+1]]["label"], callback_data=f"cust_st_coun_{keys[i+1]}"))
            buttons.append(row)
            
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data="cust_st_start")])
        await q.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")
        return

    elif data.startswith("cust_st_coun_"):
        coun = data.split("_")[3]
        st_build = context.user_data.get("st_build", {})
        cont = st_build.get("continent", "europe")
        
        if cont not in STANDINGS_GEOGRAPHY or coun not in STANDINGS_GEOGRAPHY[cont]["countries"]:
            await q.edit_message_text("⚠️ Invalid selection.")
            return
            
        st_build["country"] = coun
        context.user_data["st_build"] = st_build
        
        coun_label = STANDINGS_GEOGRAPHY[cont]["countries"][coun]["label"]
        msg = f"🏆 *Select a League in {coun_label}:*"
        buttons = []
        leagues = STANDINGS_GEOGRAPHY[cont]["countries"][coun]["leagues"]
        
        for l in leagues:
            buttons.append([InlineKeyboardButton(l["label"], callback_data=f"cust_st_league_{l['id']}")])
            
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"cust_st_cont_{cont}")])
        await q.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")
        return

    elif data.startswith("cust_st_league_"):
        parts = data.split("_")
        league_id = int(parts[3])
        st_build = context.user_data.get("st_build", {})
        st_build["league_id"] = league_id
        
        found_league = None
        for cont_val in STANDINGS_GEOGRAPHY.values():
            for coun_val in cont_val["countries"].values():
                for l in coun_val["leagues"]:
                    if l["id"] == league_id:
                        found_league = l
                        break
        
        league_name = found_league["name"] if found_league else "League"
        st_build["league_name"] = league_name
        context.user_data["st_build"] = st_build
        
        status = await q.edit_message_text("🔄 *Fetching available seasons from SofaScore...*", parse_mode="Markdown")
        
        def _fetch_seasons():
            from curl_cffi import requests
            url = f"https://api.sofascore.com/api/v1/unique-tournament/{league_id}/seasons"
            resp = requests.get(url, impersonate="chrome124", timeout=10)
            if resp.status_code != 200: return []
            return resp.json().get("seasons", [])
            
        seasons = await asyncio.to_thread(_fetch_seasons)
        if not seasons:
            await status.edit_text("❌ *Failed to fetch tournament seasons.* Please try again.", 
                                   reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Start", callback_data="cust_st_start")]]))
            return
            
        seasons_map = {str(s["id"]): s["name"] for s in seasons}
        context.user_data["st_seasons"] = seasons_map
        
        msg = f"📅 *Select Season for {league_name}:*"
        buttons = []
        for s in seasons[:4]:
            buttons.append([InlineKeyboardButton(s["name"], callback_data=f"cust_st_season_{s['id']}")])
            
        buttons.append([InlineKeyboardButton("🔙 Back to Start", callback_data="cust_st_start")])
        await status.edit_text(msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")
        return

    elif data.startswith("cust_st_season_"):
        season_id = int(data.split("_")[3])
        st_build = context.user_data.get("st_build", {})
        st_build["season_id"] = season_id
        
        seasons_map = context.user_data.get("st_seasons", {})
        season_name = seasons_map.get(str(season_id), "Season")
        st_build["season_name"] = season_name
        context.user_data["st_build"] = st_build
        
        league_id = st_build["league_id"]
        
        status = await q.edit_message_text("🔄 *Fetching match rounds from SofaScore...*", parse_mode="Markdown")
        
        def _fetch_rounds():
            from curl_cffi import requests
            url = f"https://api.sofascore.com/api/v1/unique-tournament/{league_id}/season/{season_id}/rounds"
            resp = requests.get(url, impersonate="chrome124", timeout=10)
            if resp.status_code != 200: return []
            return resp.json().get("rounds", [])
            
        rounds = await asyncio.to_thread(_fetch_rounds)
        if not rounds:
            await status.edit_text("❌ *Failed to fetch match rounds.* Please try again.", 
                                   reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Start", callback_data="cust_st_start")]]))
            return
            
        max_round = max(r.get("round", 1) for r in rounds)
        st_build["max_round"] = max_round
        context.user_data["st_build"] = st_build
        
        msg = "🔢 *Select Start Round:* \nChoose the starting gameweek for standings range:"
        buttons = []
        row = []
        for r in range(1, max_round + 1):
            row.append(InlineKeyboardButton(str(r), callback_data=f"cust_st_sr_{r}"))
            if len(row) == 5:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
            
        buttons.append([InlineKeyboardButton("🔙 Back to Start", callback_data="cust_st_start")])
        await status.edit_text(msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")
        return

    elif data.startswith("cust_st_sr_"):
        start_round = int(data.split("_")[3])
        st_build = context.user_data.get("st_build", {})
        st_build["start_round"] = start_round
        context.user_data["st_build"] = st_build
        
        max_round = st_build.get("max_round", 38)
        
        msg = "🔢 *Select End Round:* \nChoose the ending gameweek for standings range:"
        buttons = []
        row = []
        for r in range(start_round, max_round + 1):
            row.append(InlineKeyboardButton(str(r), callback_data=f"cust_st_er_{r}"))
            if len(row) == 5:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
            
        buttons.append([InlineKeyboardButton("🔙 Back to Start", callback_data="cust_st_start")])
        await q.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")
        return

    elif data.startswith("cust_st_er_"):
        end_round = int(data.split("_")[3])
        st_build = context.user_data.get("st_build", {})
        st_build["end_round"] = end_round
        context.user_data["st_build"] = st_build
        
        context.user_data["custom_state"] = "standings_round_range_waiting_photo"
        
        msg = (
            f"🏆 *Round Range Locked: Rounds {st_build['start_round']} to {end_round}!*\n\n"
            "📸 *Please send the photo you want to use as a background.* I will crop and overlay the standings on the right side of the photo in premium Opta style!"
        )
        await q.edit_message_text(msg, parse_mode="Markdown")
        return

async def handle_custom_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data
    
    if data == "cust_home":
        await custom_drawing_start(update, context)
    elif data.startswith("cust_st_"):
        await handle_standings_callback(update, context)
    elif data.startswith("cust_co_"):
        await custom_country_selected(update, context)
    elif data.startswith("cust_le_"):
        await custom_league_selected(update, context)
    elif data.startswith("cust_te_"):
        await custom_team_selected(update, context)
    elif data.startswith("cust_opt_"):
        await custom_option_selected(update, context)
    elif data.startswith("cust_pos_"):
        await custom_player_list(update, context)
    elif data.startswith("cust_pl_"):
        await custom_player_options(update, context)
    elif data.startswith("cust_ch_"):
        await custom_chart_selected(update, context)
    elif data.startswith("cust_sc_"):
        await custom_generate_chart(update, context)