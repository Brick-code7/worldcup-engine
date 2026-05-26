from __future__ import annotations

"""
Formats ranked ContentItems into structured JSON for Higgsfield (or any AI image tool).

Each output item contains:
  - All the data needed to generate an Instagram post
  - A ready-made image_prompt for Higgsfield / DALL-E / Midjourney
  - An instagram_caption_data block for the caption generation prompt
"""

import json
import os
from datetime import datetime, timezone
from typing import Any

from models.content_item import ContentItem


# Visual style per article type — tells Higgsfield what kind of shot to generate
_VISUAL_STYLES: dict[str, str] = {
    "injury": (
        "dramatic close-up, player clutching injury on pitch, blurred stadium crowd in background, "
        "moody atmospheric lighting, cinematic wide-angle, shallow depth of field"
    ),
    "squad": (
        "official team photo aesthetic, players lined up in national kit, clean professional lighting, "
        "national flag colours, sharp and bold composition"
    ),
    "lineup": (
        "tactical board visual, football pitch diagram overlay, coach pointing at formation, "
        "press conference room, focused and analytical tone"
    ),
    "transfer": (
        "player walking into stadium tunnel, new national kit, crowd in background, "
        "dramatic reveal lighting, golden hour atmosphere"
    ),
    "result": (
        "goal celebration, players mobbing scorer, packed stadium, confetti, "
        "high-energy action shot, motion blur, bright stadium floodlights"
    ),
    "preview": (
        "two national flags side by side, World Cup trophy in background, "
        "stadium at dusk, competitive tension, clean graphic composition"
    ),
    "other": (
        "World Cup 2026 trophy with stadium backdrop, dramatic sky, "
        "official tournament branding colours, cinematic"
    ),
}

# Urgency colour palette — for text overlay / background tone in Higgsfield
_URGENCY_STYLE: dict[str, str] = {
    "breaking": "urgent red and black colour scheme, BREAKING NEWS banner, high contrast",
    "update":   "bold white and dark blue, UPDATE label, clean modern design",
    "analysis": "premium editorial look, deep navy and gold, analytical tone",
}


def _build_image_prompt(item: ContentItem) -> str:
    """
    Constructs a Higgsfield-ready image generation prompt combining:
    - The player/team subject
    - The article type visual style
    - The urgency treatment
    - World Cup 2026 tournament context
    """
    article_type = getattr(item, "article_type", "other") or "other"
    urgency = getattr(item, "urgency", "update") or "update"
    player = getattr(item, "player", None)
    team = getattr(item, "team", None)

    # Subject line
    if player and team:
        subject = f"{player} in {team} national kit"
    elif player:
        subject = f"{player} in national football kit"
    elif team:
        subject = f"{team} national football team"
    else:
        subject = "World Cup 2026 football scene"

    visual = _VISUAL_STYLES.get(article_type, _VISUAL_STYLES["other"])
    urgency_treatment = _URGENCY_STYLE.get(urgency, _URGENCY_STYLE["update"])

    prompt = (
        f"{subject}, {visual}, {urgency_treatment}, "
        "World Cup 2026 branding, photorealistic, high quality, 9:16 vertical format for Instagram"
    )
    return prompt


def _build_caption_data(item: ContentItem) -> dict[str, str]:
    """
    Structured caption ingredients — feed these into your caption generation prompt.
    The AI prompt that consumes this should turn these into an Instagram caption.
    """
    article_type = getattr(item, "article_type", "other") or "other"
    urgency = getattr(item, "urgency", "update")
    player = getattr(item, "player", None)
    team = getattr(item, "team", None)

    hooks = {
        "injury":   "🚨 INJURY ALERT",
        "squad":    "📋 SQUAD NEWS",
        "lineup":   "📝 LINEUP CONFIRMED",
        "transfer": "🔄 TRANSFER NEWS",
        "result":   "⚽ MATCH RESULT",
        "preview":  "👀 MATCH PREVIEW",
        "other":    "🌍 WORLD CUP 2026",
    }

    return {
        "hook": hooks.get(article_type, hooks["other"]),
        "headline": item.headline,
        "body_excerpt": item.body[:280].replace("\n", " ").strip() if item.body else "",
        "player": player or "",
        "team": team or "",
        "source": item.source,
        "urgency": urgency,
        "article_type": article_type,
        "url": item.url,
    }


def format_item(item: ContentItem) -> dict[str, Any]:
    """Convert one ContentItem to a Higgsfield-ready output dict."""
    return {
        "id": item.id,
        "urgency": getattr(item, "urgency", "update"),
        "article_type": item.article_type or "other",
        "player": getattr(item, "player", None),
        "team": getattr(item, "team", None),
        "headline": item.headline,
        "body_excerpt": item.body[:500].replace("\n", " ").strip() if item.body else "",
        "full_body_words": len(item.body.split()) if item.body else 0,
        "image_url": item.image_url,
        "source": item.source,
        "source_url": item.url,
        "published_at": item.published_at.isoformat(),
        "rank_score": item.rank_score,
        "image_prompt": _build_image_prompt(item),
        "instagram_caption_data": _build_caption_data(item),
    }


def format_items(items: list[ContentItem]) -> list[dict]:
    """Format a list of items — returns the list so captions can be injected before writing."""
    return [format_item(i) for i in items]


def write_output(formatted: list[dict], output_dir: str = "./output") -> str:
    """
    Write pre-formatted item dicts to output/latest.json (overwritten each run)
    and a timestamped archive copy. Returns the path of the latest file.
    """
    os.makedirs(output_dir, exist_ok=True)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bucket": "team_news",
        "total_items": len(formatted),
        "items": formatted,
    }

    # Overwrite latest.json — always the current run's output
    latest_path = os.path.join(output_dir, "latest.json")
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    # Keep a rolling 24-hour archive (delete files older than 24 runs)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    archive_path = os.path.join(output_dir, f"team_news_{timestamp}.json")
    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    _prune_archive(output_dir, keep=24)
    return latest_path


def _prune_archive(output_dir: str, keep: int) -> None:
    import glob
    files = sorted(glob.glob(os.path.join(output_dir, "team_news_*.json")))
    for old in files[:-keep]:
        try:
            os.remove(old)
        except OSError:
            pass
