from __future__ import annotations

"""
Generates AI images for the top-ranked items via Replicate (Flux Schnell).

Costs about $0.003 per image. Only the top N items get images to keep
hourly costs predictable.

Replicate image URLs expire after 24 hours — for now that's fine
(same-day Instagram posting). If we need persistence later, we'll
download and re-upload to Supabase Storage.
"""

import os

import replicate
from dotenv import load_dotenv

load_dotenv()

_MODEL = "black-forest-labs/flux-schnell"


def generate_images(formatted: list[dict], top_n: int = 5) -> list[dict]:
    """
    Mutates each dict in `formatted` (top N only) by adding a
    `generated_image_url` key with the Replicate output URL.
    Items beyond top_n are skipped to control cost.
    Returns the same list.
    """
    token = os.getenv("REPLICATE_API_TOKEN", "")
    if not token:
        print("  [Image] REPLICATE_API_TOKEN not set — skipping image generation")
        return formatted

    # The replicate SDK reads REPLICATE_API_TOKEN from env automatically
    os.environ["REPLICATE_API_TOKEN"] = token

    targets = formatted[:top_n]
    print(f"  [Image] Generating {len(targets)} images via Flux Schnell...")

    generated = 0
    failed = 0

    for item_dict in targets:
        prompt = item_dict.get("image_prompt", "")
        if not prompt:
            item_dict["generated_image_url"] = None
            continue

        try:
            output = replicate.run(
                _MODEL,
                input={
                    "prompt": prompt,
                    "aspect_ratio": "9:16",
                    "output_format": "webp",
                    "output_quality": 90,
                    "num_outputs": 1,
                },
            )
            # Replicate returns a list of FileOutput objects — take the first URL
            url = str(output[0]) if output else None
            item_dict["generated_image_url"] = url
            generated += 1
        except Exception as e:
            item_dict["generated_image_url"] = None
            failed += 1
            print(f"  [Image] Failed for '{item_dict.get('headline','?')[:50]}': {e}")

    # Mark non-targets explicitly
    for item_dict in formatted[top_n:]:
        item_dict["generated_image_url"] = None

    print(f"  [Image] Generated {generated} images ({failed} failed)")
    return formatted
