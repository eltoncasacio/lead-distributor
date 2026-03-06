"""
Componentes de UI reutilizaveis - visual SaaS profissional.
"""
import streamlit as st
from .auth import logout, obter_loja_logada, require_login


# Estilo CSS para itens do drag-drop (streamlit-sortables custom_style param)
SORTABLE_CUSTOM_STYLE = """
    background-color: #1a1d24;
    border: 1px solid #272b33;
    border-radius: 8px;
    padding: 12px 16px;
    margin: 4px 0;
    color: #d1d5db;
    font-weight: 500;
    font-size: 14px;
    cursor: grab;
    transition: all 0.15s ease;
    list-style: none;
"""

# Estilo horizontal para fila de distribuicao
SORTABLE_HORIZONTAL_STYLE = """
    background-color: #1a1d24;
    border: 1px solid #272b33;
    border-radius: 8px;
    padding: 8px 16px;
    margin: 0 4px;
    color: #d1d5db;
    font-weight: 500;
    font-size: 14px;
    cursor: grab;
    transition: all 0.15s ease;
    list-style: none;
    white-space: nowrap;
"""


def inject_global_css():
    """Injeta CSS global para visual SaaS profissional."""
    st.markdown("""
    <style>
    /* Reduzir padding do topo da pagina */
    .stMainBlockContainer {
        padding-top: 2rem !important;
    }

    /* Metricas — tipografia premium */
    [data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 700;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        opacity: 0.7;
    }

    /* Containers com borda */
    [data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] {
        border-color: #272b33 !important;
        border-radius: 10px !important;
    }

    /* Tabs */
    button[data-baseweb="tab"] {
        font-size: 0.85rem !important;
    }

    /* Dividers */
    hr {
        border-color: #272b33 !important;
    }

    /* Sidebar collapse button fix */
    section[data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarCollapseButton"] {
        display: none !important;
    }
    </style>
    """, unsafe_allow_html=True)


def render_page_header(title: str):
    """Header compacto para paginas internas."""
    require_login()
    loja = obter_loja_logada()
    st.caption(f"{loja['nome']} - **{title}**")


def render_header():
    """
    DEPRECATED: Usar render_page_header() para novo design.
    Mantido para compatibilidade com codigo existente.
    """
    require_login()
    loja = obter_loja_logada()
    st.title(f"{loja['nome']}")
    st.markdown("---")


def show_sidebar_info():
    """Sidebar com informacoes contextuais da conta e botao de logout."""
    loja = obter_loja_logada()
    if not loja:
        return

    with st.sidebar:
        st.divider()
        if st.button("Sair", use_container_width=True, type="secondary"):
            logout()


def render_metric_card(label: str, value, delta=None, help_text=None):
    """Card de metrica estilizado com container e borda."""
    with st.container(border=True):
        st.metric(
            label=label,
            value=value,
            delta=delta,
            help=help_text
        )


def loading_spinner(message: str = "Carregando..."):
    """Context manager para loading states consistentes."""
    return st.spinner(message)


def success_message(message: str):
    """Toast de sucesso padronizado."""
    st.success(message)


def error_message(message: str):
    """Toast de erro padronizado."""
    st.error(message)


def info_message(message: str):
    """Toast informativo padronizado."""
    st.info(message)


def warning_message(message: str):
    """Toast de aviso padronizado."""
    st.warning(message)
