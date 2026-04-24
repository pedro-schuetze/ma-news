from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone

from supabase import Client, create_client


def get_client() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_KEY"]
    return create_client(url, key)


def make_mention_hash(titulo: str, url: str) -> str:
    basis = f"{titulo.strip().lower()}|{url.strip().lower()}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:32]


def existing_mention_hashes(client: Client, hashes: list[str]) -> set[str]:
    if not hashes:
        return set()
    resp = (
        client.table("deal_mentions")
        .select("hash_dedup")
        .in_("hash_dedup", hashes)
        .execute()
    )
    return {row["hash_dedup"] for row in resp.data}


def find_existing_deal(
    client: Client,
    alvo_norm: str | None,
    comprador_norm: str | None,
    window_days: int = 14,
) -> dict | None:
    """Procura um deal recente com mesmo alvo+comprador normalizados.

    Tenta match exato primeiro. Se falhar, faz fallback por token-subset no alvo
    (mesmo comprador + um nome é subconjunto do outro, ex.: "brava" ⊂ "brava energia").

    Retorna o registro completo do deal (dict) ou None se não encontrar.
    """
    if not alvo_norm or not comprador_norm:
        return None

    cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()

    # 1) Match exato
    resp = (
        client.table("deals")
        .select("*")
        .eq("alvo_normalizado", alvo_norm)
        .eq("comprador_normalizado", comprador_norm)
        .gte("created_at", cutoff)
        .limit(1)
        .execute()
    )
    if resp.data:
        return resp.data[0]

    # 2) Fallback: mesmo comprador, alvo é subconjunto de tokens (ou vice-versa)
    resp = (
        client.table("deals")
        .select("*")
        .eq("comprador_normalizado", comprador_norm)
        .gte("created_at", cutoff)
        .execute()
    )
    alvo_tokens = set(alvo_norm.split())
    if not alvo_tokens:
        return None
    for deal in resp.data:
        other = deal.get("alvo_normalizado") or ""
        other_tokens = set(other.split())
        if not other_tokens:
            continue
        if alvo_tokens <= other_tokens or other_tokens <= alvo_tokens:
            return deal
    return None


def insert_deal(client: Client, deal: dict) -> dict:
    resp = client.table("deals").insert(deal).execute()
    return resp.data[0]


def insert_mention(client: Client, mention: dict) -> None:
    client.table("deal_mentions").insert(mention).execute()
