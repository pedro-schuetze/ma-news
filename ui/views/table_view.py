from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from _lib import format_value, load_deals, load_mentions_for, render_header


_FILTER_KEYS = ("regiao_sel", "setor_sel", "tipo_sel", "val_range", "incluir_sem_valor", "data_range", "busca")


def _clear_filters() -> None:
    for k in _FILTER_KEYS:
        if k in st.session_state:
            del st.session_state[k]


def render() -> None:
    render_header("Tabela completa — filtros avançados")

    df = load_deals()
    if df.empty:
        st.warning("Nenhum deal na base ainda. Rode `python pipeline.py` primeiro.")
        return

    hoje = date.today()
    default_inicio = hoje - timedelta(days=30)

    # === Sidebar: filtros ===
    with st.sidebar:
        st.header("Filtros")

        regioes = ["Todos"] + sorted(df["regiao"].dropna().unique().tolist())
        regiao_sel = st.selectbox("Região", regioes, key="regiao_sel")

        setores = ["Todos"] + sorted(df["setor"].dropna().unique().tolist())
        setor_sel = st.selectbox("Setor", setores, key="setor_sel")

        tipos = ["Todos"] + sorted(df["tipo_transacao"].dropna().unique().tolist())
        tipo_sel = st.selectbox("Tipo de transação", tipos, key="tipo_sel")

        max_val_usd = float(df["valor_usd"].max() or 1e9)
        cap_mm = max(max_val_usd / 1e6, 1000.0)
        val_min, val_max = st.slider(
            "Valor (US$ milhões)",
            min_value=0.0,
            max_value=float(cap_mm),
            value=(0.0, float(cap_mm)),
            step=50.0,
            key="val_range",
        )
        incluir_sem_valor = st.checkbox(
            "Incluir deals sem valor divulgado", value=True, key="incluir_sem_valor"
        )

        data_range = st.date_input(
            "Período (anúncio)", value=(default_inicio, hoje), key="data_range"
        )
        if isinstance(data_range, tuple) and len(data_range) == 2:
            data_ini, data_fim = data_range
        else:
            data_ini, data_fim = default_inicio, hoje

        busca = st.text_input("Busca (alvo ou comprador)", key="busca")

        st.button("🧹 Limpar filtros", on_click=_clear_filters, width="stretch")

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

    active = [
        ("Região", regiao_sel != "Todos"),
        ("Setor", setor_sel != "Todos"),
        ("Tipo", tipo_sel != "Todos"),
        ("Valor", (val_min, val_max) != (0.0, float(cap_mm))),
        ("Sem valor", not incluir_sem_valor),
        ("Período", (data_ini, data_fim) != (default_inicio, hoje)),
        ("Busca", bool(busca.strip())),
    ]
    n_active = sum(1 for _, on in active if on)
    if n_active:
        labels = ", ".join(name for name, on in active if on)
        st.caption(f"🔎 **{n_active} filtro{'s' if n_active != 1 else ''} ativo{'s' if n_active != 1 else ''}:** {labels}")

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

    cols_show = [
        "data_anuncio", "regiao", "comprador", "alvo", "setor",
        "valor_usd", "tipo_transacao", "resumo_uma_frase",
    ]
    display_table = f[cols_show].rename(
        columns={
            "data_anuncio": "Data",
            "regiao": "Região",
            "comprador": "Comprador",
            "alvo": "Alvo",
            "setor": "Setor",
            "valor_usd": "Valor (US$)",
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
        column_config={
            "Data": st.column_config.DateColumn("Data", format="DD MMM YYYY", width="small"),
            "Região": st.column_config.TextColumn("Região", width="small"),
            "Comprador": st.column_config.TextColumn("Comprador", width="medium"),
            "Alvo": st.column_config.TextColumn("Alvo", width="medium"),
            "Setor": st.column_config.TextColumn("Setor", width="small"),
            "Valor (US$)": st.column_config.NumberColumn(
                "Valor (US$)", format="compact", width="small"
            ),
            "Tipo": st.column_config.TextColumn("Tipo", width="small"),
            "Resumo": st.column_config.TextColumn("Resumo", width="large"),
        },
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
