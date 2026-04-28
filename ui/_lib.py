from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterable

import pandas as pd
import streamlit as st

from db.client import get_client


_COUNTRY_FLAGS = {
    # Principais países
    "brasil": "🇧🇷", "brazil": "🇧🇷", "br": "🇧🇷",
    "estados unidos": "🇺🇸", "eua": "🇺🇸", "united states": "🇺🇸", "usa": "🇺🇸", "us": "🇺🇸",
    "colombia": "🇨🇴", "colômbia": "🇨🇴",
    "alemanha": "🇩🇪", "germany": "🇩🇪",
    "canada": "🇨🇦", "canadá": "🇨🇦",
    "italia": "🇮🇹", "itália": "🇮🇹", "italy": "🇮🇹",
    "franca": "🇫🇷", "frança": "🇫🇷", "france": "🇫🇷",
    "reino unido": "🇬🇧", "uk": "🇬🇧", "united kingdom": "🇬🇧", "inglaterra": "🇬🇧",
    "espanha": "🇪🇸", "spain": "🇪🇸",
    "portugal": "🇵🇹",
    "japao": "🇯🇵", "japão": "🇯🇵", "japan": "🇯🇵",
    "china": "🇨🇳",
    "india": "🇮🇳", "índia": "🇮🇳",
    "mexico": "🇲🇽", "méxico": "🇲🇽",
    "argentina": "🇦🇷",
    "chile": "🇨🇱",
    "peru": "🇵🇪",
    "coreia do sul": "🇰🇷", "coréia do sul": "🇰🇷", "south korea": "🇰🇷",
    "australia": "🇦🇺", "austrália": "🇦🇺",
    "suica": "🇨🇭", "suíça": "🇨🇭", "switzerland": "🇨🇭",
    "holanda": "🇳🇱", "netherlands": "🇳🇱",
    "belgica": "🇧🇪", "bélgica": "🇧🇪", "belgium": "🇧🇪",
    "irlanda": "🇮🇪", "ireland": "🇮🇪",
    "singapura": "🇸🇬", "singapore": "🇸🇬",
}


def flag_for(pais: str | None, regiao: str | None = None) -> str:
    if pais:
        key = pais.strip().lower()
        if key in _COUNTRY_FLAGS:
            return _COUNTRY_FLAGS[key]
    if regiao == "BR":
        return "🇧🇷"
    return "🌐"


def format_value(valor_usd, valor_brl, valor_status: str | None = None) -> str:
    """Formata valor da transação. Se valor está null mas valor_status indica
    'nao_divulgado', retorna 'não divulgado' (distinto de 'n/d')."""
    if pd.notna(valor_usd):
        v = float(valor_usd)
        if v >= 1e9:
            return f"US$ {v / 1e9:.2f}bi"
        if v >= 1e6:
            return f"US$ {v / 1e6:.0f}M"
        return f"US$ {v / 1e3:.0f}k"
    if pd.notna(valor_brl):
        v = float(valor_brl)
        if v >= 1e9:
            return f"R$ {v / 1e9:.2f}bi"
        if v >= 1e6:
            return f"R$ {v / 1e6:.0f}M"
        return f"R$ {v / 1e3:.0f}k"
    if valor_status == "nao_divulgado":
        return "não divulgado"
    return "n/d"


def format_date_pt(d) -> str:
    if d is None or pd.isna(d):
        return ""
    if isinstance(d, str):
        try:
            d = datetime.fromisoformat(d).date()
        except ValueError:
            return d
    if isinstance(d, datetime):
        d = d.date()
    meses = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
    return f"{d.day} {meses[d.month - 1]} {d.year}"


def format_date_pt_relative(d) -> str:
    """Como format_date_pt, mas devolve 'Hoje'/'Ontem' quando aplicável."""
    if d is None or pd.isna(d):
        return ""
    if isinstance(d, str):
        try:
            d = datetime.fromisoformat(d).date()
        except ValueError:
            return d
    if isinstance(d, datetime):
        d = d.date()
    today = date.today()
    if d == today:
        return "Hoje"
    if d == today - timedelta(days=1):
        return "Ontem"
    return format_date_pt(d)


def render_header(subtitle: str | None = None) -> None:
    """Barra de topo consistente entre as páginas."""
    df = load_deals()
    last_update = None
    if not df.empty and "created_at" in df.columns and df["created_at"].notna().any():
        try:
            last_update = pd.to_datetime(df["created_at"]).max()
        except Exception:
            last_update = None

    total = 0 if df.empty else len(df)

    left, right = st.columns([3, 1])
    with left:
        st.markdown(
            "<div style='font-size:13px;letter-spacing:2px;color:#6aa6ff;font-weight:600;"
            "text-transform:uppercase;'>📈 M&amp;A News</div>"
            f"<div style='font-size:13px;color:#8a93a0;margin-top:2px;'>"
            f"{subtitle or 'Transações de M&amp;A no Brasil e no mundo'}</div>",
            unsafe_allow_html=True,
        )
    with right:
        label = "Última atualização"
        value = "—"
        if last_update is not None:
            value = last_update.strftime("%d/%m %H:%M")
        st.markdown(
            f"<div style='text-align:right;font-size:11px;color:#8a93a0;'>{label}</div>"
            f"<div style='text-align:right;font-size:13px;color:#b0bfd4;font-weight:500;'>"
            f"{value} · {total} deals na base</div>",
            unsafe_allow_html=True,
        )
    st.markdown("<hr style='margin:10px 0 18px 0;border:none;border-top:1px solid rgba(128,128,128,0.2);'>", unsafe_allow_html=True)


@st.cache_data(ttl=300)
def load_deals() -> pd.DataFrame:
    client = get_client()
    rows = client.table("deals").select("*").order("data_anuncio", desc=True).execute().data
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["data_anuncio"] = pd.to_datetime(df["data_anuncio"], errors="coerce").dt.date
    for col in ["valor_usd", "valor_brl"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


@st.cache_data(ttl=300)
def load_mentions_for(deal_ids: Iterable[int]) -> pd.DataFrame:
    deal_ids = list(deal_ids)
    if not deal_ids:
        return pd.DataFrame()
    client = get_client()
    rows = (
        client.table("deal_mentions")
        .select("deal_id,titulo,url,fonte,data_publicacao")
        .in_("deal_id", deal_ids)
        .order("data_publicacao", desc=True)
        .execute()
        .data
    )
    return pd.DataFrame(rows)


def fetch_deal(deal_id: int) -> dict | None:
    """Sem cache — usado na página de detalhes, onde precisamos sempre
    ver o estado atual (após edições)."""
    client = get_client()
    resp = client.table("deals").select("*").eq("id", deal_id).limit(1).execute()
    return resp.data[0] if resp.data else None


def fetch_mentions_full(deal_id: int) -> list[dict]:
    """Retorna todas as colunas das menções, inclusive texto_bruto."""
    client = get_client()
    resp = (
        client.table("deal_mentions")
        .select("*")
        .eq("deal_id", deal_id)
        .order("data_publicacao", desc=True)
        .execute()
    )
    return resp.data or []


def open_deal(deal_id: int) -> None:
    """Callback para abrir o drill-down do deal dentro da seção atual.
    Apenas guarda o id em session_state — o render da seção decide se
    mostra a lista ou os detalhes. Evita full reload (que quebraria auth)
    e não chama st.rerun()/st.switch_page() dentro do callback."""
    st.session_state["selected_deal_id"] = int(deal_id)
    st.session_state["edit_mode"] = False


def close_deal() -> None:
    """Callback para voltar da view de detalhes para a lista da seção."""
    st.session_state.pop("selected_deal_id", None)
    st.session_state["edit_mode"] = False


def update_deal(deal_id: int, fields: dict) -> None:
    """Atualiza campos de um deal. Se alvo/comprador mudaram, re-normaliza."""
    from db.dedup import normalize_name

    payload = dict(fields)
    if "alvo" in payload:
        payload["alvo_normalizado"] = normalize_name(payload.get("alvo"))
    if "comprador" in payload:
        payload["comprador_normalizado"] = normalize_name(payload.get("comprador"))

    client = get_client()
    client.table("deals").update(payload).eq("id", deal_id).execute()
    load_deals.clear()
    load_mentions_for.clear()
