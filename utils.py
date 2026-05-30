"""
utils.py — Core Utilities
Caching, storage helpers, and environment validation.
"""
import os
import json
import logging
from pathlib import Path
from typing import Optional, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Cache helpers ────────────────────────────────────────────────────────────

DATA_DIR = Path("data")


def get_cache(key: str) -> Optional[Any]:
    """Load a cached JSON object by key."""
    try:
        path = DATA_DIR / f"{key}.json"
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        pass
    return None


def set_cache(key: str, data: Any):
    """Save a JSON object to cache by key."""
    try:
        DATA_DIR.mkdir(exist_ok=True)
        path = DATA_DIR / f"{key}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, default=str))
    except Exception as e:
        logger.warning(f"set_cache failed for '{key}': {e}")


# ─── Storage helpers (backward-compat aliases) ────────────────────────────────

def save_json_to_storage(data: Any, relative_path: str):
    """Save JSON data to a path under DATA_DIR."""
    try:
        full_path = DATA_DIR / relative_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(json.dumps(data, ensure_ascii=False, default=str))
    except Exception as e:
        logger.warning(f"save_json_to_storage failed for '{relative_path}': {e}")


def load_json_from_storage(relative_path: str) -> Optional[Any]:
    """Load JSON data from a path under DATA_DIR."""
    try:
        full_path = DATA_DIR / relative_path
        if full_path.exists():
            return json.loads(full_path.read_text())
    except Exception as e:
        logger.warning(f"load_json_from_storage failed for '{relative_path}': {e}")
    return None


# ─── Environment validation ───────────────────────────────────────────────────

def check_required_env():
    """Log warnings for any missing required environment variables."""
    required = ["TELEGRAM_BOT_TOKEN"]
    optional = ["GROQ_API_KEY", "GEMINI_API_KEY", "NEWS_CHANNEL_ID", "ADMIN_CHAT_ID"]
    missing_required = [v for v in required if not os.getenv(v)]
    missing_optional = [v for v in optional if not os.getenv(v)]

    if missing_required:
        logger.error(f"🔴 CRITICAL — Missing required env vars: {missing_required}")
    if missing_optional:
        logger.warning(f"🟡 Optional env vars not set (some features disabled): {missing_optional}")

    return len(missing_required) == 0