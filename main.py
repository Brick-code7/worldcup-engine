from __future__ import annotations

import asyncio

from ingestors.reddit import ingest_reddit
from ingestors.google_news import ingest_google_news
from ingestors.rss import ingest_rss_feeds
from processing.normalize import normalize
from processing.filter import filter_items
from processing.classify import classify
from processing.rank import rank_items
from storage.database import init_db, save_items, get_pending_items
from output.formatter import write_output
from utils.scraper import make_client


async def run_pipeline():
    print("=" * 60)
    print("World Cup 2026 — Team News Pipeline")
    print("=" * 60)

    async with make_client() as client:

        # 1. Ingest all sources in parallel
        print("\n[Step 1] Ingesting sources...")
        reddit_items, google_items, rss_items = await asyncio.gather(
            ingest_reddit(client),
            ingest_google_news(client),
            ingest_rss_feeds(client),
        )

    all_items = reddit_items + google_items + rss_items
    print(f"\nIngested {len(all_items)} raw items "
          f"(Reddit: {len(reddit_items)}, Google News: {len(google_items)}, RSS: {len(rss_items)})")

    if not all_items:
        print("No items ingested. Check credentials and network.")
        return

    # 2. Normalize
    print("\n[Step 2] Normalizing...")
    normalized = normalize(all_items)

    # 3. Filter — World Cup 2026 headlines only
    print("\n[Step 3] Filtering...")
    filtered = filter_items(normalized)
    print(f"{len(filtered)} items passed World Cup filter")

    if not filtered:
        print("Nothing passed the filter.")
        return

    # 4. Classify — article type, urgency, entities
    print("\n[Step 4] Classifying...")
    classified = classify(filtered)

    # 5. Rank — injury/squad/breaking items bubble up
    print("\n[Step 5] Ranking...")
    ranked = rank_items(classified)

    # 6. Store
    print("\n[Step 6] Saving to database...")
    saved = save_items(ranked)
    print(f"Saved {saved} new items")

    # 7. Write Higgsfield-ready JSON output
    print("\n[Step 7] Writing output JSON for Higgsfield...")
    top_items = get_pending_items(limit=20)
    output_path = write_output(top_items)
    print(f"Output written → {output_path}")

    # 8. Preview top 5
    print("\n" + "=" * 60)
    print("TOP 5 TEAM NEWS ITEMS")
    print("=" * 60)
    for item in top_items[:5]:
        urgency_label = getattr(item, "urgency", "update").upper()
        type_label = (item.article_type or "other").upper()
        player = getattr(item, "player", None)
        team = getattr(item, "team", None)

        print(f"\n[{urgency_label}] [{type_label}] {item.headline}")
        print(f"  Player   : {player or '—'}  |  Team: {team or '—'}")
        print(f"  Published: {item.published_at.strftime('%Y-%m-%d %H:%M UTC')}  |  Rank: {item.rank_score:.0f}")
        print(f"  Body     : {len(item.body.split()) if item.body else 0} words  |  Image: {'✓' if item.image_url else '✗'}")
        print(f"  Source   : {item.source}")
        print(f"  URL      : {item.url}")
        if item.image_url:
            print(f"  Img URL  : {item.image_url}")

    print("\n" + "=" * 60)
    print("Pipeline complete.")
    print("=" * 60)


if __name__ == "__main__":
    init_db()
    asyncio.run(run_pipeline())
