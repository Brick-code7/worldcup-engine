from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone

from config import DB_PATH
from models.content_item import ContentItem


def _get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = _get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS content_items (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            headline TEXT NOT NULL,
            body TEXT NOT NULL DEFAULT '',
            url TEXT NOT NULL UNIQUE,
            image_url TEXT,
            published_at TEXT NOT NULL,
            engagement_score INTEGER NOT NULL DEFAULT 0,
            article_type TEXT,
            raw TEXT NOT NULL DEFAULT '{}',
            ingested_at TEXT NOT NULL,
            rank_score REAL NOT NULL DEFAULT 0.0,
            status TEXT NOT NULL DEFAULT 'raw'
        )
    """)
    conn.commit()
    conn.close()
    print(f"  [DB] Initialized database at {DB_PATH}")


def _item_to_row(item: ContentItem) -> tuple:
    return (
        item.id,
        item.source,
        item.headline,
        item.body,
        item.url,
        item.image_url,
        item.published_at.isoformat() if item.published_at else "",
        item.engagement_score,
        item.article_type,
        json.dumps(item.raw, default=str),
        item.ingested_at.isoformat() if item.ingested_at else datetime.now(timezone.utc).isoformat(),
        item.rank_score,
        item.status,
    )


def _row_to_item(row: sqlite3.Row) -> ContentItem:
    def parse_dt(s):
        if not s:
            return datetime.now(timezone.utc)
        try:
            dt = datetime.fromisoformat(s)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return datetime.now(timezone.utc)

    item = ContentItem(
        id=row["id"],
        source=row["source"],
        headline=row["headline"],
        body=row["body"],
        url=row["url"],
        image_url=row["image_url"],
        published_at=parse_dt(row["published_at"]),
        engagement_score=row["engagement_score"],
        article_type=row["article_type"],
        raw=json.loads(row["raw"]) if row["raw"] else {},
        ingested_at=parse_dt(row["ingested_at"]),
        rank_score=row["rank_score"],
        status=row["status"],
    )
    return item


def save_items(items: list[ContentItem]) -> int:
    if not items:
        return 0

    conn = _get_connection()
    saved = 0

    for item in items:
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO content_items
                (id, source, headline, body, url, image_url, published_at,
                 engagement_score, article_type, raw, ingested_at, rank_score, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _item_to_row(item),
            )
            if conn.total_changes > saved:
                saved = conn.total_changes
        except Exception as e:
            print(f"  [DB] Error saving item '{item.headline[:50]}': {e}")
            continue

    conn.commit()

    # Count actually inserted rows
    cursor = conn.execute(
        "SELECT COUNT(*) FROM content_items WHERE ingested_at >= ?",
        (items[0].ingested_at.isoformat(),) if items else ("",),
    )
    result = cursor.fetchone()
    inserted = result[0] if result else 0
    conn.close()
    return inserted


def get_pending_items(limit: int = 10) -> list[ContentItem]:
    conn = _get_connection()
    cursor = conn.execute(
        """
        SELECT * FROM content_items
        WHERE status = 'raw'
        ORDER BY rank_score DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_item(row) for row in rows]


def mark_status(item_id: str, status: str) -> None:
    valid_statuses = {"raw", "queued", "generated", "published"}
    if status not in valid_statuses:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {valid_statuses}")

    conn = _get_connection()
    conn.execute(
        "UPDATE content_items SET status = ? WHERE id = ?",
        (status, item_id),
    )
    conn.commit()
    conn.close()
