"""
AI Tactical Analysis Layer – Groq LLM integration with fallback.
"""
import os
import json
import logging
from typing import List, Dict, Optional, Any
import groq
from groq import Groq
import time

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

PRIMARY_MODEL = "llama-3.3-70b-versatile"
FALLBACK_MODELS = ["qwen/qwen3-32b", "mixtral-8x7b-32768"]

def _call_groq(messages: List[Dict], model: str, temperature=0.7, max_tokens=1024, retries=2) -> Optional[str]:
    """Internal Groq call with retry and timeout."""
    for attempt in range(retries + 1):
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=20
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Groq attempt {attempt+1} failed: {e}")
            if "rate_limit" in str(e).lower():
                time.sleep(5)
            elif "timeout" in str(e).lower():
                time.sleep(2)
            if attempt == retries:
                return None

def groq_complete(prompt: str, system: str = "You are a professional football tactical analyst.", model=PRIMARY_MODEL, max_tokens=1024) -> str:
    """Main completion function with model fallback."""
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt}
    ]
    # Try primary
    result = _call_groq(messages, model, max_tokens=max_tokens)
    if result:
        return result
    logger.warning(f"Primary model {model} failed, trying fallbacks.")
    for fallback in FALLBACK_MODELS:
        result = _call_groq(messages, fallback, max_tokens=max_tokens)
        if result:
            return result
    raise Exception("All Groq models failed.")

def generate_tactical_report(tactical_summary: Dict, team_focus: str = None) -> str:
    """Generate a professional tactical analysis report using tactical engine summary."""
    # Build a concise prompt
    team_names = f"{tactical_summary['home_team']} vs {tactical_summary['away_team']}"
    prompt = f"""
Match: {team_names}
Score: {tactical_summary['home_score']} - {tactical_summary['away_score']}
Stats:
- Possession: Home {tactical_summary['possession']['home']}% - Away {tactical_summary['possession']['away']}%
- Shots (on target): Home {tactical_summary['shots']['home']['total']} ({tactical_summary['shots']['home']['on_target']}) - Away {tactical_summary['shots']['away']['total']} ({tactical_summary['shots']['away']['on_target']})
- Corners: Home {tactical_summary['corners']['home']} - Away {tactical_summary['corners']['away']}
- Fouls: Home {tactical_summary['fouls']['home']} - Away {tactical_summary['fouls']['away']}
- Offsides: Home {tactical_summary['offsides']['home']} - Away {tactical_summary['offsides']['away']}

Tactical Metrics:
- Defensive Compactness (1=low shots on target conceded): Home {tactical_summary['tactical_metrics']['defensive_compactness']['home']} - Away {tactical_summary['tactical_metrics']['defensive_compactness']['away']}
- Momentum Index (positive favours home): {tactical_summary['tactical_metrics']['momentum_index']}
- Build-up Efficiency (shots per possession %): Home {tactical_summary['tactical_metrics']['buildup_efficiency']['home']} - Away {tactical_summary['tactical_metrics']['buildup_efficiency']['away']}
- Width Usage (offside frequency): Home {tactical_summary['tactical_metrics']['width_usage']['home']} - Away {tactical_summary['tactical_metrics']['width_usage']['away']}
- Shot Quality (on target rate): Home {tactical_summary['tactical_metrics']['shot_quality']['home']} - Away {tactical_summary['tactical_metrics']['shot_quality']['away']}

Write a professional, concise tactical report in English covering: pressing analysis, build-up structure, defensive transition, half-space occupation (infer from data), tactical strengths/weaknesses, tactical adjustments, and coaching recommendations. Use Opta/Smartbomb style. Keep under 500 words.
"""
    return groq_complete(prompt, system="You are an elite football tactics analyst. Write like The Athletic or Tifo Football.", max_tokens=700)

def generate_social_insights(tactical_summary: Dict) -> List[str]:
    """Generate 3-5 concise, shareable tactical insights."""
    prompt = f"""
Based on match stats:
{json.dumps(tactical_summary, indent=2)}
Generate 3 to 5 short, punchy tactical insights suitable for Twitter/social media. Each must be a single sentence, professional, and highlight key tactical points. Example: "Arsenal allowed 14 progressive carries through the left half-space." Return as a JSON list of strings.
"""
    resp = groq_complete(prompt, system="You are a football analytics social media expert.", max_tokens=300)
    try:
        insights = json.loads(resp)
        if isinstance(insights, list):
            return insights
    except:
        # fallback parsing
        lines = [l.strip("-• ") for l in resp.split("\n") if l.strip()]
        return lines[:5]
    return []

def answer_followup(question: str, match_context: Dict) -> str:
    """Answer a tactical follow-up question using previously stored match context."""
    prompt = f"""
Previous match context:
{json.dumps(match_context, indent=2)}

Question: {question}

Answer as a professional tactical analyst. Be concise, specific, and use football terminology.
"""
    return groq_complete(prompt, system="You are a football tactical expert answering a follow-up question.", max_tokens=350)

def summarize_news(article_text: str) -> Dict:
    """Summarize football news and extract tactical implications."""
    prompt = f"""
Summarize this football news article and extract the tactical implications for the team(s). Output JSON with keys: "summary" (concise 2-sentence summary), "tactical_implication" (one sentence tactical impact). Article:
{article_text[:2000]}
"""
    resp = groq_complete(prompt, system="You are a football intelligence analyst.", max_tokens=250)
    try:
        return json.loads(resp)
    except:
        return {"summary": resp, "tactical_implication": "Unclear."}

def generate_daily_briefing(matches: List[Dict], news: List[str]) -> str:
    """Create daily football intelligence digest."""
    match_text = "\n".join([f"{m['home']} vs {m['away']}" for m in matches])
    prompt = f"""
Today's key matches:
{match_text}

Recent news highlights:
{chr(10).join(news[:5])}

Write a daily football intelligence briefing covering tactical storylines, predictions, injury impacts, and key battles. Keep it under 400 words, professional tone.
"""
    return groq_complete(prompt, system="You are a football intelligence analyst writing a daily briefing.", max_tokens=500)