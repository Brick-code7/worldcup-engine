from __future__ import annotations

"""
AI-powered article scraper using Jina AI Reader (r.jina.ai).

Jina Reader converts any URL into clean markdown using AI — no API key required.
It handles JS-rendered pages, paywalls, and messy HTML that trafilatura struggles with.

Usage: GET https://r.jina.ai/{url}
Returns: clean markdown text of the article body.
"""

import asyncio
import re
from typing import Optional

import httpx

JINA_BASE = "https://r.jina.ai/"

HEADERS = {
    "Accept": "text/plain",           # get plain markdown, not HTML wrapper
    "X-Return-Format": "markdown",    # explicitly request markdown
    "User-Agent": "worldcup-engine/1.0 (content aggregator)",
}

# Per-domain concurrency limit to be a good citizen
_domain_semaphores: dict[str, asyncio.Semaphore] = {}

def _get_semaphore(domain: str) -> asyncio.Semaphore:
    if domain not in _domain_semaphores:
        _domain_semaphores[domain] = asyncio.Semaphore(2)
    return _domain_semaphores[domain]


def _extract_image_from_markdown(markdown: str) -> Optional[str]:
    """Pull the first image URL out of Jina's markdown output."""
    # Jina returns images as ![alt](url) or as Image: url metadata
    patterns = [
        r"!\[.*?\]\((https?://[^\s)]+(?:\.jpg|\.jpeg|\.png|\.webp|\.gif)[^\s)]*)\)",
        r"Image:\s*(https?://\S+(?:\.jpg|\.jpeg|\.png|\.webp|\.gif)\S*)",
        r"!\[.*?\]\((https?://[^\s)]+)\)",  # any image link as fallback
    ]
    for pattern in patterns:
        match = re.search(pattern, markdown, re.IGNORECASE)
        if match:
            url = match.group(1).rstrip(")")
            if url.startswith("http"):
                return url
    return None


async def fetch_article(
    url: str,
    client: httpx.AsyncClient,
    min_length: int = 100,
) -> tuple[str, Optional[str]]:
    """
    Fetch article body and hero image from a URL via Jina AI Reader.

    Returns (body_text, image_url). Body is empty string on failure — never raises.
    """
    from urllib.parse import urlparse
    domain = urlparse(url).netloc
    semaphore = _get_semaphore(domain)

    async with semaphore:
        try:
            jina_url = JINA_BASE + url
            resp = await client.get(jina_url, headers=HEADERS, timeout=20, follow_redirects=True)

            if resp.status_code != 200:
                return "", None

            markdown = resp.text.strip()
            if not markdown or len(markdown) < min_length:
                return "", None

            # Strip Jina metadata header (Title:, URL:, etc.) from the top
            lines = markdown.splitlines()
            body_lines = []
            in_header = True
            for line in lines:
                if in_header and re.match(r"^(Title|URL|Published|Description|Image|Author|Source):", line):
                    continue
                in_header = False
                body_lines.append(line)

            body = "\n".join(body_lines).strip()
            image_url = _extract_image_from_markdown(markdown)
            return body, image_url

        except Exception:
            return "", None


async def fetch_articles_batch(
    urls: list[str],
    client: httpx.AsyncClient,
    min_length: int = 100,
) -> list[tuple[str, Optional[str]]]:
    """Fetch multiple articles concurrently."""
    tasks = [fetch_article(url, client, min_length) for url in urls]
    return await asyncio.gather(*tasks)


def make_client() -> httpx.AsyncClient:
    """Create a shared async HTTP client for a pipeline run."""
    return httpx.AsyncClient(
        timeout=25,
        follow_redirects=True,
        headers={"User-Agent": "worldcup-engine/1.0"},
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    )
