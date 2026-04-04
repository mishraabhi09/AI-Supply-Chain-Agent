"""
News Fetcher
Fetches live supply chain disruption news from NewsAPI or GDELT.
Falls back to hardcoded mock data when API key is missing or request fails.
Caches results in memory for 15 minutes per keyword.
"""
import os
import logging
import requests
from datetime import datetime, timedelta

# Module-level in-memory cache: {keyword: {"data": [...], "fetched_at": datetime}}
_cache: dict = {}
CACHE_TTL_SECONDS = 900  # 15 minutes

logging.basicConfig(
    filename="error.log",
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(message)s",
)


def fetch_news(keyword: str) -> dict:
    """
    Main entry point. Returns a dict with:
      - "articles": list of up to 5 NewsArticle dicts
      - "fallback": True (only when using mock data)
    """
    # 1. Check cache
    cached = _cache.get(keyword)
    if cached:
        age = (datetime.now() - cached["fetched_at"]).total_seconds()
        if age < CACHE_TTL_SECONDS:
            return cached["data"]

    api_key = os.environ.get("NEWS_API_KEY", "")
    news_source = os.environ.get("NEWS_SOURCE", "newsapi").lower()

    # 2. Try live API
    try:
        if not api_key:
            logging.warning(
                "NEWS_API_KEY not set. Using fallback mock data for keyword: %s", keyword
            )
            raise ValueError("No API key")

        if news_source == "gdelt":
            articles = _call_gdelt(keyword)
        else:
            articles = _call_newsapi(keyword, api_key)

        result = {"articles": articles[:5], "keyword": keyword}
        _cache[keyword] = {"data": result, "fetched_at": datetime.now()}
        return result

    except Exception:
        return _fallback_mock(keyword)


def _call_newsapi(keyword: str, api_key: str) -> list[dict]:
    """Calls NewsAPI /v2/everything and returns parsed article list."""
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": keyword,
        "sortBy": "publishedAt",
        "pageSize": 5,
        "language": "en",
        "apiKey": api_key,
    }
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    articles = []
    for item in data.get("articles", [])[:5]:
        articles.append({
            "title": item.get("title", ""),
            "source": item.get("source", {}).get("name", ""),
            "published_at": item.get("publishedAt", ""),
            "url": item.get("url", ""),
            "relevance_keyword": keyword,
        })
    return articles


def _call_gdelt(keyword: str) -> list[dict]:
    """Calls GDELT API as secondary source and returns parsed article list."""
    url = "https://api.gdeltproject.org/api/v2/doc/doc"
    params = {
        "query": keyword,
        "mode": "artlist",
        "maxrecords": 5,
        "format": "json",
    }
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    articles = []
    for item in data.get("articles", [])[:5]:
        articles.append({
            "title": item.get("title", ""),
            "source": item.get("domain", ""),
            "published_at": item.get("seendate", ""),
            "url": item.get("url", ""),
            "relevance_keyword": keyword,
        })
    return articles


def _fallback_mock(keyword: str) -> dict:
    """Returns hardcoded mock disruption data with fallback=True flag."""
    keyword_lower = keyword.lower()
    if any(w in keyword_lower for w in ["rotterdam", "port", "strike"]):
        articles = [{
            "title": "Major Port Strike in Rotterdam Causing Severe Shipping Delays",
            "source": "Supply Chain Digest (Mock)",
            "published_at": datetime.now().isoformat(),
            "url": "https://example.com/rotterdam-strike",
            "relevance_keyword": keyword,
        }]
    elif any(w in keyword_lower for w in ["taiwan", "chip", "semiconductor"]):
        articles = [{
            "title": "Taiwan Strait Tensions Impact Semiconductor Supply Chains",
            "source": "Reuters (Mock)",
            "published_at": datetime.now().isoformat(),
            "url": "https://example.com/taiwan-chips",
            "relevance_keyword": keyword,
        }]
    else:
        articles = [{
            "title": f"No major disruptions found for: {keyword}",
            "source": "Aegis Mock Feed",
            "published_at": datetime.now().isoformat(),
            "url": "",
            "relevance_keyword": keyword,
        }]

    return {"articles": articles, "keyword": keyword, "fallback": True}
