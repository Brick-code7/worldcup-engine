from __future__ import annotations

"""
Database layer using Supabase (hosted PostgreSQL).

Env vars required:
  SUPABASE_URL   e.g. https://xxxx.supabase.co
  SUPABASE_KEY   anon/public key from Settings → API
"""

import json
import os
from datetime import datetime, timezone
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

from models.content_item import ContentItem


def _url() -> str:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    if not url:
        raise RuntimeError("SUPABASE_URL is not set. Add it to your .env file.")
    return url


def _key() -> str:
    key = os.getenv("SUPABASE_KEY", "")
    if not key:
        raise RuntimeError("SUPABASE_KEY is not set. Add it to your .env file.")
    return key


def _headers(extra: dict | None = None) -> dict:
    h = {
        "apikey": _key(),
        "Authorization": f"Bearer {_key()}",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def _parse_dt(s: str | None) -> datetime:
    if not s:
        return datetime.now(timezone.utc)
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def _row_to_item(row: dict) -> ContentItem:
    return ContentItem(
        id=row["id"],
        source=row["source"],
        headline=row["headline"],
        body=row.get("body") or "",
        url=row["url"],
        image_url=row.get("image_url"),
        published_at=_parse_dt(row.get("published_at")),
        engagement_score=int(row.get("engagement_score") or 0),
        article_type=row.get("article_type"),
        raw=json.loads(row.get("raw") or "{}"),
        ingested_at=_parse_dt(row.get("ingested_at")),
        rank_score=float(row.get("rank_score") or 0.0),
        status=row.get("status") or "raw",
        urgency=row.get("urgency") or "update",
        player=row.get("player"),
        team=row.get("team"),
    )


def init_db() -> None:
    """Verify the connection and table exist."""
    try:
        resp = httpx.get(
            f"{_url()}/rest/v1/content_items?limit=1",
            headers=_headers(),
            timeout=15,
        )
        if resp.status_code == 404:
            raise RuntimeError(
                "Table 'content_items' not found. "
                "Run the CREATE TABLE SQL in the Supabase SQL editor first."
            )
        resp.raise_for_status()
        print("  [DB] Supabase connected")
    except httpx.HTTPStatusError as e:
        raise RuntimeError(
            f"Supabase connection error {e.response.status_code}: {e.response.text}"
        ) from e


def save_items(items: list[ContentItem]) -> int:
    if not items:
        return 0

    rows = [
        {
            "id": item.id,
            "source": item.source,
            "headline": item.headline,
            "body": item.body,
            "url": item.url,
            "image_url": item.image_url,
            "published_at": item.published_at.isoformat(),
            "engagement_score": item.engagement_score,
            "article_type": item.article_type,
            "raw": json.dumps(item.raw, default=str),
            "ingested_at": item.ingested_at.isoformat(),
            "rank_score": item.rank_score,
            "status": item.status,
            "urgency": item.urgency,
            "player": item.player,
            "team": item.team,
        }
        for item in items
    ]

    try:
        resp = httpx.post(
            f"{_url()}/rest/v1/content_items",
            headers=_headers({
                "Prefer": "resolution=ignore-duplicates,return=representation",
            }),
            json=rows,
            timeout=30,
        )
        resp.raise_for_status()
        saved = len(resp.json()) if resp.text else 0
        return saved
    except httpx.HTTPStatusError as e:
        raise RuntimeError(
            f"Supabase save error {e.response.status_code}: {e.response.text}"
        ) from e


def get_pending_items(limit: int = 20) -> list[ContentItem]:
    try:
        resp = httpx.get(
            f"{_url()}/rest/v1/content_items",
            headers=_headers({"Range": f"0-{limit - 1}"}),
            params={
                "status": "eq.raw",
                "order": "rank_score.desc",
                "limit": str(limit),
            },
            timeout=15,
        )
        resp.raise_for_status()
        return [_row_to_item(r) for r in resp.json()]
    except httpx.HTTPStatusError as e:
        raise RuntimeError(
            f"Supabase fetch error {e.response.status_code}: {e.response.text}"
        ) from e


def mark_status(item_id: str, status: str) -> None:
    valid = {"raw", "queued", "generated", "published"}
    if status not in valid:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {valid}")

    try:
        resp = httpx.patch(
            f"{_url()}/rest/v1/content_items",
            headers=_headers({"Prefer": "return=minimal"}),
            params={"id": f"eq.{item_id}"},
            json={"status": status},
            timeout=15,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise RuntimeError(
            f"Supabase update error {e.response.status_code}: {e.response.text}"
        ) from e
