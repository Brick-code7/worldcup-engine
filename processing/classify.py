from __future__ import annotations

"""
Classifies each ContentItem into:
  - article_type: injury | squad | lineup | transfer | result | preview | other
  - urgency:      breaking | update | analysis
  - entities:     { player, team } extracted from headline + body lead

These drive the Higgsfield visual style and prompt construction.
"""

import re
from datetime import datetime, timezone, timedelta

from models.content_item import ContentItem


# --- Article type signal words ---

_TYPE_SIGNALS: dict[str, list[str]] = {
    "injury": [
        "injur", "doubt", "ruled out", "fitness", "hamstring", "ankle", "knee",
        "muscle", "strain", "knock", "limp", "concern", "scan", "surgery",
        "miss", "sidelined", "out for", "doubtful", "late fitness test",
        "fitness test", "injury scare", "injury blow", "injury update",
        "medical", "physio", "rehab", "recovery",
    ],
    "squad": [
        "squad", "roster", "named", "selected", "selection", "call-up", "called up",
        "omitted", "dropped", "included", "announced", "26-man", "23-man",
        "squad list", "final squad", "provisional squad", "team announcement",
        "squad announcement", "who's in", "who's out", "surprise inclusion",
        "snub", "snubbed", "left out",
    ],
    "lineup": [
        "lineup", "line-up", "starting xi", "starting eleven", "formation",
        "predicted lineup", "confirmed lineup", "team sheet", "tactics",
        "4-3-3", "4-2-3-1", "3-5-2", "press conference", "manager", "coach",
        "will start", "expected to start", "bench", "substitut",
    ],
    "transfer": [
        "transfer", "deal", "sign", "signing", "eligib", "switch nation",
        "nationality", "passport", "represent", "switch allegiance",
    ],
    "result": [
        "wins", "beats", "defeated", "draws", "scores", "goal", "match report",
        "full time", "final score", "highlights", "recap", "reaction",
    ],
    "preview": [
        "preview", "prediction", "odds", "betting", "who will win", "analysis",
        "group stage", "fixture", "schedule", "how to watch", "where to watch",
    ],
}

# --- Urgency signal words ---

_BREAKING_SIGNALS = [
    "breaking", "just in", "confirmed", "official", "announced", "named",
    "ruled out", "latest:", "alert:", "news:", "update:",
]

_ANALYSIS_SIGNALS = [
    "analysis", "opinion", "column", "why", "how", "explained",
    "everything you need to know", "guide to", "history of", "look back",
]

# --- Entity extraction ---

# Top WC 2026 players — ordered longest-match first to avoid partial matches
_KNOWN_PLAYERS = [
    ("Lionel Messi", ["messi", "leo messi", "lionel messi"]),
    ("Kylian Mbappé", ["mbappe", "mbappé", "kylian mbappe", "kylian mbappé"]),
    ("Jude Bellingham", ["bellingham", "jude bellingham"]),
    ("Harry Kane", ["harry kane", "kane"]),
    ("Bukayo Saka", ["saka", "bukayo saka"]),
    ("Lamine Yamal", ["yamal", "lamine yamal"]),
    ("Pedri", ["pedri"]),
    ("Erling Haaland", ["haaland", "erling haaland"]),
    ("Vinicius Jr", ["vinicius", "vini jr", "vinicius jr"]),
    ("Rodrygo", ["rodrygo"]),
    ("Neymar Jr", ["neymar"]),
    ("Marcus Rashford", ["rashford", "marcus rashford"]),
    ("Phil Foden", ["foden", "phil foden"]),
    ("Declan Rice", ["declan rice"]),
    ("Antoine Griezmann", ["griezmann"]),
    ("Kevin De Bruyne", ["de bruyne", "kevin de bruyne"]),
    ("Luka Modric", ["modric", "luka modric"]),
    ("Mohamed Salah", ["salah", "mo salah"]),
    ("Robert Lewandowski", ["lewandowski"]),
    ("Christian Pulisic", ["pulisic", "christian pulisic"]),
    ("Sergiño Dest", ["dest"]),
    ("Gio Reyna", ["reyna", "gio reyna"]),
    ("Tim Weah", ["weah", "tim weah"]),
    ("Alphonso Davies", ["davies", "alphonso davies"]),
    ("Jonathan David", ["jonathan david"]),
    ("Hirving Lozano", ["lozano", "hirving lozano", "chucky lozano"]),
    ("Son Heung-min", ["son heung", "heung-min son"]),
    ("Achraf Hakimi", ["hakimi"]),
    ("Victor Osimhen", ["osimhen"]),
]

_KNOWN_TEAMS = [
    ("Argentina",    ["argentina"]),
    ("Brazil",       ["brazil"]),
    ("France",       ["france"]),
    ("England",      ["england"]),
    ("Germany",      ["germany"]),
    ("Spain",        ["spain"]),
    ("Portugal",     ["portugal"]),
    ("Netherlands",  ["netherlands", "holland"]),
    ("Morocco",      ["morocco"]),
    ("USA",          ["usa", "usmnt", "united states"]),
    ("Mexico",       ["mexico"]),
    ("Canada",       ["canada"]),
    ("Japan",        ["japan"]),
    ("South Korea",  ["south korea", "korea"]),
    ("Australia",    ["australia", "socceroos"]),
    ("Nigeria",      ["nigeria"]),
    ("Senegal",      ["senegal"]),
    ("Colombia",     ["colombia"]),
    ("Uruguay",      ["uruguay"]),
    ("Croatia",      ["croatia"]),
    ("Denmark",      ["denmark"]),
    ("Switzerland",  ["switzerland"]),
    ("Poland",       ["poland"]),
    ("Ecuador",      ["ecuador"]),
    ("Serbia",       ["serbia"]),
]


def _classify_type(text: str) -> str:
    text_lower = text.lower()
    scores: dict[str, int] = {t: 0 for t in _TYPE_SIGNALS}
    for article_type, signals in _TYPE_SIGNALS.items():
        for signal in signals:
            if signal in text_lower:
                scores[article_type] += 1
    best = max(scores, key=lambda t: scores[t])
    return best if scores[best] > 0 else "other"


def _classify_urgency(item: ContentItem) -> str:
    hl = item.headline.lower()
    age_minutes = (datetime.now(timezone.utc) - item.published_at).total_seconds() / 60

    if any(sig in hl for sig in _BREAKING_SIGNALS) and age_minutes <= 90:
        return "breaking"
    if any(sig in hl for sig in _ANALYSIS_SIGNALS):
        return "analysis"
    if age_minutes <= 90:
        return "update"
    return "analysis"


def _extract_player(text: str) -> str | None:
    text_lower = text.lower()
    for name, aliases in _KNOWN_PLAYERS:
        if any(alias in text_lower for alias in aliases):
            return name
    return None


def _extract_team(text: str) -> str | None:
    text_lower = text.lower()
    for name, aliases in _KNOWN_TEAMS:
        if any(alias in text_lower for alias in aliases):
            return name
    return None


def classify(items: list[ContentItem]) -> list[ContentItem]:
    print("  [Classify] Classifying article types and extracting entities...")
    for item in items:
        # Use headline + first 300 chars of body for classification
        search_text = item.headline + " " + item.body[:300]
        item.article_type = _classify_type(search_text)
        item.urgency = _classify_urgency(item)  # type: ignore[attr-defined]
        item.player = _extract_player(search_text)  # type: ignore[attr-defined]
        item.team = _extract_team(search_text)      # type: ignore[attr-defined]

    type_counts = {}
    for item in items:
        type_counts[item.article_type] = type_counts.get(item.article_type, 0) + 1
    print(f"  [Classify] Types: {type_counts}")

    breaking = sum(1 for i in items if getattr(i, "urgency", "") == "breaking")
    print(f"  [Classify] Breaking items: {breaking}")

    return items
