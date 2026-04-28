from __future__ import annotations

import streamlit as st

from _deal_detail import render_deal_detail
from _filters import render_active_banner, render_sidebar_and_apply
from _lib import format_value, load_deals, load_mentions_for, open_deal, render_header


def render() -> None:
    render_header("Tabela completa — filtros avançados")

    # Drill-down: se um deal está selecionado, mostra os detalhes em vez da tabela.
    selected = st.session_state.get("selected_deal_id")
    if selected is not None:
        render_deal_detail(int(selected), back_label="← Voltar à tabela")
        return

    df = load_deals()
    if df.empty:
        st.warning("Nenhum deal na base ainda. Rode `python pipeline.py` primeiro.")
        return

    ctx = render_sidebar_and_apply(df)
    f = ctx.filtered

    render_active_banner(ctx)

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
        head_l, head_r = st.columns([5, 1])
        head_l.subheader(f"{deal_row['comprador']} → {deal_row['alvo']}")
        head_r.button(
            "🔍 Abrir deal",
            key=f"open_tbl_{int(deal_row['id'])}",
            on_click=open_deal,
            args=(int(deal_row["id"]),),
            width="stretch",
        )
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
