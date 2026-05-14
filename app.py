"""
Gradio application for Hugging Face Spaces.
Simple API for tactical analysis.
"""
import os
import json
import base64
import logging
from typing import Dict, Optional
from io import BytesIO
import gradio as gr

from utils import get_match_by_id, get_match_statistics, get_match_events, get_lineups
from tactical_engine import compute_tactical_summary
from ai_analysis import generate_tactical_report, generate_social_insights, answer_followup
from visuals import generate_all_graphics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_tactical_analysis(
    match_id: int = 0,
    image=None,
    question: Optional[str] = None,
    match_context: Optional[str] = None
) -> str:
    """Main analysis function."""
    
    # Q&A mode
    if question and match_context:
        try:
            ctx = json.loads(match_context) if isinstance(match_context, str) else match_context
            answer = answer_followup(question, ctx)
            return f"<div style='padding:20px;color:white;'><h3>Answer</h3><p>{answer}</p></div>"
        except Exception as e:
            return f"<p style='color:red;'>Q&A Error: {e}</p>"
    
    if match_id == 0:
        return "<p style='color:orange;'>Enter a Match ID to analyze.</p>"
    
    # Fetch data
    try:
        match = get_match_by_id(int(match_id))
        if not match:
            return f"<p style='color:red;'>Match {match_id} not found.</p>"
        
        stats = get_match_statistics(int(match_id))
        events = get_match_events(int(match_id))
        lineups = get_lineups(int(match_id))
    except Exception as e:
        return f"<p style='color:red;'>Data fetch error: {e}</p>"
    
    # Tactical engine
    try:
        summary = compute_tactical_summary(match, stats, events, lineups)
    except Exception as e:
        return f"<p style='color:red;'>Tactical engine error: {e}</p>"
    
    # AI Report
    try:
        report = generate_tactical_report(summary)
    except Exception as e:
        return f"<p style='color:red;'>AI error: {e}</p>"
    
    # Social insights
    try:
        insights = generate_social_insights(summary)
    except:
        insights = []
    
    # Graphics
    graphics_html = ""
    try:
        graphics = generate_all_graphics(summary, lineups)
        for name, b64 in graphics.items():
            graphics_html += f'<img src="data:image/png;base64,{b64}" style="max-width:100%;margin:5px 0;"/><br/>'
    except:
        graphics_html = "<p>Graphics unavailable</p>"
    
    home = summary['home_team']
    away = summary['away_team']
    hs = summary['home_score']
    as_ = summary['away_score']
    
    return f"""
    <div style='font-family:sans-serif;color:white;max-width:800px;'>
        <h2>⚽ {home} {hs} - {as_} {away}</h2>
        <div style='background:#1a1a2e;padding:15px;border-radius:8px;margin:10px 0;'>
            <h3>📊 Tactical Report</h3>
            <pre style='white-space:pre-wrap;'>{report}</pre>
        </div>
        <div style='background:#1a1a2e;padding:15px;border-radius:8px;margin:10px 0;'>
            <h3>📱 Social Insights</h3>
            {''.join(f'<p>• {s}</p>' for s in insights)}
        </div>
        <div style='background:#1a1a2e;padding:15px;border-radius:8px;margin:10px 0;'>
            <h3>📈 Graphics</h3>
            {graphics_html}
        </div>
    </div>
    """

# Simple Gradio interface
demo = gr.Interface(
    fn=run_tactical_analysis,
    inputs=[
        gr.Number(label="Match ID", precision=0),
        gr.Image(label="Upload Screenshot (optional)", type="pil"),
        gr.Textbox(label="Question (for Q&A mode)", visible=False),
        gr.Textbox(label="Context", visible=False)
    ],
    outputs=gr.HTML(label="Analysis Results"),
    title="PepBielsa - AI Football Tactical Intelligence",
    description="Enter a Match ID from API-Football to get tactical analysis.",
    theme="soft"
)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)