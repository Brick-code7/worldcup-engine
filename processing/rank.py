from __future__ import annotations

from datetime import datetime, timezone

from models.content_item import ContentItem


def _recency_score(published_at: datetime) -> float:
    age_minutes = (datetime.now(timezone.utc) - published_at).total_seconds() / 60
    if age_minutes <= 30:   return 60   # very fresh — likely breaking
    if age_minutes <= 90:   return 50   # still hot
    if age_minutes <= 180:  return 30   # recent
    if age_minutes <= 360:  return 10   # within window
    return 0


def _engagement_score(engagement: int) -> float:
    return min(engagement / 100, 50)


# Team news article types ranked by Instagram value
_TYPE_SCORES: dict[str, float] = {
    "injury":   25,   # highest — most shareable, time-sensitive
    "squad":    20,   # official selections are major news
    "lineup":   15,   # confirmed XIs drive engagement
    "result":   15,
    "transfer": 10,
    "preview":   5,
    "other":     0,
}

_URGENCY_SCORES: dict[str, float] = {
    "breaking": 20,
    "update":    5,
    "analysis":  0,
}


def rank_items(items: list[ContentItem]) -> list[ContentItem]:
    print("  [Rank] Computing rank scores...")

    rough_scores: dict[str, float] = {}
    for item in items:
        score = (
            _recency_score(item.published_at)
            + _engagement_score(item.engagement_score)
            + _TYPE_SCORES.get(item.article_type or "other", 0)
            + _URGENCY_SCORES.get(getattr(item, "urgency", "update"), 0)
            + (10 if item.image_url else 0)
            + (10 if item.body and len(item.body.split()) > 200 else 0)
            + (15 if getattr(item, "player") else 0)   # named player = more specific
        )
        rough_scores[item.id] = score

    rough_sorted = sorted(items, key=lambda i: rough_scores[i.id], reverse=True)

    # Source diversity pass — no more than 2 items per source in the top 10
    source_top10_counts: dict[str, int] = {}
    final_items: list[ContentItem] = []

    for item in rough_sorted:
        score = rough_scores[item.id]
        if source_top10_counts.get(item.source, 0) < 2:
            score += 5
        item.rank_score = score
        final_items.append(item)
        if len(final_items) <= 10:
            source_top10_counts[item.source] = source_top10_counts.get(item.source, 0) + 1

    final_items.sort(key=lambda i: i.rank_score, reverse=True)
    print(f"  [Rank] Ranked {len(final_items)} items")
    return final_items
