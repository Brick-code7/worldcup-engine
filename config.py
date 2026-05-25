from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()

# Reddit
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "worldcup-engine/1.0")

# Pipeline
MAX_ARTICLE_AGE_HOURS = int(os.getenv("MAX_ARTICLE_AGE_HOURS", "6"))
MIN_REDDIT_SCORE = int(os.getenv("MIN_REDDIT_SCORE", "50"))
DB_PATH = os.getenv("DB_PATH", "./data/worldcup.db")

# Active content bucket — controls which output formatter runs
# Options: "team_news" (more buckets added in later phases)
ACTIVE_BUCKET = "team_news"

# Items published within this many minutes are treated as "breaking"
BREAKING_THRESHOLD_MINUTES = 90

# Reddit — r/worldcup for dedicated WC discussion; r/soccer for breaking news & highlights
REDDIT_SUBREDDITS = ["worldcup", "soccer"]
REDDIT_POST_LIMIT = 50

# RSS feeds — confirmed live as of May 2026
# Priority order: WC-specific first, then broad-football sources (filtered down by headline)
RSS_FEEDS = [
    {"name": "espn_worldcup", "url": "https://www.espn.com/espn/rss/soccer/worldcup"},
    {"name": "espn_soccer",   "url": "https://www.espn.com/espn/rss/soccer/news"},
    {"name": "cbssports",     "url": "https://www.cbssports.com/rss/headlines/soccer/"},
    {"name": "yahoo_soccer",  "url": "https://sports.yahoo.com/soccer/rss"},
    {"name": "90min",         "url": "https://www.90min.com/posts.rss"},
    {"name": "bbc",           "url": "http://feeds.bbci.co.uk/sport/football/rss.xml"},
    {"name": "guardian",      "url": "https://www.theguardian.com/football/rss"},
    {"name": "skysports",     "url": "https://www.skysports.com/rss/12040"},
]

# Google News — exact-phrase queries focused entirely on TEAM NEWS
# Using %22 = " for exact phrase matching in Google News RSS
GOOGLE_NEWS_QUERIES = [
    # Injury & fitness — highest value, most time-sensitive
    '%22World+Cup+2026%22+injury+ruled+out+doubt',
    # Squad announcements — official selections
    '%22World+Cup+2026%22+squad+named+roster+announced',
    # Lineup & tactics — starting XIs and formation news
    '%22World+Cup+2026%22+lineup+starting+eleven+tactics',
    # Manager press conferences & selection calls
    '%222026+FIFA+World+Cup%22+press+conference+manager+squad',
    # Catch-all breaking team news
    '%222026+FIFA+World+Cup%22+team+news+update',
]

GOOGLE_NEWS_RSS_BASE = "https://news.google.com/rss/search?q={query}&hl=en&gl=US&ceid=US:en"

# --- Relevance filter keywords ---

# Players who matter for WC 2026 squad/injury stories
WC_PLAYER_KEYWORDS = [
    # Europe
    "mbappe", "mbappé", "bellingham", "kane", "saka", "rashford",
    "de bruyne", "haaland", "yamal", "pedri", "gavi", "williams",
    "modric", "griezmann", "salah", "lewandowski", "mueller", "müller",
    # Americas
    "messi", "neymar", "vinicius", "rodrygo", "raphinha",
    "pulisic", "reyna", "weah", "adams", "lozano", "jimenez",
    "davies", "buchanan", "david", "ferrari",
    # Africa / Asia
    "osimhen", "ziyech", "hakimi", "son heung", "minamino",
    # Key managers
    "southgate", "deschamps", "scaloni", "berhalter",
]

# National teams competing at WC 2026
WC_TEAM_KEYWORDS = [
    "argentina", "brazil", "france", "england", "germany", "spain",
    "portugal", "netherlands", "morocco", "usa", "usmnt", "mexico",
    "canada", "japan", "south korea", "australia", "nigeria",
    "senegal", "colombia", "uruguay", "ecuador", "croatia",
    "denmark", "switzerland", "poland", "serbia", "iran",
    "saudi arabia", "costa rica", "panama", "honduras",
    "el salvador", "ivory coast", "ghana", "cameroon",
]

# Tournament-specific terms — only meaningful in a WC context
WC_TERM_KEYWORDS = [
    "group stage", "knockout stage", "round of 32", "round of 16",
    "quarter-final", "quarter final", "semi-final", "semi final",
    "third place", "golden boot", "golden glove", "var decision",
    "penalty shootout",
    "squad announcement", "injury update", "fitness doubt",
    "starting eleven", "tactical preview", "manager presser",
    "world cup opener", "opening ceremony",
]

# All combined — used in Tier 2 of the relevance filter
WORLD_CUP_KEYWORDS = WC_PLAYER_KEYWORDS + WC_TEAM_KEYWORDS + WC_TERM_KEYWORDS

# RSS fetch delay between articles per domain (seconds)
RSS_FETCH_DELAY = 2.0

# Min scraped body length to count as usable
MIN_BODY_LENGTH = 100

# Max body length in words to store
MAX_BODY_WORDS = 2000

# Deduplication fuzzy match threshold (0–100)
DEDUP_SIMILARITY_THRESHOLD = 85
