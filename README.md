# World Cup 2026 Content Engine — Phase 1: Ingestion

Collects, cleans, and stores football news from Reddit, Google News, and RSS feeds into a local SQLite database. This is the data pipeline layer only — no content is generated or published.

## Setup

```bash
cp .env.example .env
# Fill in Reddit credentials in .env
pip install -r requirements.txt
python main.py
```

## Reddit credentials

1. Go to https://www.reddit.com/prefs/apps
2. Create a "script" type application
3. Copy the client ID and secret into `.env`

Reddit credentials are optional — the pipeline will run with Google News and RSS feeds if they're not provided.

## What it does

1. **Ingest** — fetches posts from r/soccer, r/worldcup, r/football + Google News RSS + BBC/Goal/Sky Sports/ESPN/Guardian feeds in parallel
2. **Normalize** — strips HTML, normalizes whitespace, truncates body to 2000 words, assigns UUIDs
3. **Filter** — keeps only World Cup relevant items, drops low-quality entries, deduplicates similar headlines with fuzzy matching
4. **Rank** — scores items by recency, engagement, image presence, body length, and source diversity
5. **Store** — saves to `./data/worldcup.db` (SQLite), skipping already-seen URLs

## Database

Single table: `content_items`. Items start with `status = 'raw'`. Future phases read from this table and update status to `queued → generated → published`.

```python
from storage.database import get_pending_items, mark_status

items = get_pending_items(limit=10)
mark_status(item.id, "queued")
```

## Project structure

```
worldcup-engine/
├── main.py              # Entry point
├── config.py            # All config and constants
├── ingestors/           # One file per source
├── processing/          # normalize → filter → rank
├── storage/             # SQLite wrapper
├── models/              # ContentItem dataclass
└── data/                # worldcup.db created here at runtime
```
