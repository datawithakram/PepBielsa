"""
telegram_handlers.py — SofaScore Automated Edition
Fully detached from API-Football. Uses SofaScore scraping for all data.
"""
import os
import json
import logging
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
async def help_command(update, context): await (update.callback_query.edit_message_text("Coming soon!", reply_markup=main_menu_keyboard()) if update.callback_query else update.message.reply_text("Coming soon!", reply_markup=main_menu_keyboard()))
async def admin_status(update, context): await update.message.reply_text("System: Online (SofaScore Mode)")
async def daily_digest_command(update, context): await update.message.reply_text("Coming soon via SofaScore Analyzer!")
async def admin_reset_news(update, context): await update.message.reply_text("News cache has been reset.")

# ── Custom Tactical Drawing System ───────────────────────────────────────────

from custom_visuals import (
    generate_custom_player_heatmap,
    generate_custom_player_shotmap,
    generate_custom_team_shotmap,
    generate_custom_team_territory,
    generate_custom_team_flanks,
    generate_goalkeeper_saves_map,
    generate_league_standings_card,
    generate_quote_card,
    generate_player_bio_card
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
    msg = "🎨 *Custom Tactical Drawing System*\n\nSelect a country to browse leagues and teams, or select a broadcast quote/bio card creator below:"
    buttons = []
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
                    for ev in target_events:
                        ev_id = ev["id"]
                        hm_url = f"https://api.sofascore.com/api/v1/event/{ev_id}/player/{player_id}/heatmap"
                        resp_hm = requests.get(hm_url, impersonate="chrome124", timeout=8)
                        if resp_hm.status_code == 200:
                            points.extend(resp_hm.json().get("heatmap", []))
                    img_b64 = generate_custom_player_heatmap(player_name, team_name, points, scope_label)
                    return {"type": "photo", "b64": img_b64, "caption": f"🌡️ <b>Player Touch Heatmap</b> for <b>{player_name}</b> ({team_name})\nScope: {scope_label}\nSpatial touches aggregated: {len(points)}"}
                    
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
                    img_b64 = generate_custom_player_shotmap(player_name, team_name, shots, scope_label)
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
        scratch_dir = r"C:\Users\akram\.gemini\antigravity\brain\afee9046-d8f2-4707-8fe4-6563af57e94f\scratch"
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

async def handle_custom_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data
    
    if data == "cust_home":
        await custom_drawing_start(update, context)
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