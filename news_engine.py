"""
Football News Intelligence – fetches RSS feeds, summarizes with Groq,
extracts tactical implications, stores in HF dataset.
"""
import os
import json
import feedparser
from typing import List, Dict
import logging
from utils import save_json_to_storage, load_json_from_storage
from ai_analysis import summarize_news  # Correct import

logger = logging.getLogger(__name__)

RSS_FEEDS = [
    "http://feeds.bbci.co.uk/sport/football/rss.xml",
    "https://www.skysports.com/football/rss",
    "https://www.espn.com/espn/rss/soccer/news",
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
        try:
            text = f"{art['title']}\n{art['summary']}"
            result = summarize_news(text)
            processed.append({
                "title": art["title"],
                "link": art["link"],
                "summary": result.get("summary", ""),
                "tactical_implication": result.get("tactical_implication", "")
            })
        except Exception as e:
            logger.error(f"News processing failed: {e}")
            processed.append({
                "title": art["title"],
                "link": art["link"],
                "summary": art.get("summary", "")[:200],
                "tactical_implication": "Analysis unavailable"
            })
    
    # Save to storage
    try:
        save_json_to_storage(processed, "news_cache/latest_news.json")
    except:
        pass
    
    return processed

def get_latest_news(force_refresh=False) -> List[Dict]:
    if not force_refresh:
        try:
            cached = load_json_from_storage("news_cache/latest_news.json")
            if cached:
                return cached
        except:
            pass
    articles = fetch_recent_news()
    return process_news(articles)