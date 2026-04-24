from __future__ import annotations

import os
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from _lib import flag_for, format_date_pt, format_value, load_deals, load_mentions_for


CARD_CSS = """
<style>
.deal-card {
    border: 1px solid rgba(128, 128, 128, 0.2);
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 16px;
    background: rgba(255, 255, 255, 0.02);
    transition: border-color 0.15s ease, background 0.15s ease;
}
.deal-card:hover {
    border-color: rgba(128, 128, 128, 0.45);
    background: rgba(255, 255, 255, 0.04);
}
.deal-card-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
    font-size: 0.9rem;
    color: #9aa3ad;
}
.deal-card-head .flag { font-size: 1.4rem; margin-right: 6px; }
.deal-card-head .setor { font-weight: 500; }
.deal-card-head .date { font-size: 0.85rem; }
.deal-card-title {
    font-size: 1.35rem;
    font-weight: 600;
    margin: 4px 0 2px 0;
    line-height: 1.3;
}
.deal-card-title .arrow { color: #7a8591; margin: 0 10px; font-weight: 400; }
.deal-card-value {
    display: inline-block;
    font-size: 1.05rem;
    font-weight: 600;
    color: #00a86b;
    padding: 2px 10px;
    border: 1px solid rgba(0, 168, 107, 0.3);
    border-radius: 6px;
    margin: 6px 0 10px 0;
    background: rgba(0, 168, 107, 0.06);
}
.deal-card-value.unknown {
    color: #9aa3ad;
    border-color: rgba(154, 163, 173, 0.3);
    background: rgba(154, 163, 173, 0.05);
}
.deal-card-summary {
    font-size: 0.98rem;
    line-height: 1.5;
    color: #d3d7db;
    margin-bottom: 12px;
}
.deal-card-foot {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.85rem;
    color: #9aa3ad;
    flex-wrap: wrap;
    gap: 8px;
}
.deal-card-foot .tipo {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    background: rgba(100, 120, 180, 0.15);
    color: #b0bfd4;
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.deal-card-foot .sources a {
    color: #6aa6ff;
    text-decoration: none;
    margin-left: 4px;
}
.deal-card-foot .sources a:hover { text-decoration: underline; }
.deal-card-foot .sources .sep { color: #4a525e; margin: 0 4px; }
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
    valor = format_value(deal.get("valor_usd"), deal.get("valor_brl"))
    valor_class = "unknown" if valor == "n/d" else ""
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

    html = f"""
    <div class="deal-card">
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
            <span class="tipo">{tipo}</span>
            <span class="sources">📰 {sources_html}</span>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render() -> None:
    st.markdown(CARD_CSS, unsafe_allow_html=True)
    st.title("Feed de Transações")
    st.caption("Deals em ordem cronológica, mais recentes primeiro.")

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
            st.markdown(f"### {format_date_pt(dt) or 'Sem data'}")
            current_date = dt
        _render_card(deal, mentions)
