from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# Permite rodar com `streamlit run ui/app.py` da raiz do projeto.
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
sys.path.insert(0, str(_ROOT))   # Para `from db...` / `from collectors...`
sys.path.insert(0, str(_HERE))   # Para `from _lib` / `from views...`

load_dotenv(override=True)

st.set_page_config(
    page_title="M&A News",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="📈",
)

from views import feed_view, table_view  # noqa: E402

pg = st.navigation(
    [
        st.Page(feed_view.render, title="Feed", icon="📰", url_path="feed", default=True),
        st.Page(table_view.render, title="Tabela", icon="📊", url_path="tabela"),
    ]
)
pg.run()
