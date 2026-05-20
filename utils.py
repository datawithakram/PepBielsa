"""
utils.py — Cleaned Utilities (No API-Football)
Focuses on caching, storage, and helper functions.
"""
import os
import json
import logging
from pathlib import Path
from typing import Optional, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ----- Configuration -----
# Removed API_FOOTBALL_KEY as requested.
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# ----- Cache helpers -----
def get_cache(key: str) -> Optional[Any]:
    try:
        with open(f"data/{key}.json", "r") as f:
            return json.load(f)
    except:
        return None

def set_cache(key: str, data: Any):
    Path("data").mkdir(exist_ok=True)
    with open(f"data/{key}.json", "w") as f:
        json.dump(data, f)

def check_required_env():
    required = ["GROQ_API_KEY", "TELEGRAM_BOT_TOKEN"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        logger.warning(f"Missing essential env vars: {missing}")