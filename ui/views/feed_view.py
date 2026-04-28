from __future__ import annotations

import os
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from _deal_detail import render_deal_detail
from _lib import (
    flag_for,
    format_date_pt,
    format_date_pt_relative,
    format_value,
    load_deals,
    load_mentions_for,
    open_deal,
    render_header,
)


CARD_CSS = """
<style>
.deal-card-inner {
    padding: 4px 6px 0 6px;
}
.deal-card-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
    font-size: 0.88rem;
    opacity: 0.7;
}
.deal-card-head .flag { font-size: 1.3rem; margin-right: 8px; }
.deal-card-head .setor { font-weight: 500; }
.deal-card-head .date { font-size: 0.82rem; }
.deal-card-title {
    font-size: 1.3rem;
    font-weight: 600;
    margin: 4px 0 2px 0;
    line-height: 1.3;
}
.deal-card-title .arrow { opacity: 0.5; margin: 0 10px; font-weight: 400; }
.deal-card-value {
    display: inline-block;
    font-size: 1rem;
    font-weight: 600;
    color: #047857;
    padding: 2px 10px;
    border: 1px solid rgba(4, 120, 87, 0.35);
    border-radius: 6px;
    margin: 6px 0 10px 0;
    background: rgba(16, 185, 129, 0.1);
}
.deal-card-value.unknown {
    color: inherit;
    opacity: 0.55;
    border-color: rgba(128, 128, 128, 0.3);
    background: rgba(128, 128, 128, 0.08);
}
.deal-card-value.undisclosed {
    color: inherit;
    opacity: 0.7;
    border-color: rgba(128, 128, 128, 0.35);
    background: rgba(128, 128, 128, 0.1);
    font-weight: 500;
    font-size: 0.88rem;
}
.deal-card-mega {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    background: rgba(212, 160, 23, 0.18);
    color: #d4a017;
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-right: 8px;
}
.deal-card-inner.is-mega {
    border-left: 4px solid #d4a017;
    background: rgba(212, 160, 23, 0.06);
    padding: 12px 16px;
    margin: -4px -6px 0 -6px;
    border-radius: 6px;
}
.deal-card-summary {
    font-size: 0.96rem;
    line-height: 1.5;
    margin-bottom: 12px;
    opacity: 0.88;
}
.deal-card-foot {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.85rem;
    opacity: 0.75;
    flex-wrap: wrap;
    gap: 8px;
}
.deal-card-foot .tipo {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    background: rgba(100, 120, 180, 0.18);
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-weight: 600;
}
.deal-card-foot .sources a {
    color: #0969da;
    text-decoration: none;
    margin-left: 4px;
}
.deal-card-foot .sources a:hover { text-decoration: underline; }
.deal-card-foot .sources .sep { opacity: 0.4; margin: 0 4px; }
.feed-date-header {
    font-size: 1.05rem;
    font-weight: 600;
    margin: 18px 0 8px 0;
    padding-bottom: 4px;
    border-bottom: 1px solid rgba(128, 128, 128, 0.2);
    opacity: 0.85;
}
</style>
"""


def _render_card(deal: pd.Series, mentions: pd.DataFrame) -> None:
    flag = flag_for(deal.get("pais"), deal.get("regiao"))
    setor = deal.get("setor") or "—"
    subsetor = deal.get("subsetor")
    setor_line = f"{setor}" + (f" · {subsetor}" if subsetor else "")
    data_str = format_date_pt(deal.get("data_anuncio"))
    comprador = deal.get("comprador") or "?"
    alvo = deal.get("alvo") or "?"
    valor = format_value(deal.get("valor_usd"), deal.get("valor_brl"), deal.get("valor_status"))
    if valor == "n/d":
        valor_class = "unknown"
    elif valor == "não divulgado":
        valor_class = "undisclosed"
    else:
        valor_class = ""
    resumo = deal.get("resumo_uma_frase") or ""
    tipo = (deal.get("tipo_transacao") or "").upper()

    if mentions is not None and not mentions.empty:
        deal_mentions = mentions[mentions["deal_id"] == deal["id"]]
    else:
        deal_mentions = pd.DataFrame()

    source_links = []
    for _, m in deal_mentions.iterrows():
        source_links.append(f'<a href="{m["url"]}" target="_blank" rel="noopener">{m["fonte"]}</a>')
    if not source_links:
        sources_html = '<span style="color:#6a727e;">sem menções</span>'
    else:
        sep = '<span class="sep">·</span>'
        sources_html = sep.join(source_links)

    # Mega deal: US$5bi+ (ou R$10bi+ se só tiver BRL)
    mega_threshold_usd = float(os.environ.get("MEGA_DEAL_USD", "5000000000"))
    mega_threshold_brl = float(os.environ.get("MEGA_DEAL_BRL", "10000000000"))
    valor_usd_raw = deal.get("valor_usd")
    valor_brl_raw = deal.get("valor_brl")
    is_mega = (
        (pd.notna(valor_usd_raw) and float(valor_usd_raw) >= mega_threshold_usd)
        or (
            not pd.notna(valor_usd_raw)
            and pd.notna(valor_brl_raw)
            and float(valor_brl_raw) >= mega_threshold_brl
        )
    )
    mega_badge = '<span class="deal-card-mega">⭐ Mega deal</span>' if is_mega else ""
    inner_class = "deal-card-inner is-mega" if is_mega else "deal-card-inner"

    deal_id = int(deal["id"])
    inner_html = f"""
    <div class="{inner_class}">
        <div class="deal-card-head">
            <div><span class="flag">{flag}</span><span class="setor">{setor_line}</span></div>
            <div class="date">{data_str}</div>
        </div>
        <div class="deal-card-title">
            <span>{comprador}</span><span class="arrow">→</span><span>{alvo}</span>
        </div>
        <div class="deal-card-value {valor_class}">{valor}</div>
        <div class="deal-card-summary">{resumo}</div>
        <div class="deal-card-foot">
            <span>{mega_badge}<span class="tipo">{tipo}</span></span>
            <span class="sources">📰 {sources_html}</span>
        </div>
    </div>
    """

    with st.container(border=True):
        st.markdown(inner_html, unsafe_allow_html=True)
        _, right = st.columns([5, 1])
        right.button(
            "🔍 Abrir deal",
            key=f"open_deal_{deal_id}",
            on_click=open_deal,
            args=(deal_id,),
            width="stretch",
        )


def render() -> None:
    st.markdown(CARD_CSS, unsafe_allow_html=True)
    render_header("Feed de transações — mais recentes primeiro")

    # Drill-down: se um deal está selecionado, mostra os detalhes em vez da lista.
    selected = st.session_state.get("selected_deal_id")
    if selected is not None:
        render_deal_detail(int(selected), back_label="← Voltar ao feed")
        return

    df = load_deals()
    if df.empty:
        st.warning("Nenhum deal na base ainda. Rode `python pipeline.py` primeiro.")
        return

    with st.sidebar:
        st.header("Período")
        periodo = st.radio(
            "Mostrar deals dos últimos:",
            ["7 dias", "30 dias", "90 dias", "Tudo"],
            index=1,
        )
        regiao_filtro = st.radio("Região", ["Todos", "BR", "Global"], index=0, horizontal=True)

    hoje = date.today()
    if periodo != "Tudo":
        dias = {"7 dias": 7, "30 dias": 30, "90 dias": 90}[periodo]
        inicio = hoje - timedelta(days=dias)
        df = df[df["data_anuncio"].fillna(hoje) >= inicio]
    if regiao_filtro != "Todos":
        df = df[df["regiao"] == regiao_filtro]

    display_min_global = float(os.environ.get("DISPLAY_MIN_USD_GLOBAL", "500000000"))
    mask_br = df["regiao"] == "BR"
    mask_global_ok = (df["regiao"] == "Global") & (df["valor_usd"].fillna(0) >= display_min_global)
    df = df[mask_br | mask_global_ok]

    df = df.sort_values(by="data_anuncio", ascending=False, na_position="last")

    c1, c2, c3 = st.columns(3)
    c1.metric("Deals", len(df))
    c2.metric("Brasil", int((df["regiao"] == "BR").sum()))
    c3.metric("Global", int((df["regiao"] == "Global").sum()))

    if df.empty:
        st.info("Nenhum deal no período selecionado.")
        return

    mentions = load_mentions_for(df["id"].tolist())

    current_date = None
    for _, deal in df.iterrows():
        dt = deal.get("data_anuncio")
        if dt != current_date:
            label = format_date_pt_relative(dt) or "Sem data"
            st.markdown(f"<div class='feed-date-header'>{label}</div>", unsafe_allow_html=True)
            current_date = dt
        _render_card(deal, mentions)
