from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import feedparser


@dataclass
class RawItem:
    titulo: str
    url: str
    fonte: str
    publicado_em: datetime | None
    resumo_fonte: str


def fetch_rss(feed_url: str, fonte: str) -> list[RawItem]:
    parsed = feedparser.parse(feed_url)
    items: list[RawItem] = []
    for entry in parsed.entries:
        published = None
        if getattr(entry, "published_parsed", None):
            published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        elif getattr(entry, "updated_parsed", None):
            published = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)

        items.append(
            RawItem(
                titulo=(entry.title or "").strip(),
                url=(entry.link or "").strip(),
                fonte=fonte,
                publicado_em=published,
                resumo_fonte=(getattr(entry, "summary", "") or "").strip(),
            )
        )
    return items
