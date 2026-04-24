from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_HERE))

load_dotenv(override=False)

# No Streamlit Cloud não há .env; usa st.secrets e promove para env vars
# para manter `db/client.py` agnóstico.
for _key in ("SUPABASE_URL", "SUPABASE_KEY", "APP_PASSWORD"):
    if _key not in os.environ and _key in st.secrets:
        os.environ[_key] = st.secrets[_key]

st.set_page_config(
    page_title="M&A News",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="📈",
)


def _require_auth() -> bool:
    expected = os.environ.get("APP_PASSWORD")
    if not expected:
        # Sem senha configurada — libera (modo local dev)
        return True
    if st.session_state.get("authed"):
        return True

    st.markdown(
        "<div style='max-width:380px;margin:80px auto 0 auto;'>"
        "<h2 style='margin:0 0 4px 0;'>M&A News</h2>"
        "<p style='color:#6a737d;margin:0 0 20px 0;font-size:14px;'>Acesso restrito</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    _, col, _ = st.columns([1, 2, 1])
    with col:
        with st.form("login", clear_on_submit=False):
            pwd = st.text_input("Senha", type="password", label_visibility="collapsed", placeholder="Senha")
            ok = st.form_submit_button("Entrar", width="stretch")
        if ok:
            if pwd == expected:
                st.session_state["authed"] = True
                st.rerun()
            else:
                st.error("Senha incorreta")
    return False


if not _require_auth():
    st.stop()

from views import deal_view, feed_view, mercado_view, table_view  # noqa: E402

_PAGES = {
    "feed": st.Page(feed_view.render, title="Feed", icon="📰", url_path="feed", default=True),
    "table": st.Page(table_view.render, title="Tabela", icon="📊", url_path="tabela"),
    "mercado": st.Page(mercado_view.render, title="Mercado", icon="📈", url_path="mercado"),
    "deal": st.Page(deal_view.render, title="Deal", icon="🔍", url_path="deal"),
}
st.session_state["pages"] = _PAGES

pg = st.navigation(list(_PAGES.values()))
pg.run()
