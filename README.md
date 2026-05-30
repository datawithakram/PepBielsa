# ⚽ PepBielsa AI — Elite Football Tactical Intelligence Bot

> A professional-grade Telegram bot that delivers deep tactical analysis, broadcast-quality visuals, and real-time football intelligence — powered by **SofaScore** data and **Gemini AI**.

---

## 🌟 Features

### 1. 📊 Full Match Analysis — 14 Sections
Select any live or finished match and receive an instant 14-section tactical report, each paired with a custom visual:

| # | Section | Visual |
|---|---------|--------|
| 1 | Match Overview + Key Stats | Overview Map |
| 2 | Shot Map Dashboard | Full-pitch shot locations + xG size |
| 3 | xG Flow | Rolling 15-min expected goals chart |
| 4 | Tactical Formations | Lineup with jersey shapes |
| 5 | Goal Mouth Analysis | Frame-accurate shot placement |
| 6 | Assist Map | Key pass arrows to goal |
| 7 | Defensive Rocks | Top defensive performers |
| 8 | Match Performers | Top attackers + ratings |
| 9 | Momentum Index | Dominance over time |
| 10 | Chances & Mistakes | Big chances + errors |
| 11 | Stars of the Match | Best XI with photos |
| 12 | Territory Map | 32-zone pitch dominance heatmap |
| 13 | Passing Networks | Buildup patterns + connections |
| 14 | Attack Zones | Left / Center / Right % breakdown |

### 2. 🎨 Custom Drawing System
Generate on-demand tactical charts for any team or player across 32+ leagues:

- 🌡️ **Player Heatmap** — movement density over 1/5/10 matches
- 🎯 **Player Passing Map** — accurate, key, and long balls
- ⚽ **Player Shot Map** — all shots with xG sizes
- 🧤 **Goalkeeper Saves Map** — frame-accurate save locations
- 🗺️ **Team Territory Map** — 32-zone aggregated dominance
- 🏹 **Team Attack Flanks** — left / center / right % chart
- 🥅 **Team Shot Map** — multi-match aggregated shots

### 3. 🏆 Custom League Standings Cards
Generate Opta-style standings tables overlaid on your own photo:

- **Live standings** — current season snapshot
- **Round-range standings** — any gameweek range (e.g. Rounds 5–15)
- Covers **32+ leagues** across Europe, Asia, Africa, Americas, and International cups

### 4. 🎴 Social Media Cards
Broadcast-grade cards ready for Twitter/Instagram:

- **Quote Card** — Manager/player quote with photo background
- **Player Bio Stats Card** — Season or match stats with player photo
- Uses **Gemini AI Smart Crop** to auto-detect and perfectly frame the subject

### 5. 💬 AI Tactical Q&A
After any analysis, ask the bot anything about the match:
> *"Why did Arsenal's high press stop working in the second half?"*
> *"How did Mbappé beat the offside trap for his second goal?"*

Gemini AI analyzes the full match data and responds like an expert pundit.

### 6. 📰 Smart News Engine
Automatic broadcasts to your Telegram channel:

| Category | Frequency |
|----------|-----------|
| ⚽ General Football | Every 30 min |
| 🔄 Transfers | Every 30 min |
| 🎙️ Press Conferences | Every 30 min |
| 🏥 Injuries | Every 30 min |
| 🚨 Breaking News | Every 10 min |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Interface** | python-telegram-bot 21.x |
| **Data** | SofaScore (curl_cffi scraping) |
| **AI** | Google Gemini 2.5 Flash |
| **Visuals** | matplotlib + mplsoccer + seaborn |
| **Scheduler** | APScheduler via PTB JobQueue |
| **Hosting** | Render.com (free tier) |
| **Uptime** | UptimeRobot ping every 5 min |

---

## 🚀 Quick Start

### Bot Commands
```
/start          — Main menu
/matches        — Today's major matches
/news           — News categories
/transfers      — Transfer news
/injuries       — Injury updates
/breaking       — Breaking alerts
/press          — Press conference summaries
/daily_digest   — Today's match briefing
/custom         — Custom drawing system
/help           — Full command guide
```

### User Flow
1. Send `/start` → tap **Show Matches**
2. Select any live or finished match
3. Wait ~60–90 seconds for the full 14-section report + 14 visuals
4. Ask follow-up questions directly in chat

---

## ⚙️ Configuration

Copy `.env.example` to `.env` and fill in your values:

```env
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
GEMINI_API_KEY=your_gemini_api_key

# News broadcasting (optional)
NEWS_CHANNEL_ID=-100xxxxxxxxxx
ADMIN_CHAT_ID=your_telegram_user_id

# Timing (defaults shown)
NEWS_POLL_MINUTES=30
BREAKING_POLL_MINUTES=10
PORT=10000
```

### Getting API Keys
| Key | Where to get |
|-----|-------------|
| `TELEGRAM_BOT_TOKEN` | [@BotFather](https://t.me/botfather) on Telegram |
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) → Get API Key |
| `NEWS_CHANNEL_ID` | Add bot as admin to channel → [@userinfobot](https://t.me/userinfobot) |
| `ADMIN_CHAT_ID` | [@userinfobot](https://t.me/userinfobot) |

---

## 🌐 Free 24/7 Hosting

Deploy on **Render.com** (free) + **UptimeRobot** (free):

1. Fork/clone this repo → push to your GitHub
2. Create a **Web Service** on [render.com](https://render.com) from your repo
3. Set environment variables in Render dashboard
4. Add a **UptimeRobot** HTTP monitor on `https://your-app.onrender.com/health`

The bot exposes `/health` and `/` endpoints for uptime monitoring.

---

## 📁 Project Structure

```
PepBielsa/
├── telegram_bot.py          # Entry point — bot + health server
├── telegram_handlers.py     # All command & callback handlers
├── keyboard.py              # Inline keyboard layouts
├── visuals.py               # 14 match analysis charts
├── custom_visuals.py        # 9 custom chart types
├── tactical_engine.py       # Tactical data preprocessing
├── ai_analysis.py           # Gemini AI report generation
├── data_aggregator.py       # SofaScore data aggregation
├── daily_digest.py          # Daily briefing generator
├── news_scheduler.py        # APScheduler news jobs
├── feed_fetcher.py          # RSS feed parser
├── news_store.py            # Deduplication store
├── collectors/              # Per-source scrapers
│   ├── sofascore.py
│   ├── fbref.py
│   ├── fotmob.py
│   └── ...
├── app.py                   # Health check web server
├── Procfile                 # Render start command
├── render.yaml              # Render deployment config
├── runtime.txt              # Python 3.11
└── requirements.txt         # Dependencies
```

---

## 📄 License

This project is for educational and personal use. Data is sourced from public football statistics platforms. Not affiliated with SofaScore, Opta, or any official football organization.

---

*"Not just a stats tool — a complete tactical analyst worthy of professional dressing rooms."*