from __future__ import annotations

import pandas as pd
import streamlit as st

from _filters import render_active_banner, render_sidebar_and_apply
from _lib import format_value, load_deals, render_header


KPI_CSS = """
<style>
.kpi-card {
    border: 1px solid rgba(128, 128, 128, 0.25);
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 14px;
    background: rgba(128, 128, 128, 0.03);
    min-height: 96px;
    transition: border-color 0.15s ease, background 0.15s ease;
}
.kpi-card:hover {
    border-color: rgba(128, 128, 128, 0.5);
    background: rgba(128, 128, 128, 0.06);
}
.kpi-label {
    font-size: 0.82rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-weight: 600;
    opacity: 0.65;
    margin-bottom: 6px;
}
.kpi-value {
    font-size: 1.7rem;
    font-weight: 600;
    line-height: 1.15;
}
.kpi-sub {
    font-size: 0.78rem;
    opacity: 0.6;
    margin-top: 4px;
}
</style>
"""


def _kpi_card(label: str, value: str, sub: str | None = None) -> str:
    sub_html = f"<div class='kpi-sub'>{sub}</div>" if sub else ""
    return (
        f"<div class='kpi-card'>"
        f"<div class='kpi-label'>{label}</div>"
        f"<div class='kpi-value'>{value}</div>"
        f"{sub_html}"
        f"</div>"
    )


def _kpi_row(f: pd.DataFrame) -> None:
    st.markdown(KPI_CSS, unsafe_allow_html=True)

    total_deals = len(f)
    n_br = int((f["regiao"] == "BR").sum())
    n_gl = int((f["regiao"] == "Global").sum())

    with_value = f[f["valor_usd"].notna()]
    total_usd = float(with_value["valor_usd"].sum()) if not with_value.empty else 0.0
    ticket_medio = total_usd / len(with_value) if not with_value.empty else 0.0
    maior = float(with_value["valor_usd"].max()) if not with_value.empty else 0.0
    pct_com_valor = (len(with_value) / total_deals * 100) if total_deals else 0.0

    maior_row = with_value.sort_values("valor_usd", ascending=False).head(1)
    maior_sub = None
    if not maior_row.empty:
        r = maior_row.iloc[0]
        maior_sub = f"{r.get('comprador') or '?'} → {r.get('alvo') or '?'}"

    volume_str = format_value(total_usd, None) if total_usd else "n/d"
    ticket_str = format_value(ticket_medio, None) if ticket_medio else "n/d"
    maior_str = format_value(maior, None) if maior else "n/d"

    c1, c2, c3 = st.columns(3, gap="medium")
    c1.markdown(_kpi_card("Total de deals", str(total_deals)), unsafe_allow_html=True)
    c2.markdown(_kpi_card("Deals Brasil", str(n_br)), unsafe_allow_html=True)
    c3.markdown(_kpi_card("Deals Global", str(n_gl)), unsafe_allow_html=True)

    c4, c5, c6 = st.columns(3, gap="medium")
    c4.markdown(_kpi_card("Volume total", volume_str, f"{pct_com_valor:.0f}% com valor divulgado"), unsafe_allow_html=True)
    c5.markdown(_kpi_card("Ticket médio", ticket_str), unsafe_allow_html=True)
    c6.markdown(_kpi_card("Maior deal", maior_str, maior_sub), unsafe_allow_html=True)


def _volume_por_mes(f: pd.DataFrame) -> None:
    if f.empty or f["data_anuncio"].isna().all():
        st.info("Sem dados de data suficientes para o gráfico temporal.")
        return

    df = f.dropna(subset=["data_anuncio"]).copy()
    df["mes"] = pd.to_datetime(df["data_anuncio"]).dt.to_period("M").dt.to_timestamp()

    vol = (
        df.groupby("mes")["valor_usd"]
        .sum(min_count=1)
        .fillna(0)
        .div(1e9)
        .rename("Volume (US$ bi)")
    )
    cnt = df.groupby("mes").size().rename("Deals")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Volume por mês** _(US$ bi)_")
        st.bar_chart(vol, height=260)
    with c2:
        st.markdown("**Nº de deals por mês**")
        st.bar_chart(cnt, height=260)


def _por_categoria(f: pd.DataFrame, coluna: str, titulo: str, top_n: int = 10) -> None:
    if f.empty or coluna not in f.columns or f[coluna].isna().all():
        return

    st.markdown(f"**{titulo}**")
    c1, c2 = st.columns(2)

    cnt = f[coluna].fillna("(n/d)").value_counts().head(top_n)
    vol = (
        f.groupby(f[coluna].fillna("(n/d)"))["valor_usd"]
        .sum(min_count=1)
        .fillna(0)
        .div(1e9)
        .sort_values(ascending=False)
        .head(top_n)
    )

    with c1:
        st.caption("Por número de deals")
        st.bar_chart(cnt, height=240, horizontal=True)
    with c2:
        st.caption("Por volume (US$ bi)")
        st.bar_chart(vol, height=240, horizontal=True)


def _top_deals(f: pd.DataFrame, n: int = 10) -> None:
    if f.empty:
        return
    top = (
        f.dropna(subset=["valor_usd"])
        .sort_values("valor_usd", ascending=False)
        .head(n)
    )
    if top.empty:
        return

    st.markdown(f"**Top {n} deals por valor**")
    display = top[["data_anuncio", "regiao", "comprador", "alvo", "setor", "valor_usd"]].rename(
        columns={
            "data_anuncio": "Data",
            "regiao": "Região",
            "comprador": "Comprador",
            "alvo": "Alvo",
            "setor": "Setor",
            "valor_usd": "Valor (US$)",
        }
    )
    st.dataframe(
        display,
        hide_index=True,
        width="stretch",
        column_config={
            "Data": st.column_config.DateColumn("Data", format="DD MMM YYYY", width="small"),
            "Região": st.column_config.TextColumn("Região", width="small"),
            "Valor (US$)": st.column_config.NumberColumn(
                "Valor (US$)", format="compact", width="small"
            ),
        },
    )


def render() -> None:
    render_header("Mercado — visão consolidada")

    df = load_deals()
    if df.empty:
        st.warning("Nenhum deal na base ainda. Rode `python pipeline.py` primeiro.")
        return

    ctx = render_sidebar_and_apply(df)
    f = ctx.filtered

    render_active_banner(ctx)

    if f.empty:
        st.info("Nenhum deal bate com os filtros.")
        return

    _kpi_row(f)
    st.divider()
    _volume_por_mes(f)
    st.divider()
    _por_categoria(f, "setor", "Distribuição por setor")
    st.divider()
    _por_categoria(f, "tipo_transacao", "Distribuição por tipo de transação")
    st.divider()
    _top_deals(f)
