from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd
import streamlit as st


_FILTER_KEYS = (
    "regiao_sel",
    "setor_sel",
    "tipo_sel",
    "val_range",
    "incluir_sem_valor",
    "data_range",
    "busca",
)


def _clear_filters() -> None:
    for k in _FILTER_KEYS:
        if k in st.session_state:
            del st.session_state[k]


@dataclass
class FilterContext:
    filtered: pd.DataFrame
    active_labels: list[str]
    active_count: int


def render_sidebar_and_apply(df: pd.DataFrame) -> FilterContext:
    """Renderiza os filtros na sidebar e aplica ao df. Compartilhado
    entre Tabela e Mercado para que o estado persista entre as páginas.
    """
    hoje = date.today()
    default_inicio = hoje - timedelta(days=30)

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
    active_labels = [name for name, on in active if on]

    return FilterContext(filtered=f, active_labels=active_labels, active_count=len(active_labels))


def render_active_banner(ctx: FilterContext) -> None:
    if ctx.active_count:
        labels = ", ".join(ctx.active_labels)
        plural = "s" if ctx.active_count != 1 else ""
        st.caption(f"🔎 **{ctx.active_count} filtro{plural} ativo{plural}:** {labels}")
