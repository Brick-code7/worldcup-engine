from __future__ import annotations

import html
import re
import uuid
from datetime import datetime, timezone

from models.content_item import ContentItem


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)  # handles &#8220; &#8221; &amp; &lt; etc.
    return text


def _normalize_whitespace(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _truncate_to_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words])


def _to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def normalize(items: list[ContentItem]) -> list[ContentItem]:
    print("  [Normalize] Normalizing items...")
    normalized = []
    now = datetime.now(timezone.utc)

    for item in items:
        try:
            headline = _normalize_whitespace(_strip_html(item.headline or ""))
            body = _normalize_whitespace(_strip_html(item.body or ""))
            body = _truncate_to_words(body, 2000)

            published_at = _to_utc(item.published_at) if item.published_at else now

            normalized.append(ContentItem(
                id=str(uuid.uuid4()),
                source=item.source,
                headline=headline,
                body=body,
                url=item.url.strip() if item.url else "",
                image_url=item.image_url,
                published_at=published_at,
                engagement_score=item.engagement_score,
                article_type=item.article_type,
                raw=item.raw,
                ingested_at=now,
            ))
        except Exception as e:
            print(f"  [Normalize] Error normalizing item '{item.headline[:50] if item.headline else 'unknown'}': {e}")
            continue

    print(f"  [Normalize] {len(normalized)} items normalized")
    return normalized
