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
    /* =============================================
       CENTRO DE COMANDO — Design System
       ============================================= */

    /* === FONTS === */
    .stApp, .stApp * {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }}

    /* Outfit for titles, headings, and numbers */
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

    /* Main content — padding generoso (p-8) */
    .stMainBlockContainer {{
        padding: 2rem 2rem 0.5rem 2rem !important;
    }}

    /* Header transparente */
    .stAppHeader {{
        background: transparent !important;
        backdrop-filter: none !important;
    }}

    /* === SIDEBAR — branco puro, borda sutil === */
    section[data-testid="stSidebar"] {{
        background-color: {c["surface"]} !important;
        border-right: 1px solid #EFEFEF !important;
    }}
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .stMarkdown span {{
        color: {c["text"]} !important;
    }}

    /* Sidebar nav items: rounded-xl */
    section[data-testid="stSidebar"] a {{
        border-radius: 12px !important;
        transition: all 0.2s ease !important;
        margin: 2px 4px !important;
    }}
    section[data-testid="stSidebar"] a:hover {{
        background-color: {c["background"]} !important;
    }}

    /* Sidebar nav: item ativo — fundo grafite escuro, sombra suave */
    section[data-testid="stSidebar"] a[aria-current="page"] {{
        background-color: {c["text"]} !important;
        color: #fff !important;
        border-right: none !important;
        border-radius: 12px !important;
        box-shadow: 0 2px 8px rgba(39,43,48,0.15) !important;
    }}
    section[data-testid="stSidebar"] a[aria-current="page"] span {{
        color: #fff !important;
        font-weight: 600 !important;
    }}

    /* === CARDS / CONTAINERS — brancos, rounded-2xl, sombra hover === */
    [data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] {{
        background-color: {c["surface"]} !important;
        border: 1px solid {c["border"]} !important;
        border-radius: 16px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
        transition: box-shadow 0.2s ease, transform 0.2s ease !important;
    }}
    [data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"]:hover {{
        box-shadow: 0 4px 12px rgba(0,0,0,0.08) !important;
    }}

    /* === METRICS === */
    [data-testid="stMetricValue"] {{
        font-size: 2rem;
        font-weight: 700;
        color: {c["text"]} !important;
    }}
    [data-testid="stMetricLabel"] {{
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        color: {c["text_muted"]} !important;
    }}

    /* === TABS === */
    button[data-baseweb="tab"] {{
        font-size: 0.85rem !important;
        font-weight: 500 !important;
        color: {c["text_secondary"]} !important;
        transition: color 0.2s ease !important;
    }}
    button[data-baseweb="tab"][aria-selected="true"] {{
        color: {c["text"]} !important;
        font-weight: 600 !important;
    }}
    div[data-baseweb="tab-highlight"] {{
        background-color: {c["text"]} !important;
        height: 2px !important;
    }}

    /* === TABLES — headers cinza claro, uppercase, tracking-wider === */
    [data-testid="stDataFrame"] {{
        border-color: {c["border"]} !important;
        border-radius: 12px !important;
        overflow: hidden !important;
    }}
    [data-testid="stDataFrame"] th {{
        background-color: #FAFAFA !important;
        font-size: 0.7rem !important;
        font-weight: 700 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.8px !important;
        color: {c["text_muted"]} !important;
    }}
    [data-testid="stDataFrame"] td {{
        transition: background-color 0.15s ease !important;
    }}

    /* === INPUTS — rounded-xl === */
    input, textarea {{
        background-color: {c["surface"]} !important;
        color: {c["text"]} !important;
        border-color: {c["border"]} !important;
        border-radius: 12px !important;
        transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
    }}
    input:focus, textarea:focus {{
        border-color: {c["primary"]} !important;
        box-shadow: 0 0 0 3px rgba(14,165,233,0.1) !important;
    }}

    /* Selects */
    [data-baseweb="select"] > div {{
        background-color: {c["surface"]} !important;
        color: {c["text"]} !important;
        border-color: {c["border"]} !important;
        border-radius: 12px !important;
    }}

    /* === BUTTONS === */
    button[data-testid="stBaseButton-primary"] {{
        background-color: {c["text"]} !important;
        color: #fff !important;
        border: none !important;
        border-radius: 12px !important;
        font-weight: 600 !important;
        transition: all 0.2s ease !important;
    }}
    button[data-testid="stBaseButton-primary"]:hover {{
        background-color: #1a1d21 !important;
        box-shadow: 0 2px 8px rgba(39,43,48,0.2) !important;
    }}

    button[data-testid="stBaseButton-secondary"] {{
        border-radius: 10px !important;
        transition: all 0.2s ease !important;
    }}

    /* === DIVIDERS === */
    hr {{
        border-color: {c["border"]} !important;
    }}

    /* === EXPANDER === */
    details {{
        border-radius: 12px !important;
    }}
    details summary {{
        color: {c["text"]} !important;
        font-weight: 600 !important;
    }}

    /* === CAPTION === */
    .stCaption, [data-testid="stCaption"] {{
        color: {c["text_muted"]} !important;
    }}

    /* === BADGES / TAGS (utility classes for HTML injection) === */
    .badge {{
        display: inline-block;
        padding: 3px 10px;
        border-radius: 8px;
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }}
    .badge-success {{
        background: #ECFDF5;
        color: #065F46;
    }}
    .badge-warning {{
        background: #FFFBEB;
        color: #92400E;
    }}
    .badge-error {{
        background: #FEF2F2;
        color: #991B1B;
    }}
    .badge-info {{
        background: #EFF6FF;
        color: #1E40AF;
    }}
    .badge-neutral {{
        background: #F3F4F6;
        color: #374151;
    }}

    /* === TRANSITIONS — entrada suave para containers === */
    [data-testid="stVerticalBlock"] > div {{
        animation: fadeInUp 0.3s ease forwards;
    }}
    @keyframes fadeInUp {{
        from {{
            opacity: 0.6;
            transform: translateY(6px);
        }}
        to {{
            opacity: 1;
            transform: translateY(0);
        }}
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
