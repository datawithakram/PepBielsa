"""
Football News Intelligence – fetches RSS feeds, summarizes with Groq,
extracts tactical implications, stores in HF dataset.
"""
import os
import json
import feedparser
from typing import List, Dict
import logging
from utils import save_json_to_storage, load_json_from_storage, groq_complete  # import after definition if needed; but here we import from ai_analysis

from ai_analysis import summarize_news

logger = logging.getLogger(__name__)

RSS_FEEDS = [
    "http://feeds.bbci.co.uk/sport/football/rss.xml",
    "https://www.skysports.com/football/rss",
    "https://www.espn.com/espn/rss/soccer/news",
    "https://www.theguardian.com/football/rss",
]

def fetch_recent_news(max_per_feed=3) -> List[Dict]:
    """Fetch latest football news from RSS feeds."""
    articles = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_feed]:
                articles.append({
                    "title": entry.title,
                    "summary": entry.get("summary", ""),
                    "link": entry.link,
                    "source": url
                })
        except Exception as e:
            logger.warning(f"RSS parse error {url}: {e}")
    return articles

def process_news(articles: List[Dict]) -> List[Dict]:
    """Summarize each article and extract tactical implications."""
    processed = []
    for art in articles:
        text = f"{art['title']}\n{art['summary']}"
        result = summarize_news(text)
        processed.append({
            "title": art["title"],
            "link": art["link"],
            "summary": result.get("summary", ""),
            "tactical_implication": result.get("tactical_implication", "")
        })
    # Save to storage
    save_json_to_storage(processed, "news_cache/latest_news.json")
    return processed

def get_latest_news(force_refresh=False) -> List[Dict]:
    if not force_refresh:
        cached = load_json_from_storage("news_cache/latest_news.json")
        if cached:
            return cached
    articles = fetch_recent_news()
    return process_news(articles)