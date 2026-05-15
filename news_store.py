"""
news_store.py
Lightweight JSON-based deduplication store.
Persists seen article IDs to data/seen_articles.json.
Designed for free-tier (no database required).
"""
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Set

logger = logging.getLogger(__name__)

STORE_PATH = Path("data/seen_articles.json")
MAX_STORE_SIZE = 5000       # Max article IDs to keep (rolling window)
EXPIRY_SECONDS = 60 * 60 * 72  # Drop IDs older than 72 hours


class NewsStore:
    """
    Stores { article_id: timestamp } to detect duplicates.
    Thread-safe for single-process use (asyncio-safe since it's sync I/O).
    """

    def __init__(self):
        self._store: Dict[str, float] = {}
        self._load()

    # ── persistence ──────────────────────────────────────────────────────────

    def _load(self):
        STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        if STORE_PATH.exists():
            try:
                raw = json.loads(STORE_PATH.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    self._store = raw
                elif isinstance(raw, list):
                    # Migrate from old list format
                    self._store = {k: time.time() for k in raw}
            except Exception as e:
                logger.warning(f"NewsStore load failed, starting fresh: {e}")
                self._store = {}

    def _save(self):
        try:
            STORE_PATH.write_text(
                json.dumps(self._store, indent=None),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"NewsStore save failed: {e}")

    # ── cleanup ───────────────────────────────────────────────────────────────

    def _evict(self):
        """Remove expired and excess entries to stay lightweight."""
        now = time.time()
        cutoff = now - EXPIRY_SECONDS

        # Remove expired
        self._store = {k: v for k, v in self._store.items() if v >= cutoff}

        # If still too large, drop oldest
        if len(self._store) > MAX_STORE_SIZE:
            sorted_items = sorted(self._store.items(), key=lambda x: x[1])
            self._store = dict(sorted_items[-(MAX_STORE_SIZE // 2) :])

    # ── public API ────────────────────────────────────────────────────────────

    def is_seen(self, article_id: str) -> bool:
        """Return True if this article has already been sent."""
        return article_id in self._store

    def mark_seen(self, article_id: str):
        """Record that this article has been sent."""
        self._store[article_id] = time.time()

    def filter_new(self, items: List[Dict]) -> List[Dict]:
        """
        Given a list of news items (each with an 'id' key),
        return only items not yet seen, and mark them as seen.
        """
        new_items = []
        for item in items:
            aid = item.get("id") or item.get("link", "")
            if not self.is_seen(aid):
                new_items.append(item)
                self.mark_seen(aid)

        if new_items:
            self._evict()
            self._save()

        return new_items

    def size(self) -> int:
        return len(self._store)

    def reset(self):
        """Clear all stored IDs (for testing / admin)."""
        self._store = {}
        self._save()


# ── module-level singleton ────────────────────────────────────────────────────
store = NewsStore()
