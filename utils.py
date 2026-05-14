"""
Utility module: API clients, caching, HuggingFace Dataset storage, helpers.
"""
import os
import json
import time
import base64
import logging
from io import BytesIO
from functools import wraps
from pathlib import Path
from typing import Optional, Dict, Any

import requests
import pandas as pd
from dotenv import load_dotenv
from huggingface_hub import HfApi, hf_hub_download, login

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ----- Configuration -----
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
HF_TOKEN = os.getenv("HF_TOKEN")
HF_USERNAME = os.getenv("HF_USERNAME")
HF_DATASET_REPO = os.getenv("HF_DATASET_REPO")

API_FOOTBALL_BASE = "https://v3.football.api-sports.io"
RAPID_HEADERS = {
    "x-rapidapi-key": API_FOOTBALL_KEY,
    "x-rapidapi-host": "v3.football.api-sports.io"
}

# ----- Retry decorator -----
def retry(max_retries=3, delay=1, backoff=2, exceptions=(Exception,)):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            m_retries, m_delay = max_retries, delay
            while m_retries > 0:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    m_retries -= 1
                    if m_retries == 0:
                        raise
                    logger.warning(f"Retry {func.__name__} in {m_delay}s due to {e}")
                    time.sleep(m_delay)
                    m_delay *= backoff
        return wrapper
    return decorator

# ----- API-Football client -----
@retry(max_retries=2, delay=2)
def api_football_get(endpoint: str, params: dict = None) -> dict:
    url = f"{API_FOOTBALL_BASE}/{endpoint}"
    resp = requests.get(url, headers=RAPID_HEADERS, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()

def get_today_matches() -> list:
    """Fetch today's fixtures."""
    from datetime import date
    today = date.today().strftime("%Y-%m-%d")
    data = api_football_get("fixtures", {"date": today})
    return data.get("response", [])

def get_match_by_id(match_id: int) -> dict:
    data = api_football_get("fixtures", {"id": match_id})
    fixtures = data.get("response", [])
    return fixtures[0] if fixtures else None

def get_match_statistics(match_id: int) -> dict:
    data = api_football_get("fixtures/statistics", {"fixture": match_id})
    return data.get("response", [])

def get_match_events(match_id: int) -> dict:
    data = api_football_get("fixtures/events", {"fixture": match_id})
    return data.get("response", [])

def get_lineups(match_id: int) -> dict:
    data = api_football_get("fixtures/lineups", {"fixture": match_id})
    return data.get("response", [])

# ----- HuggingFace Dataset Storage -----
def init_hf_storage():
    """Login to HuggingFace Hub if token available."""
    if HF_TOKEN:
        login(token=HF_TOKEN)

def upload_to_storage(file_path: str, repo_path: str = None, repo_type="dataset"):
    """Upload a file to the HF dataset repo."""
    if not repo_path:
        repo_path = HF_DATASET_REPO
    api = HfApi()
    api.upload_file(
        path_or_fileobj=file_path,
        path_in_repo=repo_path if repo_path else os.path.basename(file_path),
        repo_id=repo_path,
        repo_type=repo_type,
        token=HF_TOKEN
    )

def download_from_storage(repo_path: str, filename: str, cache_dir="data") -> Optional[Path]:
    """Download a file from HF dataset repo."""
    try:
        local = hf_hub_download(
            repo_id=repo_path,
            filename=filename,
            repo_type="dataset",
            token=HF_TOKEN,
            cache_dir=cache_dir
        )
        return Path(local)
    except Exception as e:
        logger.error(f"Storage download failed: {e}")
        return None

def save_json_to_storage(data: dict, filename: str):
    """Save dict as JSON in HF dataset."""
    tmp = f"temp/{filename}"
    Path("temp").mkdir(exist_ok=True)
    with open(tmp, "w") as f:
        json.dump(data, f)
    upload_to_storage(tmp, filename)

def load_json_from_storage(filename: str) -> Optional[dict]:
    """Load JSON from HF dataset."""
    path = download_from_storage(HF_DATASET_REPO, filename)
    if path and path.exists():
        with open(path, "r") as f:
            return json.load(f)
    return None

# ----- Image helpers -----
def image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def base64_to_image(b64_str: str, output_path: str) -> Path:
    img_data = base64.b64decode(b64_str)
    path = Path(output_path)
    path.write_bytes(img_data)
    return path

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

# ----- Configuration checker -----
def check_required_env():
    required = ["API_FOOTBALL_KEY", "GROQ_API_KEY", "TELEGRAM_BOT_TOKEN", "HF_TOKEN", "HF_DATASET_REPO"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        raise EnvironmentError(f"Missing env vars: {missing}")

check_required_env()
init_hf_storage()