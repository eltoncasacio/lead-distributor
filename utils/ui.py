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
        # Spacer flexível que empurra o botão logout para baixo
        st.markdown('<div id="sidebar-flex-spacer"></div>', unsafe_allow_html=True)

        # Wrapper para aplicar estilos ao botão logout
        st.markdown('<div id="sidebar-logout-container">', unsafe_allow_html=True)

        # Botão de logout
        if st.button(
            ":material/logout:",
            use_container_width=True,
            type="secondary",
            help="Sair",
            key="logout_button"
        ):
            logout()

        st.markdown('</div>', unsafe_allow_html=True)


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
