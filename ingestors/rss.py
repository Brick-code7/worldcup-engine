from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from typing import Optional

import feedparser
import httpx

from config import RSS_FEEDS, MAX_ARTICLE_AGE_HOURS
from models.content_item import ContentItem
from utils.scraper import fetch_article


def _parse_date(entry) -> Optional[datetime]:
    for attr in ("published", "updated", "created"):
        raw = getattr(entry, attr, None)
        if raw:
            try:
                dt = parsedate_to_datetime(raw)
                return dt.astimezone(timezone.utc)
            except Exception:
                continue
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            try:
                return datetime(*parsed[:6], tzinfo=timezone.utc)
            except Exception:
                continue
    return None


def _extract_rss_image(entry) -> Optional[str]:
    for media in getattr(entry, "media_content", []):
        url = media.get("url", "")
        if url and any(url.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif")):
            return url
    for enc in getattr(entry, "enclosures", []):
        href = enc.get("href", enc.get("url", ""))
        if href and enc.get("type", "").startswith("image/"):
            return href
    thumbnails = getattr(entry, "media_thumbnail", [])
    if thumbnails:
        return thumbnails[0].get("url")
    return None


async def ingest_rss_feeds(client: httpx.AsyncClient) -> list[ContentItem]:
    print("  [RSS] Starting ingestion...")

    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_ARTICLE_AGE_HOURS)

    # Step 1: parse all feeds and collect candidates
    candidates: list[dict] = []
    for feed_config in RSS_FEEDS:
        feed_name = feed_config["name"]
        feed_url = feed_config["url"]
        print(f"  [RSS/{feed_name}] Parsing feed...")
        try:
            feed = feedparser.parse(feed_url)
        except Exception as e:
            print(f"  [RSS/{feed_name}] Parse error: {e}")
            continue

        count = 0
        for entry in feed.entries:
            try:
                published_at = _parse_date(entry)
                if not published_at:
                    published_at = datetime.now(timezone.utc) - timedelta(hours=1)
                if published_at < cutoff:
                    continue
                url = getattr(entry, "link", "")
                if not url:
                    continue
                candidates.append({
                    "feed_name": feed_name,
                    "feed_url": feed_url,
                    "title": getattr(entry, "title", ""),
                    "url": url,
                    "published_at": published_at,
                    "summary": getattr(entry, "summary", "") or getattr(entry, "description", "") or "",
                    "rss_image": _extract_rss_image(entry),
                })
                count += 1
            except Exception:
                continue
        print(f"  [RSS/{feed_name}] {count} entries in time window")

    print(f"  [RSS] {len(candidates)} total candidates — fetching bodies via Jina AI...")

    # Step 2: fetch all article bodies concurrently via Jina AI (no rate limiting needed — Jina handles it)
    fetch_tasks = [fetch_article(c["url"], client) for c in candidates]
    fetch_results = await asyncio.gather(*fetch_tasks)

    # Step 3: build ContentItems
    items: list[ContentItem] = []
    for cand, (body, scraped_image) in zip(candidates, fetch_results):
        try:
            # Use Jina-extracted image first, fall back to RSS media tags
            image_url = scraped_image or cand["rss_image"]
            # If Jina got nothing, use RSS summary as body fallback
            if not body:
                body = cand["summary"]

            raw = {
                "feed_name": cand["feed_name"],
                "feed_url": cand["feed_url"],
                "title": cand["title"],
                "link": cand["url"],
                "summary": cand["summary"],
            }

            items.append(ContentItem(
                id="",
                source=cand["feed_name"],
                headline=cand["title"],
                body=body,
                url=cand["url"],
                image_url=image_url,
                published_at=cand["published_at"],
                engagement_score=0,
                article_type=None,
                raw=raw,
                ingested_at=datetime.now(timezone.utc),
            ))
        except Exception as e:
            print(f"  [RSS/{cand.get('feed_name','?')}] Error building item: {e}")

    print(f"  [RSS] Collected {len(items)} items")
    return items
