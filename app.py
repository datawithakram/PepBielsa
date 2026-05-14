"""
Gradio application for Hugging Face Spaces – serves tactical analysis API.
"""
import os
import json
import logging
import gradio as gr
from typing import Dict, Optional
import requests
from io import BytesIO
import base64

from utils import get_match_by_id, get_match_statistics, get_match_events, get_lineups, get_cache, set_cache
from tactical_engine import compute_tactical_summary
from ai_analysis import generate_tactical_report, generate_social_insights, answer_followup, summarize_news
from visuals import generate_all_graphics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_tactical_analysis(match_id: int, image_b64: Optional[str] = None, question: Optional[str] = None, match_context: Optional[Dict] = None) -> Dict:
    """
    Main endpoint: accept match_id and optional image, return analysis.
    """
    # Handle follow-up Q&A
    if question and match_context:
        answer = answer_followup(question, match_context)
        return {"answer": answer}

    # Fetch match data
    try:
        match = get_match_by_id(match_id)
        if not match:
            raise ValueError("Match not found")
        stats = get_match_statistics(match_id)
        events = get_match_events(match_id)
        lineups = get_lineups(match_id)
    except Exception as e:
        logger.error(f"Data fetch failed: {e}")
        return {"error": f"Failed to fetch match data: {str(e)}"}

    # Local tactical engine
    try:
        tactical_summary = compute_tactical_summary(match, stats, events, lineups)
    except Exception as e:
        logger.error(f"Tactical engine error: {e}")
        return {"error": "Tactical engine analysis failed."}

    # Image analysis (if image provided)
    image_notes = ""
    if image_b64 and os.getenv("GEMINI_API_KEY"):
        try:
            import google.generativeai as genai
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            model = genai.GenerativeModel('gemini-pro-vision')
            # Convert base64 to image
            img_data = base64.b64decode(image_b64)
            # Call Gemini (simplified; actual vision API requires image part)
            # This is placeholder; Gemini Vision API would be used here
            image_notes = "Image analysis: [tactical observations]"
        except Exception as e:
            logger.warning(f"Gemini Vision failed: {e}")

    # Generate AI report
    try:
        report = generate_tactical_report(tactical_summary)
    except Exception as e:
        return {"error": f"AI report generation failed: {str(e)}"}

    # Generate social insights
    insights = generate_social_insights(tactical_summary)

    # Generate graphics
    try:
        graphics = generate_all_graphics(tactical_summary, lineups)
    except Exception as e:
        logger.warning(f"Graphics generation failed: {e}")
        graphics = {}

    # Combine result
    result = {
        "report": report,
        "insights": insights,
        "images": graphics,
        "tactical_summary": tactical_summary
    }
    # Cache report for follow-up
    set_cache(f"report_{match_id}", result)
    return result

# Gradio interface
def gradio_handler(match_id, image=None, question=None, match_context=None):
    # Convert image to base64 if provided
    img_b64 = None
    if image is not None:
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode()

    # Call main function
    result = run_tactical_analysis(int(match_id), img_b64, question, match_context)
    # Format for Gradio output
    if "error" in result:
        return result["error"]
    report_text = result.get("report", "")
    insights_text = "\n".join([f"• {s}" for s in result.get("insights", [])])
    images_html = ""
    for name, b64 in result.get("images", {}).items():
        images_html += f'<img src="data:image/png;base64,{b64}" style="max-width:300px;"/><br/><b>{name}</b><br/>'
    return f"{report_text}\n\n{insights_text}\n{images_html}"

# Define Gradio Blocks for UI testing and API
with gr.Blocks() as demo:
    gr.Markdown("# AI Football Tactical Intelligence")
    with gr.Tab("Analysis"):
        match_id_input = gr.Number(label="Match ID", precision=0)
        image_input = gr.Image(label="Upload tactical screenshot (optional)", type="pil")
        output = gr.HTML()
        analyze_btn = gr.Button("Analyze")
        analyze_btn.click(gradio_handler, inputs=[match_id_input, image_input], outputs=output)

    # API endpoint (accessible via Gradio's built-in API)
    demo.queue()

# For Hugging Face Spaces, the Gradio app is launched automatically
if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0")