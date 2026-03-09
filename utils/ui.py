"""
Componentes de UI reutilizaveis - visual SaaS profissional.
"""

import streamlit as st
from .auth import logout, obter_loja_logada, require_login
from .theme import get_colors, inject_theme_css


def get_sortable_style(horizontal: bool = False) -> str:
    c = get_colors()
    base = f"""
        background-color: {c["surface"]};
        border: 1px solid {c["border"]};
        border-radius: 8px;
        padding: {"8px 16px" if horizontal else "12px 16px"};
        margin: {"0 4px" if horizontal else "4px 0"};
        color: {c["text"]};
        font-weight: 500;
        font-size: 14px;
        cursor: grab;
        transition: all 0.15s ease;
        list-style: none;
    """
    if horizontal:
        base += "white-space: nowrap;"
    return base


def inject_global_css():
    inject_theme_css()


def render_page_header(title: str):
    require_login()
    loja = obter_loja_logada()
    st.caption(f"{loja['nome']} - **{title}**")


def render_header():
    """DEPRECATED: Usar render_page_header()."""
    require_login()
    loja = obter_loja_logada()
    st.title(f"{loja['nome']}")
    st.markdown("---")


def show_sidebar_info():
    loja = obter_loja_logada()
    if not loja:
        return

    with st.sidebar:
        # Botao Sair fixo no fundo da sidebar
        st.markdown(
            """
            <style>
            /* Empurrar conteudo pos-nav para o fundo da sidebar */
            section[data-testid="stSidebar"] [data-testid="stSidebarContent"] > div:last-child {
                position: absolute;
                bottom: 0px;
                left: 16px;
                right: 16px;
            }
            /* Botao Sair sem borda */
            section[data-testid="stSidebar"] [data-testid="stSidebarContent"] > div:last-child button {
                border: none !important;
                outline: none !important;
                box-shadow: none !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        if st.button(
            ":material/logout:", use_container_width=True, type="secondary", help="Sair"
        ):
            logout()


def render_metric_card(label: str, value, delta=None, help_text=None):
    with st.container(border=True):
        st.metric(label=label, value=value, delta=delta, help=help_text)


def loading_spinner(message: str = "Carregando..."):
    return st.spinner(message)


def success_message(message: str):
    st.success(message)


def error_message(message: str):
    st.error(message)


def info_message(message: str):
    st.info(message)


def warning_message(message: str):
    st.warning(message)
