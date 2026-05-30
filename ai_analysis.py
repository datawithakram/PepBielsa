"""
ai_analysis.py — Elite Football Match Analysis Engine
Uses Groq (free, fast) for 14-section reports with Gemini as optional enhancer.
"""
import os
import json
import html
import logging
import time
from typing import List, Dict, Optional, Any

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

PRIMARY_MODEL   = "llama-3.3-70b-versatile"
FALLBACK_MODELS = ["qwen/qwen3-32b", "mixtral-8x7b-32768"]

ANALYST_SYSTEM = (
    "You are an elite football intelligence analyst. Your writing is modelled on Tifo Football, "
    "The Athletic, Coaches' Voice, Opta Analyst, and StatsBomb. "
    "You write with tactical precision, contextual depth, and intelligent storytelling. "
    "Avoid generic clichés. Every sentence must add real analytical value. "
    "Language: English (Formal/Analytical). Tone: professional, intelligent, tactical, concise but insightful."
)

# ─── Lazy Groq client (only created when needed, avoids import-time crash) ─────

_groq_client = None

def _get_groq_client():
    global _groq_client
    if _groq_client is None:
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY environment variable is not set.")
        try:
            from groq import Groq
            _groq_client = Groq(api_key=GROQ_API_KEY)
        except ImportError:
            raise RuntimeError("groq package not installed. Add 'groq' to requirements.txt")
    return _groq_client


# ─── Core LLM wrapper ──────────────────────────────────────────────────────────

def _call_groq(messages: List[Dict], model: str, temperature=0.65,
               max_tokens=1500, retries=2) -> Optional[str]:
    try:
        client = _get_groq_client()
    except RuntimeError as e:
        logger.error(f"Groq client error: {e}")
        return None

    for attempt in range(retries + 1):
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=30,
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Groq attempt {attempt+1} [{model}] failed: {e}")
            if "rate_limit" in str(e).lower():
                time.sleep(6)
            elif "timeout" in str(e).lower():
                time.sleep(3)
            if attempt == retries:
                return None


def groq_complete(prompt: str, system: str = ANALYST_SYSTEM,
                  model: str = PRIMARY_MODEL, max_tokens: int = 1500) -> str:
    messages = [
        {"role": "system", "content": system},
        {"role": "user",   "content": prompt},
    ]
    result = _call_groq(messages, model, max_tokens=max_tokens)
    if result:
        return result
    for fallback in FALLBACK_MODELS:
        result = _call_groq(messages, fallback, max_tokens=max_tokens)
        if result:
            return result
    return "⚠️ Analysis temporarily unavailable. Please try again shortly."


# ─── Context builder ──────────────────────────────────────────────────────────

def _build_context_block(s: Dict) -> str:
    ms   = s.get("match_stats", {})
    ti   = s.get("tactical_intelligence", {})
    fm   = ti.get("formations") or s.get("formations", {})
    lp   = ti.get("lineups_full") or s.get("lineups", {}) or {}
    xg   = ms.get("xg") or s.get("xg", {})
    pas  = ms.get("passing", {})
    poss = ms.get("possession") or s.get("possession", {})
    shts = ms.get("shots") or s.get("shots", {})
    crn  = ms.get("corners") or s.get("corners", {})
    fls  = ms.get("fouls") or s.get("fouls", {})
    svs  = ms.get("saves", {})
    datk = ms.get("dangerous_attacks", {})
    comp = ti.get("defensive_compactness", {})
    prss = ti.get("pressing_intensity", {})
    ph   = pas.get("home", {})
    pa   = pas.get("away", {})
    ev   = s.get("raw_events") or s.get("events") or []

    goals_text = ""
    for incident in ev:
        if incident.get("type") == "goal":
            p = incident.get("player", "Unknown")
            player = p.get("name", "Unknown") if isinstance(p, dict) else str(p)
            minute = incident.get("time") or incident.get("minute", "?")
            team = "Home" if incident.get("isHome") else "Away"
            goals_text += f"  ⚽ {minute}' — {player} ({team})\n"
    if not goals_text:
        goals_text = "  No goals\n"

    def _xi(side_key: str) -> str:
        side = lp.get(side_key, {})
        if not side:
            return "N/A"
        names = []
        for p in side.get("players", [])[:11]:
            if isinstance(p, dict):
                n = (p.get("player") or {}).get("name") if isinstance(p.get("player"), dict) else p.get("name", "")
                if n:
                    names.append(n)
        return ", ".join(names) or "N/A"

    block = f"""
=== MATCH CONTEXT ===
{s.get('home_team','?')} {s.get('home_score',0)} – {s.get('away_score',0)} {s.get('away_team','?')}
League: {s.get('league') or s.get('match_info',{}).get('league','?')} | Venue: {s.get('venue') or s.get('match_info',{}).get('venue','?')}
Formations: {fm.get('home','?')} (Home) vs {fm.get('away','?')} (Away)

HOME XI: {_xi('home')}
AWAY XI: {_xi('away')}

=== GOALS ===
{goals_text}
=== STATISTICS ===
Possession:        Home {poss.get('home',0)}%  |  Away {poss.get('away',0)}%
Total Shots:       Home {shts.get('home',{}).get('total',0)}  |  Away {shts.get('away',{}).get('total',0)}
Shots on Target:   Home {shts.get('home',{}).get('on_target',0)}  |  Away {shts.get('away',{}).get('on_target',0)}
xG:                Home {float(xg.get('home',0)):.2f}  |  Away {float(xg.get('away',0)):.2f}
Pass Accuracy:     Home {round(float(ph.get('accuracy',0)),1)}%  |  Away {round(float(pa.get('accuracy',0)),1)}%
Accurate Passes:   Home {ph.get('accurate',0)}  |  Away {pa.get('accurate',0)}
Corners:           Home {crn.get('home',0)}  |  Away {crn.get('away',0)}
Fouls:             Home {fls.get('home',0)}  |  Away {fls.get('away',0)}
GK Saves:          Home {svs.get('home',0)}  |  Away {svs.get('away',0)}
Dangerous Attacks: Home {datk.get('home',0)}  |  Away {datk.get('away',0)}

=== TACTICAL METRICS ===
Defensive Compactness: Home {comp.get('home','N/A')}  |  Away {comp.get('away','N/A')}
Pressing Intensity:    Home {prss.get('home','N/A')}  |  Away {prss.get('away','N/A')}
Field Tilt:            {ti.get('field_tilt',50)}%
"""
    return block.strip()


# ─── Report section builders ──────────────────────────────────────────────────

def _section(title: str, instruction: str, context: str, max_tokens: int = 500) -> str:
    prompt = f"""
{context}

=== YOUR TASK ===
Write SECTION: {title} in formal English.

Instructions:
{instruction}

Rules:
- Write in formal, analytical English.
- No generic football clichés.
- Every observation must be grounded in the data above.
- Write like an elite analyst (Tifo/Athletic/Opta style).
- Professional and analytical tone.
"""
    return groq_complete(prompt, max_tokens=max_tokens)


def generate_full_match_report(tactical_summary: Dict) -> Dict[str, str]:
    ctx = _build_context_block(tactical_summary)
    home = tactical_summary.get("home_team", "Home")
    away = tactical_summary.get("away_team", "Away")
    hs   = tactical_summary.get("home_score", 0)
    as_  = tactical_summary.get("away_score", 0)
    winner = home if hs > as_ else (away if as_ > hs else None)

    report = {}
    report["match_overview"]             = _section("1. MATCH OVERVIEW", "Summarize final result, flow, tactical context, and rhythm.", ctx)
    win_label = "2. WHY DID THE TEAM WIN?" if winner else "2. WHY WAS IT A DRAW?"
    report["why_team_won"]               = _section(win_label, "Explain key tactical reasons for the result.", ctx)
    report["result_fairness"]            = _section("3. WAS THE RESULT FAIR?", "Analyze xG and shot quality.", ctx)
    report["tactical_analysis"]          = _section("4. TACTICAL ANALYSIS", "Deep tactical analysis for BOTH teams.", ctx, max_tokens=800)
    report["team_strengths"]             = _section("5. TEAM STRENGTHS", "Identify strongest mechanisms for both teams.", ctx)
    report["team_weaknesses"]            = _section("6. TEAM WEAKNESSES", "Identify tactical gaps for both teams.", ctx)
    report["performance_analysis"]       = _section("7. PERFORMANCE ANALYSIS", "Evaluate overall performance level.", ctx)
    report["stats_interpretation"]       = _section("8. STATISTICS INTERPRETATION", "Explain what the numbers actually mean.", ctx)
    report["turning_points"]             = _section("9. MATCH TURNING POINTS", "Identify key moments and shifts.", ctx)
    report["match_mistakes"]             = _section("10. MATCH MISTAKES", "Analyze key tactical errors.", ctx)
    report["best_worst_player"]          = _section("11. BEST AND WORST PLAYER", "Determine best/worst based on tactical impact.", ctx)
    report["alternative_match_scenario"] = _section("12. ALTERNATIVE MATCH SCENARIO", "Generate tactical 'what-if' analysis.", ctx)
    report["next_match_prediction"]      = _section("13. NEXT MATCH PREDICTION", "Tactical forecasting for future matches.", ctx)
    report["professional_conclusion"]    = _section("14. PROFESSIONAL CONCLUSION", "Exactly 3 concise professional bullet points.", ctx, max_tokens=300)
    return report


# ─── Telegram formatting ──────────────────────────────────────────────────────

def _esc(text: str) -> str:
    if not text:
        return ""
    return html.escape(str(text))


def format_report_for_telegram(report: Dict[str, str], tactical_summary: Dict) -> List[str]:
    home = _esc(tactical_summary.get("home_team", "Home"))
    away = _esc(tactical_summary.get("away_team", "Away"))
    hs   = _esc(str(tactical_summary.get("home_score", 0)))
    as_  = _esc(str(tactical_summary.get("away_score", 0)))

    section_labels = {
        "match_overview":             "1. MATCH OVERVIEW",
        "why_team_won":               "2. WHY DID THE TEAM WIN?",
        "result_fairness":            "3. WAS THE RESULT FAIR?",
        "tactical_analysis":          "4. TACTICAL ANALYSIS",
        "team_strengths":             "5. TEAM STRENGTHS",
        "team_weaknesses":            "6. TEAM WEAKNESSES",
        "performance_analysis":       "7. PERFORMANCE ANALYSIS",
        "stats_interpretation":       "8. STATISTICS INTERPRETATION",
        "turning_points":             "9. MATCH TURNING POINTS",
        "match_mistakes":             "10. MATCH MISTAKES",
        "best_worst_player":          "11. BEST AND WORST PLAYER",
        "alternative_match_scenario": "12. ALTERNATIVE MATCH SCENARIO",
        "next_match_prediction":      "13. NEXT MATCH PREDICTION",
        "professional_conclusion":    "14. PROFESSIONAL CONCLUSION",
    }

    header = (
        f"\U0001f4cb <b>Elite Tactical Intelligence Report</b>\n"
        f"\u26bd <b>{home} {hs} \u2014 {as_} {away}</b>\n"
        f"\u2500" * 26
    )
    messages = [header]

    for key, label in section_labels.items():
        content = report.get(key, "")
        if content:
            msg = (
                f"<b>{'='*32}</b>\n"
                f"<b>{label}</b>\n"
                f"<b>{'='*32}</b>\n\n"
                f"{_esc(content)}"
            )
            messages.append(msg)

    return messages


# ─── Utility functions ────────────────────────────────────────────────────────

def generate_social_insights(tactical_summary: Dict) -> List[str]:
    ctx = _build_context_block(tactical_summary)
    prompt = f"{ctx}\n\nGenerate 5 punchy tactical insights in formal English. One sentence each."
    resp = groq_complete(prompt, max_tokens=400)
    return [line.strip("-• ") for line in resp.split("\n") if line.strip()][:5]


def generate_telegram_summary(tactical_summary: Dict) -> str:
    ctx = _build_context_block(tactical_summary)
    prompt = f"{ctx}\n\nWrite a professional tactical summary in formal English. Max 200 words."
    return groq_complete(prompt, max_tokens=400)


def answer_followup(question: str, match_context: Dict) -> str:
    ctx = _build_context_block(match_context)
    prompt = f"{ctx}\n\nQuestion: {question}\n\nAnswer in formal English as a professional tactical analyst."
    return groq_complete(prompt, max_tokens=400)


def summarize_news(text: str) -> Dict[str, str]:
    """Summarize a news article and extract tactical implication."""
    prompt = (
        f"News: {text[:500]}\n\n"
        "Return JSON with keys: 'summary' (1 sentence) and 'tactical_implication' (1 sentence)."
    )
    resp = groq_complete(prompt, max_tokens=150)
    try:
        return json.loads(resp)
    except Exception:
        return {"summary": text[:200], "tactical_implication": ""}


# ─── Backward compatibility ───────────────────────────────────────────────────

def generate_tactical_report(tactical_summary: Dict, team_focus: str = None) -> str:
    report = generate_full_match_report(tactical_summary)
    combined = [f"*{k}*\n{v}" for k, v in report.items()]
    return "\n\n".join(combined)


def generate_daily_briefing(matches: List[Dict], news_titles: List[str]) -> str:
    """Generate a daily briefing from matches and news headlines."""
    match_lines = "\n".join(
        f"- {m.get('home','?')} vs {m.get('away','?')} ({m.get('league','')})"
        for m in matches[:8]
    ) or "No major matches today."
    news_lines = "\n".join(f"- {t}" for t in news_titles[:6]) or "No headlines available."
    prompt = (
        f"Today's Matches:\n{match_lines}\n\n"
        f"Latest Headlines:\n{news_lines}\n\n"
        "Write a brief, professional daily football digest in 3-4 sentences."
    )
    return groq_complete(prompt, max_tokens=300)