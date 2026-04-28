"""Drill-down de um deal — usado dentro do Feed e da Tabela.

Não é uma página separada na navegação; é um modo da seção atual,
controlado por st.session_state["selected_deal_id"]. Assim a sessão
(auth, filtros) é totalmente preservada.
"""
from __future__ import annotations

from datetime import date, datetime

import streamlit as st

from _lib import (
    close_deal,
    fetch_deal,
    fetch_mentions_full,
    flag_for,
    format_date_pt,
    format_value,
    update_deal,
)


DEAL_CSS = """
<style>
.deal-hero {
    border: 1px solid rgba(128, 128, 128, 0.25);
    border-radius: 14px;
    padding: 24px 28px;
    background: rgba(128, 128, 128, 0.03);
    margin-bottom: 20px;
}
.deal-hero .meta {
    font-size: 0.88rem;
    opacity: 0.7;
    margin-bottom: 8px;
}
.deal-hero .flag { font-size: 1.35rem; margin-right: 8px; vertical-align: middle; }
.deal-hero h2 {
    font-size: 1.8rem;
    font-weight: 700;
    margin: 4px 0 8px 0;
    line-height: 1.25;
}
.deal-hero .arrow { opacity: 0.5; margin: 0 12px; font-weight: 400; }
.deal-hero .value-pill {
    display: inline-block;
    font-size: 1.05rem;
    font-weight: 600;
    color: #047857;
    padding: 3px 12px;
    border: 1px solid rgba(4, 120, 87, 0.35);
    border-radius: 6px;
    background: rgba(16, 185, 129, 0.1);
    margin-right: 10px;
}
.deal-hero .tipo-pill {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 6px;
    background: rgba(100, 120, 180, 0.18);
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-weight: 600;
}
.deal-hero .summary {
    font-size: 1rem;
    line-height: 1.55;
    opacity: 0.88;
    margin-top: 14px;
}
.deal-fact {
    border: 1px solid rgba(128, 128, 128, 0.2);
    border-radius: 10px;
    padding: 12px 16px;
    margin-bottom: 10px;
    background: rgba(128, 128, 128, 0.02);
}
.deal-fact .label {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    opacity: 0.6;
    font-weight: 600;
}
.deal-fact .value { font-size: 1rem; margin-top: 3px; }
.mention-box {
    border: 1px solid rgba(128, 128, 128, 0.22);
    border-radius: 10px;
    padding: 14px 18px;
    margin-bottom: 12px;
    background: rgba(128, 128, 128, 0.02);
}
.mention-box .head {
    font-size: 0.82rem;
    opacity: 0.7;
    margin-bottom: 4px;
}
.mention-box .title { font-size: 1rem; font-weight: 500; margin-bottom: 6px; }
.mention-box .title a { color: inherit; text-decoration: none; border-bottom: 1px solid rgba(128,128,128,0.3); }
.mention-box .title a:hover { border-bottom-color: currentColor; }
.mention-box .raw {
    font-size: 0.88rem;
    line-height: 1.5;
    opacity: 0.8;
    white-space: pre-wrap;
    margin-top: 6px;
    padding-top: 8px;
    border-top: 1px dashed rgba(128, 128, 128, 0.2);
}
</style>
"""


def _render_hero(deal: dict) -> None:
    flag = flag_for(deal.get("pais"), deal.get("regiao"))
    setor = deal.get("setor") or "—"
    subsetor = deal.get("subsetor")
    setor_line = setor + (f" · {subsetor}" if subsetor else "")
    data_str = format_date_pt(deal.get("data_anuncio")) or "Sem data"
    comprador = deal.get("comprador") or "?"
    alvo = deal.get("alvo") or "?"
    valor = format_value(deal.get("valor_usd"), deal.get("valor_brl"))
    tipo = (deal.get("tipo_transacao") or "").upper()
    resumo = deal.get("resumo_uma_frase") or ""

    value_html = f'<span class="value-pill">{valor}</span>' if valor != "n/d" else ""
    tipo_html = f'<span class="tipo-pill">{tipo}</span>' if tipo else ""

    st.markdown(
        f"""
        <div class="deal-hero">
            <div class="meta"><span class="flag">{flag}</span>{setor_line} · {data_str}</div>
            <h2><span>{comprador}</span><span class="arrow">→</span><span>{alvo}</span></h2>
            <div>{value_html}{tipo_html}</div>
            <div class="summary">{resumo}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_facts(deal: dict) -> None:
    def fact(label: str, value) -> str:
        display = value if (value is not None and value != "") else "n/d"
        return f"<div class='deal-fact'><div class='label'>{label}</div><div class='value'>{display}</div></div>"

    valor_usd = deal.get("valor_usd")
    valor_brl = deal.get("valor_brl")
    valor_usd_str = format_value(valor_usd, None) if valor_usd is not None else "n/d"
    valor_brl_str = format_value(None, valor_brl) if valor_brl is not None else "n/d"

    created_at = deal.get("created_at")
    if created_at:
        try:
            created_at = datetime.fromisoformat(str(created_at).replace("Z", "+00:00")).strftime("%d/%m/%Y %H:%M")
        except Exception:
            pass

    rows = [
        ("Status", deal.get("status")),
        ("Região", deal.get("regiao")),
        ("País", deal.get("pais")),
        ("Setor", deal.get("setor")),
        ("Subsetor", deal.get("subsetor")),
        ("Tipo de transação", deal.get("tipo_transacao")),
        ("Valor (USD)", valor_usd_str),
        ("Valor (BRL)", valor_brl_str),
        ("Data do anúncio", format_date_pt(deal.get("data_anuncio"))),
        ("Criado em", created_at),
        ("ID do deal", deal.get("id")),
    ]

    c1, c2, c3 = st.columns(3)
    for i, (label, value) in enumerate(rows):
        [c1, c2, c3][i % 3].markdown(fact(label, value), unsafe_allow_html=True)


def _render_edit_form(deal: dict) -> None:
    with st.form("edit_deal_form"):
        st.caption("Edite os campos e clique em Salvar. Alvo/comprador são re-normalizados automaticamente.")
        c1, c2 = st.columns(2)
        with c1:
            comprador = st.text_input("Comprador", value=deal.get("comprador") or "")
            alvo = st.text_input("Alvo", value=deal.get("alvo") or "")
            regiao = st.selectbox(
                "Região",
                ["BR", "Global"],
                index=0 if deal.get("regiao") == "BR" else 1,
            )
            pais = st.text_input("País", value=deal.get("pais") or "")
            setor = st.text_input("Setor", value=deal.get("setor") or "")
            subsetor = st.text_input("Subsetor", value=deal.get("subsetor") or "")
        with c2:
            valor_usd_raw = deal.get("valor_usd")
            valor_usd = st.number_input(
                "Valor (USD)",
                value=float(valor_usd_raw) if valor_usd_raw is not None else 0.0,
                step=1_000_000.0,
                format="%f",
            )
            valor_brl_raw = deal.get("valor_brl")
            valor_brl = st.number_input(
                "Valor (BRL)",
                value=float(valor_brl_raw) if valor_brl_raw is not None else 0.0,
                step=1_000_000.0,
                format="%f",
            )
            tipos = ["aquisição", "fusão", "joint venture", "venda de ativo", "IPO", "follow-on", "investimento minoritário", "outro"]
            tipo_atual = deal.get("tipo_transacao") or ""
            tipo = st.selectbox(
                "Tipo de transação",
                [""] + tipos,
                index=(tipos.index(tipo_atual) + 1) if tipo_atual in tipos else 0,
            )
            status = st.selectbox(
                "Status",
                ["", "anunciada", "concluída"],
                index={"anunciada": 1, "concluída": 2}.get(deal.get("status") or "", 0),
            )
            data_raw = deal.get("data_anuncio")
            if isinstance(data_raw, str):
                try:
                    data_raw = datetime.fromisoformat(data_raw).date()
                except ValueError:
                    data_raw = None
            data_anuncio = st.date_input(
                "Data do anúncio",
                value=data_raw if data_raw else date.today(),
            )

        resumo = st.text_area(
            "Resumo (uma frase)",
            value=deal.get("resumo_uma_frase") or "",
            height=80,
        )

        c_save, c_cancel = st.columns([1, 5])
        save = c_save.form_submit_button("💾 Salvar", type="primary")
        cancel = c_cancel.form_submit_button("Cancelar")

    if save:
        payload = {
            "comprador": comprador or None,
            "alvo": alvo or None,
            "regiao": regiao,
            "pais": pais or None,
            "setor": setor or None,
            "subsetor": subsetor or None,
            "valor_usd": valor_usd if valor_usd > 0 else None,
            "valor_brl": valor_brl if valor_brl > 0 else None,
            "tipo_transacao": tipo or None,
            "status": status or None,
            "data_anuncio": data_anuncio.isoformat() if data_anuncio else None,
            "resumo_uma_frase": resumo or None,
        }
        try:
            update_deal(int(deal["id"]), payload)
            st.success("Deal atualizado.")
            st.session_state["edit_mode"] = False
            st.rerun()
        except Exception as exc:
            st.error(f"Falha ao salvar: {exc}")

    if cancel:
        st.session_state["edit_mode"] = False
        st.rerun()


def _render_mentions(deal_id: int) -> None:
    mentions = fetch_mentions_full(deal_id)
    if not mentions:
        st.info("Nenhuma menção associada a este deal.")
        return

    st.markdown(f"### Menções ({len(mentions)})")
    for m in mentions:
        data = format_date_pt(m.get("data_publicacao")) or "s/ data"
        fonte = m.get("fonte") or ""
        titulo = m.get("titulo") or "(sem título)"
        url = m.get("url") or "#"
        texto = (m.get("texto_bruto") or "").strip()

        raw_html = ""
        if texto:
            safe = texto.replace("<", "&lt;").replace(">", "&gt;")
            raw_html = f"<div class='raw'>{safe}</div>"

        st.markdown(
            f"""
            <div class="mention-box">
                <div class="head">{fonte} · {data}</div>
                <div class="title"><a href="{url}" target="_blank" rel="noopener">{titulo}</a></div>
                {raw_html}
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_deal_detail(deal_id: int, back_label: str = "← Voltar") -> None:
    """Renderiza o drill-down completo de um deal dentro da seção atual.
    `back_label` é exibido no botão que limpa o selected_deal_id.
    """
    st.markdown(DEAL_CSS, unsafe_allow_html=True)

    top_l, top_r = st.columns([1, 5])
    top_l.button(back_label, key=f"back_{deal_id}", on_click=close_deal, width="stretch")

    deal = fetch_deal(deal_id)
    if not deal:
        st.error(f"Deal #{deal_id} não encontrado.")
        return

    edit_mode = st.session_state.get("edit_mode", False)
    if not edit_mode:
        with top_r:
            _, right = st.columns([5, 1])
            if right.button("✏️ Editar", width="stretch", key=f"edit_{deal_id}"):
                st.session_state["edit_mode"] = True
                st.rerun()

    if edit_mode:
        _render_edit_form(deal)
        return

    _render_hero(deal)

    tab1, tab2 = st.tabs(["Detalhes", "Menções e texto bruto"])
    with tab1:
        _render_facts(deal)
    with tab2:
        _render_mentions(deal_id)
