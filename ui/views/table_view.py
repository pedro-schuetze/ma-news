from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from _lib import format_value, load_deals, load_mentions_for


def render() -> None:
    st.title("Tabela de Deals")
    st.caption("Todas as transações coletadas, com filtros para explorar a base.")

    df = load_deals()
    if df.empty:
        st.warning("Nenhum deal na base ainda. Rode `python pipeline.py` primeiro.")
        return

    # === Sidebar: filtros ===
    with st.sidebar:
        st.header("Filtros")

        regioes = ["Todos"] + sorted(df["regiao"].dropna().unique().tolist())
        regiao_sel = st.selectbox("Região", regioes, index=0)

        setores = ["Todos"] + sorted(df["setor"].dropna().unique().tolist())
        setor_sel = st.selectbox("Setor", setores, index=0)

        tipos = ["Todos"] + sorted(df["tipo_transacao"].dropna().unique().tolist())
        tipo_sel = st.selectbox("Tipo de transação", tipos, index=0)

        max_val_usd = float(df["valor_usd"].max() or 1e9)
        cap_mm = max(max_val_usd / 1e6, 1000.0)
        val_min, val_max = st.slider(
            "Valor (US$ milhões)",
            min_value=0.0,
            max_value=float(cap_mm),
            value=(0.0, float(cap_mm)),
            step=50.0,
        )
        incluir_sem_valor = st.checkbox("Incluir deals sem valor divulgado", value=True)

        hoje = date.today()
        default_inicio = hoje - timedelta(days=30)
        data_range = st.date_input("Período (anúncio)", value=(default_inicio, hoje))
        if isinstance(data_range, tuple) and len(data_range) == 2:
            data_ini, data_fim = data_range
        else:
            data_ini, data_fim = default_inicio, hoje

        busca = st.text_input("Busca (alvo ou comprador)", "")

    f = df.copy()
    if regiao_sel != "Todos":
        f = f[f["regiao"] == regiao_sel]
    if setor_sel != "Todos":
        f = f[f["setor"] == setor_sel]
    if tipo_sel != "Todos":
        f = f[f["tipo_transacao"] == tipo_sel]

    val_mask = (f["valor_usd"].fillna(-1) >= val_min * 1e6) & (f["valor_usd"].fillna(-1) <= val_max * 1e6)
    if incluir_sem_valor:
        val_mask = val_mask | f["valor_usd"].isna()
    f = f[val_mask]

    date_mask = f["data_anuncio"].between(data_ini, data_fim) | f["data_anuncio"].isna()
    f = f[date_mask]

    if busca.strip():
        q = busca.strip().lower()
        f = f[
            f["alvo"].fillna("").str.lower().str.contains(q)
            | f["comprador"].fillna("").str.lower().str.contains(q)
        ]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Deals filtrados", len(f))
    col2.metric("Brasil", int((f["regiao"] == "BR").sum()))
    col3.metric("Global", int((f["regiao"] == "Global").sum()))
    total_usd = f["valor_usd"].sum(skipna=True)
    col4.metric("Volume total", f"US$ {total_usd / 1e9:.1f}bi" if total_usd else "n/d")

    st.divider()

    if f.empty:
        st.info("Nenhum deal bate com os filtros.")
        return

    display = f.copy()
    display["valor"] = display.apply(lambda r: format_value(r.get("valor_usd"), r.get("valor_brl")), axis=1)
    cols_show = ["data_anuncio", "regiao", "comprador", "alvo", "setor", "valor", "tipo_transacao", "resumo_uma_frase"]
    display_table = display[cols_show].rename(
        columns={
            "data_anuncio": "Data",
            "regiao": "Região",
            "comprador": "Comprador",
            "alvo": "Alvo",
            "setor": "Setor",
            "valor": "Valor",
            "tipo_transacao": "Tipo",
            "resumo_uma_frase": "Resumo",
        }
    )

    selection = st.dataframe(
        display_table,
        width="stretch",
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        height=450,
    )

    selected_rows = selection.selection.rows if selection.selection else []
    if selected_rows:
        deal_row = f.iloc[selected_rows[0]]
        st.subheader(f"{deal_row['comprador']} → {deal_row['alvo']}")
        st.write(f"**{deal_row.get('resumo_uma_frase', '')}**")

        c1, c2, c3 = st.columns(3)
        c1.markdown(f"**Setor:** {deal_row.get('setor', 'n/d')}")
        c1.markdown(f"**Subsetor:** {deal_row.get('subsetor', 'n/d')}")
        c2.markdown(f"**Valor:** {format_value(deal_row.get('valor_usd'), deal_row.get('valor_brl'))}")
        c2.markdown(f"**Tipo:** {deal_row.get('tipo_transacao', 'n/d')}")
        c3.markdown(f"**Região:** {deal_row.get('regiao', 'n/d')}")
        c3.markdown(f"**País:** {deal_row.get('pais', 'n/d')}")

        mentions = load_mentions_for([int(deal_row["id"])])
        st.markdown(f"**Menções ({len(mentions)}):**")
        for _, m in mentions.iterrows():
            st.markdown(f"- [{m['titulo']}]({m['url']}) — *{m['fonte']}*")
