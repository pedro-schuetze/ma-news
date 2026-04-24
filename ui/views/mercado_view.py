from __future__ import annotations

import pandas as pd
import streamlit as st

from _filters import render_active_banner, render_sidebar_and_apply
from _lib import format_value, load_deals, render_header


def _kpi_row(f: pd.DataFrame) -> None:
    total_deals = len(f)
    with_value = f[f["valor_usd"].notna()]
    total_usd = float(with_value["valor_usd"].sum()) if not with_value.empty else 0.0
    ticket_medio = total_usd / len(with_value) if not with_value.empty else 0.0
    maior = float(with_value["valor_usd"].max()) if not with_value.empty else 0.0
    pct_com_valor = (len(with_value) / total_deals * 100) if total_deals else 0.0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Deals", total_deals)
    c2.metric("Volume total", f"US$ {total_usd / 1e9:.1f}bi" if total_usd else "n/d")
    c3.metric("Ticket médio", format_value(ticket_medio, None) if ticket_medio else "n/d")
    c4.metric("Maior deal", format_value(maior, None) if maior else "n/d")
    c5.metric("% com valor divulgado", f"{pct_com_valor:.0f}%")


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
