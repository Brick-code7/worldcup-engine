from __future__ import annotations

"""
Database layer using Turso (hosted libSQL / SQLite-compatible).

Turso persists across routine runs — unlike a local SQLite file which is
lost when the cloned repo is discarded at the end of each routine session.

Env vars required:
  TURSO_DATABASE_URL  e.g. libsql://worldcup-engine-xxx.turso.io
  TURSO_AUTH_TOKEN    JWT token from `turso db tokens create <db>`
"""

import json
import os
from datetime import datetime, timezone
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

from models.content_item import ContentItem


def _turso_url() -> str:
    url = os.getenv("TURSO_DATABASE_URL", "")
    if not url:
        raise RuntimeError("TURSO_DATABASE_URL is not set. Add it to your .env file.")
    # Convert libsql:// → https:// for the HTTP API
    return url.replace("libsql://", "https://")


def _turso_token() -> str:
    token = os.getenv("TURSO_AUTH_TOKEN", "")
    if not token:
        raise RuntimeError("TURSO_AUTH_TOKEN is not set. Add it to your .env file.")
    return token


def _execute(statements: list[dict[str, Any]]) -> list[dict]:
    """
    Execute one or more SQL statements via Turso's HTTP pipeline API.
    Returns the results list from the response.
    """
    requests = [{"type": "execute", "stmt": s} for s in statements]
    requests.append({"type": "close"})

    try:
        resp = httpx.post(
            f"{_turso_url()}/v2/pipeline",
            headers={
                "Authorization": f"Bearer {_turso_token()}",
                "Content-Type": "application/json",
            },
            json={"requests": requests},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("results", [])
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"Turso HTTP error {e.response.status_code}: {e.response.text}") from e


def _val(cell: dict) -> Any:
    """Parse a Turso cell value — cells are {'type': 'text'|'integer'|'float'|'null', 'value': ...}"""
    if cell.get("type") == "null":
        return None
    return cell.get("value")


def _row_to_item(cols: list[str], row: list[dict]) -> ContentItem:
    data = {cols[i]: _val(row[i]) for i in range(len(cols))}

    def parse_dt(s: str | None) -> datetime:
        if not s:
            return datetime.now(timezone.utc)
        try:
            dt = datetime.fromisoformat(s)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return datetime.now(timezone.utc)

    return ContentItem(
        id=data["id"],
        source=data["source"],
        headline=data["headline"],
        body=data.get("body") or "",
        url=data["url"],
        image_url=data.get("image_url"),
        published_at=parse_dt(data.get("published_at")),
        engagement_score=int(data.get("engagement_score") or 0),
        article_type=data.get("article_type"),
        raw=json.loads(data.get("raw") or "{}"),
        ingested_at=parse_dt(data.get("ingested_at")),
        rank_score=float(data.get("rank_score") or 0.0),
        status=data.get("status") or "raw",
        urgency=data.get("urgency") or "update",
        player=data.get("player"),
        team=data.get("team"),
    )


def init_db() -> None:
    _execute([{
        "sql": """
            CREATE TABLE IF NOT EXISTS content_items (
                id               TEXT PRIMARY KEY,
                source           TEXT NOT NULL,
                headline         TEXT NOT NULL,
                body             TEXT NOT NULL DEFAULT '',
                url              TEXT NOT NULL UNIQUE,
                image_url        TEXT,
                published_at     TEXT NOT NULL,
                engagement_score INTEGER NOT NULL DEFAULT 0,
                article_type     TEXT,
                raw              TEXT NOT NULL DEFAULT '{}',
                ingested_at      TEXT NOT NULL,
                rank_score       REAL NOT NULL DEFAULT 0.0,
                status           TEXT NOT NULL DEFAULT 'raw',
                urgency          TEXT NOT NULL DEFAULT 'update',
                player           TEXT,
                team             TEXT
            )
        """,
        "args": [],
    }])
    print("  [DB] Turso database initialised")


def save_items(items: list[ContentItem]) -> int:
    if not items:
        return 0

    statements = []
    for item in items:
        statements.append({
            "sql": """
                INSERT OR IGNORE INTO content_items
                (id, source, headline, body, url, image_url, published_at,
                 engagement_score, article_type, raw, ingested_at, rank_score,
                 status, urgency, player, team)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            "args": [
                {"type": "text",    "value": item.id},
                {"type": "text",    "value": item.source},
                {"type": "text",    "value": item.headline},
                {"type": "text",    "value": item.body},
                {"type": "text",    "value": item.url},
                {"type": "text",    "value": item.image_url} if item.image_url else {"type": "null"},
                {"type": "text",    "value": item.published_at.isoformat()},
                {"type": "integer", "value": str(item.engagement_score)},
                {"type": "text",    "value": item.article_type} if item.article_type else {"type": "null"},
                {"type": "text",    "value": json.dumps(item.raw, default=str)},
                {"type": "text",    "value": item.ingested_at.isoformat()},
                {"type": "float",   "value": float(item.rank_score)},
                {"type": "text",    "value": item.status},
                {"type": "text",    "value": item.urgency},
                {"type": "text",    "value": item.player} if item.player else {"type": "null"},
                {"type": "text",    "value": item.team} if item.team else {"type": "null"},
            ],
        })

    results = _execute(statements)

    # Count successful inserts (rows_affected > 0 means it wasn't a duplicate)
    saved = sum(
        1 for r in results
        if r.get("type") == "ok"
        and r.get("response", {}).get("result", {}).get("rows_affected", 0) > 0
    )
    return saved


def get_pending_items(limit: int = 10) -> list[ContentItem]:
    results = _execute([{
        "sql": "SELECT * FROM content_items WHERE status = 'raw' ORDER BY rank_score DESC LIMIT ?",
        "args": [{"type": "integer", "value": str(limit)}],
    }])

    if not results or results[0].get("type") != "ok":
        return []

    result_data = results[0]["response"]["result"]
    cols = [c["name"] for c in result_data["cols"]]
    return [_row_to_item(cols, row) for row in result_data["rows"]]


def mark_status(item_id: str, status: str) -> None:
    valid = {"raw", "queued", "generated", "published"}
    if status not in valid:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {valid}")

    _execute([{
        "sql": "UPDATE content_items SET status = ? WHERE id = ?",
        "args": [
            {"type": "text", "value": status},
            {"type": "text", "value": item_id},
        ],
    }])
