"""
Sistema de temas (dark/light) com paleta amber.
Single source of truth para todas as cores do app.
"""

import streamlit as st

# ============================================
# PALETAS
# ============================================

DARK_PALETTE = {
    "primary": "#f59e0b",
    "primary_dark": "#d97706",
    "primary_light": "#fbbf24",
    "background": "#0b0f19",
    "surface": "#111827",
    "surface_hover": "#1a2332",
    "border": "#1f2937",
    "border_light": "#374151",
    "text": "#e5e7eb",
    "text_muted": "#9ca3af",
    "text_subtle": "#6b7280",
    "success": "#10b981",
    "warning": "#f59e0b",
    "error": "#ef4444",
    "info": "#3b82f6",
    "scrollbar_track": "#1f2937",
    "scrollbar_thumb": "#475569",
    "scrollbar_thumb_hover": "#64748b",
}

LIGHT_PALETTE = {
    "primary": "#f59e0b",
    "primary_dark": "#d97706",
    "primary_light": "#fbbf24",
    "background": "#f8fafc",
    "surface": "#ffffff",
    "surface_hover": "#f1f5f9",
    "border": "#e2e8f0",
    "border_light": "#cbd5e1",
    "text": "#1e293b",
    "text_muted": "#64748b",
    "text_subtle": "#94a3b8",
    "success": "#10b981",
    "warning": "#f59e0b",
    "error": "#ef4444",
    "info": "#3b82f6",
    "scrollbar_track": "#e2e8f0",
    "scrollbar_thumb": "#94a3b8",
    "scrollbar_thumb_hover": "#64748b",
}


# ============================================
# GETTERS
# ============================================


def get_theme() -> str:
    return st.session_state.get("theme", "dark")


def set_theme(theme: str):
    st.session_state["theme"] = theme


def get_colors() -> dict:
    return DARK_PALETTE if get_theme() == "dark" else LIGHT_PALETTE


def get_plotly_layout_defaults() -> dict:
    c = get_colors()
    return dict(
        template="plotly_dark" if get_theme() == "dark" else "plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=c["text"]),
    )


# ============================================
# CSS INJECTION
# ============================================


def inject_theme_css():
    c = get_colors()
    st.markdown(
        f"""
    <style>
    /* === BASE === */
    .stApp {{
        background-color: {c["background"]} !important;
        color: {c["text"]} !important;
    }}

    /* Sidebar */
    section[data-testid="stSidebar"] {{
        background-color: {c["surface"]} !important;
        border-right: 1px solid {c["border"]} !important;
    }}
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .stMarkdown span {{
        color: {c["text"]} !important;
    }}

    /* Sidebar nav: item ativo = amber + barra direita */
    section[data-testid="stSidebar"] a[aria-current="page"] {{
        color: {c["primary"]} !important;
        border-right: 3px solid {c["primary"]} !important;
        border-radius: 0 !important;
    }}
    section[data-testid="stSidebar"] a[aria-current="page"] span {{
        color: {c["primary"]} !important;
    }}

    /* Containers com borda */
    [data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] {{
        background-color: {c["surface"]} !important;
        border-color: {c["border"]} !important;
        border-radius: 12px !important;
    }}

    /* Metrics */
    [data-testid="stMetricValue"] {{
        font-size: 2rem;
        font-weight: 700;
        color: {c["text"]} !important;
    }}
    [data-testid="stMetricLabel"] {{
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        color: {c["text_muted"]} !important;
    }}

    /* Tabs */
    button[data-baseweb="tab"] {{
        font-size: 0.85rem !important;
        color: {c["text_muted"]} !important;
    }}
    button[data-baseweb="tab"][aria-selected="true"] {{
        color: {c["primary"]} !important;
    }}
    div[data-baseweb="tab-highlight"] {{
        background-color: {c["primary"]} !important;
    }}

    /* Dividers */
    hr {{
        border-color: {c["border"]} !important;
    }}

    /* Buttons primary */
    button[data-testid="stBaseButton-primary"] {{
        background-color: {c["primary"]} !important;
        color: #000 !important;
        border: none !important;
    }}
    button[data-testid="stBaseButton-primary"]:hover {{
        background-color: {c["primary_dark"]} !important;
    }}

    /* Inputs */
    input, textarea, [data-baseweb="select"] > div {{
        background-color: {c["surface"]} !important;
        color: {c["text"]} !important;
        border-color: {c["border"]} !important;
    }}

    /* Data editor / dataframe */
    [data-testid="stDataFrame"] {{
        border-color: {c["border"]} !important;
    }}

    /* Expander */
    details summary {{
        color: {c["text"]} !important;
    }}

    /* Caption */
    .stCaption, [data-testid="stCaption"] {{
        color: {c["text_muted"]} !important;
    }}

    /* Reduce top padding — alinhar conteudo com menu lateral */
    .stMainBlockContainer {{
        padding-top: 0.5rem !important;
    }}
    .stAppHeader {{
        display: none !important;
    }}

    /* Sidebar collapse button fix */
    section[data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarCollapseButton"] {{
        display: none !important;
    }}
    </style>
    """,
        unsafe_allow_html=True,
    )


# ============================================
# THEME TOGGLE
# ============================================


def render_theme_toggle():
    current = get_theme()
    icon = ":material/light_mode:" if current == "dark" else ":material/dark_mode:"
    label = "Modo Claro" if current == "dark" else "Modo Escuro"
    if st.button(icon, use_container_width=True, help=label, key="theme_toggle"):
        set_theme("light" if current == "dark" else "dark")
        st.rerun()
