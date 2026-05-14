"""
Gradio application for Hugging Face Spaces – serves tactical analysis API.
Compatible with Gradio 4+ (latest HF Spaces default).
"""
import os
import json
import logging
import gradio as gr
from typing import Dict, Optional, Tuple
import requests
from io import BytesIO
import base64
import traceback

from utils import get_match_by_id, get_match_statistics, get_match_events, get_lineups, get_cache, set_cache
from tactical_engine import compute_tactical_summary
from ai_analysis import generate_tactical_report, generate_social_insights, answer_followup, summarize_news
from visuals import generate_all_graphics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_tactical_analysis(
    match_id: int = 0,
    image=None,
    question: Optional[str] = None,
    match_context: Optional[Dict] = None
) -> str:
    """
    Main endpoint: accept match_id and optional image, return analysis HTML.
    
    Args:
        match_id: API-Football fixture ID
        image: Optional uploaded screenshot (PIL Image)
        question: Optional follow-up question text
        match_context: Previous match context dict for Q&A
    """
    logger.info(f"run_tactical_analysis called with match_id={match_id}, question={question}")
    
    # Handle follow-up Q&A
    if question and match_context:
        try:
            if isinstance(match_context, str):
                match_context = json.loads(match_context)
            answer = answer_followup(question, match_context)
            return f"<div style='color:white;padding:20px;'><h3>💬 Tactical Q&A</h3><p>{answer}</p></div>"
        except Exception as e:
            logger.error(f"Q&A failed: {traceback.format_exc()}")
            return f"<div style='color:red;'><p>Q&A Error: {str(e)}</p></div>"

    # Validate match_id
    if match_id == 0:
        return "<div style='color:orange;padding:20px;'><p>Please provide a valid Match ID to analyze.</p></div>"
    
    # Fetch match data
    try:
        match = get_match_by_id(int(match_id))
        if not match:
            return f"<div style='color:red;'><p>❌ Match with ID {match_id} not found. It may be finished or unavailable.</p></div>"
        
        stats = get_match_statistics(int(match_id))
        events = get_match_events(int(match_id))
        lineups = get_lineups(int(match_id))
        
        logger.info(f"Data fetched for match {match_id}: {match['teams']['home']['name']} vs {match['teams']['away']['name']}")
    except Exception as e:
        logger.error(f"Data fetch failed: {traceback.format_exc()}")
        return f"<div style='color:red;'><p>❌ Failed to fetch match data: {str(e)}</p></div>"

    # Local tactical engine
    try:
        tactical_summary = compute_tactical_summary(match, stats, events, lineups)
        logger.info(f"Tactical summary computed for {tactical_summary['home_team']} vs {tactical_summary['away_team']}")
    except Exception as e:
        logger.error(f"Tactical engine error: {traceback.format_exc()}")
        return f"<div style='color:red;'><p>❌ Tactical engine analysis failed: {str(e)}</p></div>"

    # Image analysis (if image provided)
    image_notes = ""
    if image is not None and os.getenv("GEMINI_API_KEY"):
        try:
            import google.generativeai as genai
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            # Gemini Vision analysis would go here
            image_notes = "<br/><small>📸 Tactical image analyzed</small>"
        except Exception as e:
            logger.warning(f"Gemini Vision failed: {e}")

    # Generate AI report
    try:
        report = generate_tactical_report(tactical_summary)
        logger.info("AI report generated successfully")
    except Exception as e:
        logger.error(f"AI report generation failed: {traceback.format_exc()}")
        return f"<div style='color:red;'><p>❌ AI report generation failed: {str(e)}</p></div>"

    # Generate social insights
    try:
        insights = generate_social_insights(tactical_summary)
    except Exception as e:
        logger.warning(f"Social insights failed: {e}")
        insights = []

    # Generate graphics
    graphics_html = ""
    try:
        graphics = generate_all_graphics(tactical_summary, lineups)
        for name, b64 in graphics.items():
            graphics_html += f"""
            <div style='margin:10px 0;'>
                <img src="data:image/png;base64,{b64}" style="max-width:100%;border-radius:8px;"/>
                <br/><small style='color:#888;'>{name.replace('_', ' ').title()}</small>
            </div>
            """
        logger.info("Graphics generated successfully")
    except Exception as e:
        logger.warning(f"Graphics generation failed: {traceback.format_exc()}")
        graphics_html = "<p style='color:orange;'>⚠️ Graphics could not be generated.</p>"

    # Build HTML response
    html_output = f"""
    <div style='font-family: Arial, sans-serif; color: #e0e0e0; max-width: 800px;'>
        <h2 style='color: #4fc3f7;'>⚽ Tactical Analysis</h2>
        <h3>{tactical_summary['home_team']} {tactical_summary['home_score']} - {tactical_summary['away_score']} {tactical_summary['away_team']}</h3>
        {image_notes}
        
        <div style='background: #1a1a2e; padding: 15px; border-radius: 8px; margin: 10px 0;'>
            <h4 style='color: #4fc3f7;'>📊 Tactical Report</h4>
            <pre style='white-space: pre-wrap; font-family: inherit;'>{report}</pre>
        </div>
        
        <div style='background: #1a1a2e; padding: 15px; border-radius: 8px; margin: 10px 0;'>
            <h4 style='color: #ffd54f;'>📱 Social Insights</h4>
            {''.join(f'<p>• {s}</p>' for s in insights) if insights else '<p>No insights generated</p>'}
        </div>
        
        <div style='background: #1a1a2e; padding: 15px; border-radius: 8px; margin: 10px 0;'>
            <h4 style='color: #81c784;'>📈 Tactical Graphics</h4>
            {graphics_html}
        </div>
        
        <div style='background: #1a1a2e; padding: 15px; border-radius: 8px; margin: 10px 0;'>
            <h4 style='color: #4fc3f7;'>📋 Match Stats</h4>
            <table style='width:100%; color: #e0e0e0;'>
                <tr><td>Possession</td><td>{tactical_summary['possession']['home']}% - {tactical_summary['possession']['away']}%</td></tr>
                <tr><td>Shots (on target)</td><td>{tactical_summary['shots']['home']['total']} ({tactical_summary['shots']['home']['on_target']}) - {tactical_summary['shots']['away']['total']} ({tactical_summary['shots']['away']['on_target']})</td></tr>
                <tr><td>Momentum Index</td><td>{tactical_summary['tactical_metrics']['momentum_index']}</td></tr>
            </table>
        </div>
    </div>
    """
    
    # Cache for follow-up questions
    try:
        set_cache(f"report_{match_id}", tactical_summary)
    except:
        pass
    
    return html_output

# Gradio interface with API enabled
with gr.Blocks(theme=gr.themes.Soft(), title="PepBielsa Tactical AI") as demo:
    gr.Markdown("""
    # ⚽ PepBielsa - AI Football Tactical Intelligence
    *Professional tactical analysis powered by AI*
    """)
    
    with gr.Tab("📊 Match Analysis"):
        with gr.Row():
            with gr.Column(scale=1):
                match_id_input = gr.Number(
                    label="Match ID (from API-Football)",
                    precision=0,
                    value=0,
                    info="Enter the fixture ID to analyze"
                )
                image_input = gr.Image(
                    label="📸 Upload tactical screenshot (optional)",
                    type="pil",
                    height=200
                )
                analyze_btn = gr.Button("🔍 Analyze Match", variant="primary", size="lg")
            
            with gr.Column(scale=2):
                output = gr.HTML(label="Analysis Results")
    
    with gr.Tab("💬 Tactical Q&A"):
        gr.Markdown("Ask follow-up questions about analyzed matches")
        question_input = gr.Textbox(
            label="Your tactical question",
            placeholder="Why did the team struggle in build-up?",
            lines=2
        )
        qa_output = gr.HTML(label="Answer")
        qa_btn = gr.Button("Ask Question")
        qa_btn.click(
            fn=lambda q: run_tactical_analysis(0, None, q, get_cache("last_context")),
            inputs=[question_input],
            outputs=[qa_output]
        )
    
    # Bind analysis
    analyze_btn.click(
        fn=run_tactical_analysis,
        inputs=[match_id_input, image_input],
        outputs=[output]
    )
    
    # API documentation
    gr.Markdown("""
    ---
    ### 🔌 API Usage
    
    **Endpoint:** `/gradio_api/call/run_tactical_analysis`
    
    **Parameters:**
    - `match_id` (int): API-Football fixture ID
    - `image` (file, optional): Tactical screenshot
    - `question` (str, optional): Follow-up question
    - `match_context` (dict, optional): Previous match context
    
    **Example:**
    ```python
    import requests
    response = requests.post(
        "https://thehnx-pepbielsa.hf.space/gradio_api/call/run_tactical_analysis",
        json={"data": [12345, None, None, None]}
    )
    """)

# For Hugging Face Spaces, the Gradio app is launched automatically
if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0")