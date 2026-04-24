from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    nome: str
    feed_url: str
    regiao_hint: str  # "BR", "Global", ou "Mixed"


SOURCES: list[Source] = [
    # Brasil — incluir tudo (filtro do pipeline aceita qualquer valor)
    Source(
        nome="Brazil Journal",
        feed_url="https://braziljournal.com/feed/",
        regiao_hint="BR",
    ),
    Source(
        nome="Neofeed",
        feed_url="https://www.neofeed.com.br/feed/",
        regiao_hint="BR",
    ),
    Source(
        nome="InfoMoney Mercados",
        feed_url="https://www.infomoney.com.br/mercados/feed/",
        regiao_hint="BR",
    ),
    Source(
        nome="Bloomberg Línea BR",
        feed_url="https://www.bloomberglinea.com.br/arc/outboundfeeds/rss/?outputType=xml",
        regiao_hint="BR",
    ),
    Source(
        nome="Google News M&A Brasil",
        feed_url=(
            "https://news.google.com/rss/search"
            "?q=%22aquisi%C3%A7%C3%A3o%22+OR+%22compra%22+OR+%22fus%C3%A3o%22+M%26A+Brasil"
            "&hl=pt-BR&gl=BR&ceid=BR:pt-419"
        ),
        regiao_hint="BR",
    ),

    # Global — filtro de tamanho (>=US$500M) aplicado no pipeline
    Source(
        nome="Google News M&A Global",
        feed_url=(
            "https://news.google.com/rss/search"
            "?q=%22mergers+and+acquisitions%22+OR+%22acquires%22+OR+%22to+buy%22"
            "&hl=en-US&gl=US&ceid=US:en"
        ),
        regiao_hint="Global",
    ),
    Source(
        nome="PR Newswire M&A",
        feed_url="https://www.prnewswire.com/rss/financial-services-latest-news/acquisitions-mergers-and-takeovers-list.rss",
        regiao_hint="Global",
    ),
    Source(
        nome="FT Companies",
        feed_url="https://www.ft.com/companies?format=rss",
        regiao_hint="Global",
    ),
    Source(
        nome="WSJ Business",
        feed_url="https://feeds.a.dj.com/rss/RSSWSJD.xml",
        regiao_hint="Global",
    ),
]
