from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone

from dotenv import load_dotenv

from collectors.rss import RawItem, fetch_rss
from collectors.sources import SOURCES
from db.client import (
    existing_mention_hashes,
    find_existing_deal,
    get_client,
    insert_deal,
    insert_mention,
    make_mention_hash,
)
from db.dedup import normalize_name
from extractor.claude_extractor import extract


def collect_all(lookback_hours: int) -> list[RawItem]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    items: list[RawItem] = []
    for src in SOURCES:
        try:
            raw = fetch_rss(src.feed_url, src.nome)
        except Exception as exc:
            print(f"[warn] falha coletando {src.nome}: {exc}")
            continue
        for item in raw:
            if item.publicado_em and item.publicado_em < cutoff:
                continue
            items.append(item)
    return items


def should_keep(deal: dict, min_global_usd: float) -> bool:
    if deal.get("regiao") == "BR":
        return True
    valor = deal.get("valor_usd")
    return valor is not None and valor >= min_global_usd


def _build_deal_row(extracted: dict, deal_date: date | None) -> dict:
    return {
        "data_anuncio": deal_date.isoformat() if deal_date else None,
        "alvo": extracted.get("alvo"),
        "alvo_normalizado": normalize_name(extracted.get("alvo")),
        "comprador": extracted.get("comprador"),
        "comprador_normalizado": normalize_name(extracted.get("comprador")),
        "regiao": extracted.get("regiao"),
        "pais": extracted.get("pais"),
        "setor": extracted.get("setor"),
        "subsetor": extracted.get("subsetor"),
        "valor_usd": extracted.get("valor_usd"),
        "valor_brl": extracted.get("valor_brl"),
        "tipo_transacao": extracted.get("tipo_transacao"),
        "status": extracted.get("status"),
        "resumo_uma_frase": extracted.get("resumo_uma_frase"),
    }


def _build_mention_row(item: RawItem, deal_id: int, hash_mention: str) -> dict:
    return {
        "deal_id": deal_id,
        "hash_dedup": hash_mention,
        "titulo": item.titulo,
        "url": item.url,
        "fonte": item.fonte,
        "data_publicacao": item.publicado_em.isoformat() if item.publicado_em else None,
        "texto_bruto": item.resumo_fonte,
    }


def run(lookback_hours: int = 24) -> dict:
    load_dotenv(override=True)
    client = get_client()
    min_global_usd = float(os.environ.get("GLOBAL_DEAL_MIN_USD", "500000000"))

    raw_items = collect_all(lookback_hours)
    print(f"[info] coletadas {len(raw_items)} notícias brutas")

    hashes = [make_mention_hash(item.titulo, item.url) for item in raw_items]
    seen = existing_mention_hashes(client, hashes)
    new_items = [(h, item) for h, item in zip(hashes, raw_items) if h not in seen]
    print(f"[info] {len(new_items)} são novas (após dedup de menções)")

    new_deals = 0
    new_mentions_on_existing = 0
    skipped_not_ma = 0
    skipped_threshold = 0

    for h, item in new_items:
        extracted = extract(item.titulo, item.resumo_fonte)
        if not extracted:
            skipped_not_ma += 1
            continue
        if not should_keep(extracted, min_global_usd):
            skipped_threshold += 1
            continue

        deal_date: date | None = None
        if item.publicado_em:
            deal_date = item.publicado_em.date()

        alvo_norm = normalize_name(extracted.get("alvo"))
        comprador_norm = normalize_name(extracted.get("comprador"))

        existing = find_existing_deal(client, alvo_norm, comprador_norm)
        if existing:
            insert_mention(client, _build_mention_row(item, existing["id"], h))
            new_mentions_on_existing += 1
            print(f"[+mention] deal #{existing['id']} ({existing.get('alvo')} <- {existing.get('comprador')}): {item.fonte}")
        else:
            deal_row = _build_deal_row(extracted, deal_date)
            created = insert_deal(client, deal_row)
            insert_mention(client, _build_mention_row(item, created["id"], h))
            new_deals += 1
            print(f"[+deal #{created['id']}] {created.get('alvo')} <- {created.get('comprador')} | {item.fonte}")

    summary = {
        "coletadas": len(raw_items),
        "novas_menções": len(new_items),
        "novos_deals": new_deals,
        "menções_em_deals_existentes": new_mentions_on_existing,
        "descartadas_não_ma": skipped_not_ma,
        "descartadas_threshold_global": skipped_threshold,
    }
    print(f"[done] {summary}")
    return summary


if __name__ == "__main__":
    run(lookback_hours=24)
