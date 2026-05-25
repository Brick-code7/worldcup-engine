from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

import feedparser
import httpx

from config import (
    GOOGLE_NEWS_QUERIES,
    GOOGLE_NEWS_RSS_BASE,
    MAX_ARTICLE_AGE_HOURS,
)
from models.content_item import ContentItem
from utils.scraper import fetch_article


def _strip_source_suffix(title: str) -> str:
    """Remove ' - Source Name' suffix that Google News appends."""
    return re.sub(r"\s+-\s+[^-]+$", "", title).strip()


def _parse_date(date_str: str) -> datetime | None:
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


async def _resolve_redirect(client: httpx.AsyncClient, url: str) -> str:
    try:
        resp = await client.head(url, follow_redirects=True, timeout=10)
        return str(resp.url)
    except Exception:
        return url


async def ingest_google_news(client: httpx.AsyncClient) -> list[ContentItem]:
    print("  [Google News] Starting ingestion...")

    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_ARTICLE_AGE_HOURS)
    seen_urls: set[str] = set()

    # Step 1: parse all RSS feeds and collect candidate entries
    candidates: list[dict] = []
    for query in GOOGLE_NEWS_QUERIES:
        feed_url = GOOGLE_NEWS_RSS_BASE.format(query=query)
        print(f"  [Google News] Fetching: {query}")
        try:
            feed = feedparser.parse(feed_url)
        except Exception as e:
            print(f"  [Google News] Feed error for {query}: {e}")
            continue

        for entry in feed.entries:
            try:
                raw_date = getattr(entry, "published", None)
                if not raw_date:
                    continue
                published_at = _parse_date(raw_date)
                if not published_at or published_at < cutoff:
                    continue
                raw_url = getattr(entry, "link", "")
                if not raw_url:
                    continue
                candidates.append({
                    "raw_url": raw_url,
                    "title": getattr(entry, "title", ""),
                    "published_at": published_at,
                    "summary": getattr(entry, "summary", ""),
                    "query": query,
                })
            except Exception:
                continue

    print(f"  [Google News] {len(candidates)} raw entries, resolving redirects...")

    # Step 2: resolve all redirect URLs concurrently
    redirect_tasks = [_resolve_redirect(client, c["raw_url"]) for c in candidates]
    canonical_urls = await asyncio.gather(*redirect_tasks)

    # Step 3: deduplicate by canonical URL
    unique: list[tuple[dict, str]] = []
    for cand, canon_url in zip(candidates, canonical_urls):
        if canon_url not in seen_urls:
            seen_urls.add(canon_url)
            unique.append((cand, canon_url))

    print(f"  [Google News] {len(unique)} unique articles — fetching bodies via Jina AI...")

    # Step 4: fetch all article bodies concurrently via Jina AI
    fetch_tasks = [fetch_article(canon_url, client) for _, canon_url in unique]
    fetch_results = await asyncio.gather(*fetch_tasks)

    # Step 5: assemble ContentItems
    items: list[ContentItem] = []
    for (cand, canon_url), (body, image_url) in zip(unique, fetch_results):
        try:
            headline = _strip_source_suffix(cand["title"])
            raw = {
                "title": cand["title"],
                "link": cand["raw_url"],
                "canonical_url": canon_url,
                "published": cand["published_at"].isoformat(),
                "query": cand["query"],
                "summary": cand["summary"],
            }
            items.append(ContentItem(
                id="",
                source="google_news",
                headline=headline,
                body=body,
                url=canon_url,
                image_url=image_url,
                published_at=cand["published_at"],
                engagement_score=0,
                article_type=None,
                raw=raw,
                ingested_at=datetime.now(timezone.utc),
            ))
        except Exception as e:
            print(f"  [Google News] Error building item '{cand.get('title','?')[:50]}': {e}")

    print(f"  [Google News] Collected {len(items)} items")
    return items
