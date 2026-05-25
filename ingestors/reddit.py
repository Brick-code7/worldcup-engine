from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
import praw

from config import (
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_USER_AGENT,
    REDDIT_SUBREDDITS,
    REDDIT_POST_LIMIT,
    MAX_ARTICLE_AGE_HOURS,
    MIN_REDDIT_SCORE,
    MIN_BODY_LENGTH,
)
from models.content_item import ContentItem
from utils.scraper import fetch_article


def _is_valid_image_url(url: Optional[str]) -> bool:
    if not url or url in ("self", "default", "nsfw", "spoiler", ""):
        return False
    return (
        url.startswith("http") and (
            any(url.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp"))
            or "i.redd.it" in url
            or "imgur.com" in url
            or "preview.redd.it" in url
        )
    )


async def ingest_reddit(client: httpx.AsyncClient) -> list[ContentItem]:
    print("  [Reddit] Starting ingestion...")

    if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
        print("  [Reddit] WARNING: No credentials — skipping Reddit ingestion")
        return []

    try:
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT,
        )
    except Exception as e:
        print(f"  [Reddit] Failed to init PRAW: {e}")
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_ARTICLE_AGE_HOURS)
    candidates: list[tuple] = []  # (post, subreddit_name)

    for subreddit_name in REDDIT_SUBREDDITS:
        print(f"  [Reddit] Fetching r/{subreddit_name}...")
        try:
            posts = list(reddit.subreddit(subreddit_name).hot(limit=REDDIT_POST_LIMIT))
        except Exception as e:
            print(f"  [Reddit] Error fetching r/{subreddit_name}: {e}")
            continue

        for post in posts:
            try:
                published_at = datetime.fromtimestamp(post.created_utc, tz=timezone.utc)
                if published_at < cutoff:
                    continue
                if post.score < MIN_REDDIT_SCORE:
                    continue
                if getattr(post, "is_video", False):
                    continue
                candidates.append((post, subreddit_name))
            except Exception:
                continue

    # Fetch article bodies concurrently via Jina AI for all link posts
    link_posts = [(p, s) for p, s in candidates if not p.is_self]
    text_posts = [(p, s) for p, s in candidates if p.is_self]

    bodies: dict[str, tuple[str, Optional[str]]] = {}

    if link_posts:
        results = await asyncio.gather(*[
            fetch_article(post.url, client, MIN_BODY_LENGTH)
            for post, _ in link_posts
        ])
        for (post, _), (body, img) in zip(link_posts, results):
            bodies[post.id] = (body, img)

    items: list[ContentItem] = []
    for post, subreddit_name in candidates:
        try:
            published_at = datetime.fromtimestamp(post.created_utc, tz=timezone.utc)
            thumbnail = getattr(post, "thumbnail", None)

            if post.is_self:
                body = post.selftext or ""
                image_url = thumbnail if _is_valid_image_url(thumbnail) else None
            else:
                body, scraped_image = bodies.get(post.id, ("", None))
                image_url = scraped_image or (thumbnail if _is_valid_image_url(thumbnail) else None)

            source_label = "reddit_worldcup" if subreddit_name == "worldcup" else "reddit"

            raw = {
                "id": post.id,
                "subreddit": subreddit_name,
                "score": post.score,
                "num_comments": post.num_comments,
                "url": post.url,
                "permalink": f"https://reddit.com{post.permalink}",
                "is_self": post.is_self,
            }

            items.append(ContentItem(
                id="",
                source=source_label,
                headline=post.title,
                body=body,
                url=post.url if not post.is_self else f"https://reddit.com{post.permalink}",
                image_url=image_url,
                published_at=published_at,
                engagement_score=post.score + (post.num_comments * 2),
                article_type=None,
                raw=raw,
                ingested_at=datetime.now(timezone.utc),
            ))
        except Exception as e:
            print(f"  [Reddit] Error on post '{getattr(post, 'title', '?')[:50]}': {e}")

    print(f"  [Reddit] Collected {len(items)} items from {len(REDDIT_SUBREDDITS)} subreddits")
    return items
