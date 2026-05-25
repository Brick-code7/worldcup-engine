from __future__ import annotations

from rapidfuzz import fuzz

from config import (
    WC_PLAYER_KEYWORDS,
    WC_TEAM_KEYWORDS,
    WC_TERM_KEYWORDS,
    DEDUP_SIMILARITY_THRESHOLD,
)
from models.content_item import ContentItem

# Other sports also run "World Cups" — explicitly block them first
_OTHER_SPORT_WC = [
    "rugby world cup", "cricket world cup", "hockey world cup",
    "t20 world cup", "rugby league world cup", "polo world cup",
    "handball world cup", "basketball world cup", "volleyball world cup",
    "swimming world cup", "cycling world cup", "skiing world cup",
    "chess world cup", "darts world cup",
]

# Year-anchored or compound phrases — a headline with ANY of these is unambiguously WC 2026
_HIGH_CONFIDENCE_PHRASES = [
    "world cup 2026", "2026 world cup", "wc 2026", "wc26",
    "fifa 2026", "2026 fifa",
    # Compound phrases where "World Cup" + tournament noun = clearly the football WC
    "world cup squad", "world cup roster", "world cup selection",
    "world cup injury", "world cup fitness",
    "world cup qualifier", "world cup qualifying",
    "world cup group", "world cup draw",
    "world cup final", "world cup semi", "world cup quarter",
    "world cup round", "world cup knockout",
    "world cup prediction", "world cup preview", "world cup analysis",
    "world cup highlights", "world cup goals", "world cup match",
    "world cup opener", "world cup game", "world cup fixture",
    "world cup lineup", "world cup starting",
    "world cup host", "world cup venue",
    "world cup golden boot", "world cup top scorer",
]


def _headline_passes(headline: str) -> bool:
    hl = headline.lower()

    # Hard block: other sports' World Cups
    if any(other in hl for other in _OTHER_SPORT_WC):
        return False

    # Tier 1: headline contains a year-anchored or compound WC phrase → always pass
    if any(phrase in hl for phrase in _HIGH_CONFIDENCE_PHRASES):
        return True

    # Tier 2: headline contains "world cup" or "worldcup" + football context in the SAME headline
    # e.g. "USA beats Mexico in World Cup thriller" — no year but has teams + "world cup"
    if "world cup" in hl or "worldcup" in hl:
        has_player = any(p in hl for p in WC_PLAYER_KEYWORDS)
        has_team = any(t in hl for t in WC_TEAM_KEYWORDS)
        has_term = any(t in hl for t in WC_TERM_KEYWORDS)
        # Must have at least one contextual anchor alongside "world cup"
        return has_player or has_team or has_term

    return False


def _passes_quality(item: ContentItem) -> bool:
    if not item.headline or len(item.headline) < 10:
        return False
    if not item.body and not item.image_url:
        return False
    return True


def _deduplicate(items: list[ContentItem]) -> list[ContentItem]:
    kept: list[ContentItem] = []

    for item in items:
        duplicate_idx = None
        for i, existing in enumerate(kept):
            if fuzz.ratio(item.headline.lower(), existing.headline.lower()) > DEDUP_SIMILARITY_THRESHOLD:
                duplicate_idx = i
                break

        if duplicate_idx is None:
            kept.append(item)
        else:
            existing = kept[duplicate_idx]
            if item.engagement_score > existing.engagement_score:
                kept[duplicate_idx] = item
            elif item.engagement_score == existing.engagement_score and item.body and not existing.body:
                kept[duplicate_idx] = item

    return kept


def filter_items(items: list[ContentItem]) -> list[ContentItem]:
    print("  [Filter] Applying World Cup 2026 relevance filter...")

    relevant = [i for i in items if _headline_passes(i.headline)]
    dropped = len(items) - len(relevant)
    print(f"  [Filter] {len(relevant)}/{len(items)} items passed headline filter ({dropped} dropped)")

    quality = [i for i in relevant if _passes_quality(i)]
    print(f"  [Filter] {len(quality)}/{len(relevant)} items passed quality filter")

    deduplicated = _deduplicate(quality)
    print(f"  [Filter] {len(deduplicated)}/{len(quality)} items after deduplication")

    return deduplicated
