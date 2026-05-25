from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ContentItem:
    id: str
    source: str              # "reddit" | "google_news" | "bbc" | etc.
    headline: str
    body: str                # full article text or post body, empty string if unavailable
    url: str
    image_url: Optional[str]
    published_at: datetime
    engagement_score: int    # upvotes, comments, or 0 for news
    article_type: Optional[str]  # injury | squad | lineup | transfer | result | preview | other
    raw: dict                # original source payload, stored for debugging
    ingested_at: datetime    # when our system collected it
    rank_score: float = 0.0  # computed during ranking phase
    status: str = "raw"      # raw | queued | generated | published
    # Populated by classify step
    urgency: str = "update"          # breaking | update | analysis
    player: Optional[str] = None     # primary player entity extracted from text
    team: Optional[str] = None       # primary team entity extracted from text
