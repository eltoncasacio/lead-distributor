"""
Sistema de tema ZapLead — paleta Sky Blue + Orange CTA (light mode).
Single source of truth para todas as cores do app.
"""

import streamlit as st

# ============================================
# PALETA ZAPLEAD
# ============================================

PALETTE = {
    # Primary (Sky Blue)
    "primary": "#0EA5E9",
    "primary_dark": "#0284C7",
    "primary_light": "#38BDF8",
    "primary_bg": "#EFF8FF",

    # CTA / Accent (Orange)
    "accent": "#F97316",
    "accent_dark": "#EA580C",
    "accent_light": "#FED7AA",

    # Backgrounds
    "background": "#F8F9FA",
    "surface": "#FFFFFF",
    "surface_hover": "#F1F5F9",
    "surface_alt": "#F0F9FF",

    # Text
    "text": "#272B30",
    "text_secondary": "#5F6B7A",
    "text_muted": "#94A3B8",
    "text_subtle": "#94A3B8",

    # Borders
    "border": "#E2E8F0",
    "border_light": "#F1F5F9",

    # Semantic
    "success": "#10B981",
    "warning": "#F59E0B",
    "error": "#EF4444",
    "info": "#0EA5E9",

    # Scrollbar
    "scrollbar_track": "#E2E8F0",
    "scrollbar_thumb": "#94A3B8",
    "scrollbar_thumb_hover": "#64748B",
}

# Aliases for backward compatibility
LIGHT_PALETTE = PALETTE
DARK_PALETTE = PALETTE


# ============================================
# GETTERS
# ============================================


def get_theme() -> str:
    return "light"


def set_theme(theme: str):
    st.session_state["theme"] = "light"


def get_colors() -> dict:
    return PALETTE


def get_plotly_layout_defaults() -> dict:
    c = get_colors()
    return dict(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=c["text"], family="Outfit, Inter, sans-serif"),
    )


# ============================================
# CSS INJECTION
# ============================================


def inject_theme_css():
    c = get_colors()
    # Google Fonts: Inter (body) + Outfit (titles/numbers)
    st.markdown(
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@500;600;700;800&display=swap" rel="stylesheet">',
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
    <style>
    /* === FONTS === */
    .stApp, .stApp * {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }}

    /* Outfit for titles and numbers */
    h1, h2, h3, h4, h5, h6,
    [data-testid="stMetricValue"],
    .stCard .value,
    .kpi-value {{
        font-family: 'Outfit', 'Inter', sans-serif !important;
    }}

    /* === BASE === */
    .stApp {{
        background-color: {c["background"]} !important;
        color: {c["text"]} !important;
    }}

    /* Main content padding */
    .stMainBlockContainer {{
        padding: 2rem 2rem 0.5rem 2rem !important;
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

    /* Sidebar nav: item ativo */
    section[data-testid="stSidebar"] a[aria-current="page"] {{
        color: {c["primary"]} !important;
        border-right: 3px solid {c["primary"]} !important;
        border-radius: 0 !important;
    }}
    section[data-testid="stSidebar"] a[aria-current="page"] span {{
        color: {c["primary"]} !important;
    }}

    /* Containers com borda — cards brancos sobre fundo cinza */
    [data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] {{
        background-color: {c["surface"]} !important;
        border-color: {c["border"]} !important;
        border-radius: 12px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
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
        color: {c["text_secondary"]} !important;
    }}

    /* Tabs */
    button[data-baseweb="tab"] {{
        font-size: 0.85rem !important;
        color: {c["text_secondary"]} !important;
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
        color: #fff !important;
        border: none !important;
        border-radius: 8px !important;
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
        color: {c["text_secondary"]} !important;
    }}

    /* Header transparente */
    .stAppHeader {{
        background: transparent !important;
        backdrop-filter: none !important;
    }}
    </style>
    """,
        unsafe_allow_html=True,
    )


# ============================================
# THEME TOGGLE (no-op, light-only)
# ============================================


def render_theme_toggle():
    pass
