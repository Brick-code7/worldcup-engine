from __future__ import annotations

"""
Generates Instagram captions for ranked ContentItems using Claude.

Reads ANTHROPIC_API_KEY from the environment. Items without captions
are skipped gracefully so the pipeline never blocks on API failures.
"""

import os
from typing import Any

import anthropic
from dotenv import load_dotenv

from models.content_item import ContentItem

load_dotenv()

_SYSTEM_PROMPT = """\
You write Instagram captions for a World Cup 2026 football news account.

Style rules:
- Hook on line 1: bold claim or question, max 12 words
- 2-3 short sentences of context (no filler words)
- End with a clear call to action ("Drop your thoughts below 👇" / "Who's your pick? 👇")
- 4-6 relevant hashtags on the final line
- Emojis: 1-2 per section, football/flag/fire only — no spam
- Tone: urgent for breaking news, confident for squad/lineup, analytical for previews
- Max 220 characters before the hashtag line (Instagram optimal)
- Never fabricate stats or quotes
"""


def _build_user_prompt(data: dict[str, Any]) -> str:
    urgency = data.get("urgency", "update").upper()
    article_type = data.get("article_type", "other").upper()
    hook = data.get("hook", "")
    headline = data.get("headline", "")
    excerpt = data.get("body_excerpt", "")
    player = data.get("player", "")
    team = data.get("team", "")

    lines = [
        f"URGENCY: {urgency}",
        f"TYPE: {article_type}",
        f"HOOK TEMPLATE: {hook}",
        f"HEADLINE: {headline}",
    ]
    if player:
        lines.append(f"PLAYER: {player}")
    if team:
        lines.append(f"TEAM: {team}")
    if excerpt:
        lines.append(f"ARTICLE EXCERPT: {excerpt[:300]}")

    lines.append("\nWrite the Instagram caption now.")
    return "\n".join(lines)


def generate_captions(items: list[ContentItem], output_data: list[dict]) -> list[dict]:
    """
    Mutates each dict in output_data by adding an 'instagram_caption' key.
    output_data is the list of formatted dicts from formatter.format_item().
    Returns the same list.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("  [Caption] ANTHROPIC_API_KEY not set — skipping caption generation")
        return output_data

    client = anthropic.Anthropic(api_key=api_key)
    generated = 0
    failed = 0

    print(f"  [Caption] Generating captions for {len(output_data)} items...")

    for item_dict in output_data:
        caption_data = item_dict.get("instagram_caption_data", {})
        try:
            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=300,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": _build_user_prompt(caption_data)}],
            )
            item_dict["instagram_caption"] = message.content[0].text.strip()
            generated += 1
        except Exception as e:
            item_dict["instagram_caption"] = ""
            failed += 1
            print(f"  [Caption] Failed for '{item_dict.get('headline','?')[:50]}': {e}")

    print(f"  [Caption] Generated {generated} captions ({failed} failed)")
    return output_data
