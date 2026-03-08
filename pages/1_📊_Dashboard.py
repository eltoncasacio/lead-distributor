"""
Dashboard SaaS Premium: Operacional + Analytics
Layout Final: KPIs (SaaS Style) -> (Fila SaaS | Timeline) -> Analytics Grid
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
from streamlit_sortables import sort_items
from utils.ui import loading_spinner, inject_global_css
from utils.auth import obter_loja_logada
from utils.theme import get_colors, get_plotly_layout_defaults
from utils.queries import (
    get_metricas_hoje,
    get_leads_ontem,
    get_leads_por_dia,
    get_leads_por_hora,
    get_leads_por_origem_comparativo,
    listar_vendedores,
    obter_proximo_vendedor,
    get_atividades_recentes,
    reordenar_vendedores,
    get_metricas_funil,
    get_ultimo_lead_info,
)

# 1. SETUP E TEMA
inject_global_css()
loja = obter_loja_logada()
c = get_colors()
plotly_defaults = get_plotly_layout_defaults()

# CSS Global para consistência visual e FIDELIDADE MÁXIMA DA FILA
st.markdown(
    f"""
    <style>
    .main {{ background-color: #0b0f19; color: #e5e7eb; }}
    .stCard {{ 
        background-color: #111827; 
        border: 1px solid #1f2937; 
        border-radius: 12px; 
    }}
    
    /* FIX PARA FILA HORIZONTAL ESTILIZADA */
    [data-testid="stVerticalBlock"] > div:has(.sortable-container) > div {{
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        align-items: center !important;
    }}
    
    .sortable-container {{
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        overflow-x: auto !important;
        padding: 10px 0px !important;
        gap: 0px !important;
    }}
    .sortable-container::-webkit-scrollbar {{ display: none; }}

    .sortable-item {{
        flex: 0 0 auto !important;
        width: 140px !important; 
        height: 85px !important;
        background: #111827 !important;
        border: 1.5px solid #374151 !important;
        border-radius: 10px !important;
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        justify-content: center !important;
        color: white !important;
        font-size: 20px !important;
        font-weight: 700 !important;
        margin-right: 45px !important; 
        position: relative !important;
        cursor: grab !important;
    }}

    /* Seta Branca Indicativa entre os cards */
    .sortable-item:not(:last-child)::after {{
        content: '→';
        position: absolute;
        right: -38px;
        top: 50%;
        transform: translateY(-50%);
        color: white !important;
        font-size: 24px;
        font-weight: 300;
        pointer-events: none;
    }}

    /* Estilo do Card Ativo (Giu/André conforme print) */
    .sortable-item:first-child {{
        border-color: #f59e0b !important;
        box-shadow: 0 0 12px rgba(245, 158, 11, 0.15) !important;
    }}

    /* Badge "PRÓXIMO LEAD" interno */
    .sortable-item:first-child::before {{
        content: 'PRÓXIMO LEAD';
        position: absolute;
        bottom: 8px;
        background: #f59e0b;
        color: black;
        font-size: 9px;
        font-weight: 800;
        padding: 2px 8px;
        border-radius: 4px;
        letter-spacing: 0.2px;
        white-space: nowrap;
    }}

    .sortable-item:first-child {{
        padding-bottom: 15px !important;
    }}
    </style>
""",
    unsafe_allow_html=True,
)

# 2. DATA FETCHING
with loading_spinner("Sincronizando dados..."):
    metricas = get_metricas_hoje(loja["loja_id"])
    vendedores = listar_vendedores(loja["loja_id"])
    proximo = obter_proximo_vendedor(loja["loja_id"])
    ultimo_lead_info = get_ultimo_lead_info(loja["loja_id"])
    vendedores_ativos = [v for v in vendedores if v["status"] == "ativo"]
    leads_ontem = get_leads_ontem(loja["loja_id"])

# Calcular variação real hoje vs ontem
_hoje = metricas["total_leads"]
if leads_ontem > 0:
    _variacao = round(((_hoje - leads_ontem) / leads_ontem) * 100)
    _sinal = "+" if _variacao > 0 else ""
    _sub_leads = f"{_sinal}{_variacao}% vs ontem"
    _sub_cor = "#10B981" if _variacao >= 0 else "#EF4444"
elif _hoje > 0:
    _sub_leads = f"+{_hoje} vs ontem"
    _sub_cor = "#10B981"
else:
    _sub_leads = ""
    _sub_cor = None

# 3. SEÇÃO 1: KPI CARDS
_SVG_STYLE = f'stroke="{c["primary"]}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none"'
_ICONS = {
    "leads": f'<svg width="12" height="12" viewBox="0 0 24 24" {_SVG_STYLE}><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/></svg>',
    "clock": f'<svg width="12" height="12" viewBox="0 0 24 24" {_SVG_STYLE}><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
    "next": f'<svg width="12" height="12" viewBox="0 0 24 24" {_SVG_STYLE}><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
    "team": f'<svg width="12" height="12" viewBox="0 0 24 24" {_SVG_STYLE}><circle cx="12" cy="12" r="3"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="M2 12h2"/><path d="M20 12h2"/></svg>',
}


def render_kpi_card(icon_key, label, value, subtext="", sub_color=None):
    sub_color = sub_color or c["text_muted"]
    st.markdown(
        f"""
        <div class="stCard" style="padding: 10px 20px; min-height: 135px; display: flex; flex-direction: column; gap: 8px;">
            <div style="width: 24px; height: 24px; background: #1e293b; border-radius: 8px; display: flex; align-items: center; justify-content: center; margin-bottom: 4px;">
                {_ICONS[icon_key]}
            </div>
            <div style="color: {c["text_muted"]}; font-size: 14px;">{label}</div>
            <div style="color: {c["text"] if label != "Próximo Vendedor na Fila" else c["primary"]}; font-size: 20px; font-weight: 700; line-height: 1;">{value}</div>
            <div style="color: {sub_color}; font-size: 12px; font-weight: 500; margin-top: 2px;">{subtext}</div>
        </div>
    """,
        unsafe_allow_html=True,
    )


k_cols = st.columns(4)
with k_cols[0]:
    render_kpi_card(
        "leads", "Leads Hoje", metricas["total_leads"], _sub_leads, _sub_cor
    )
with k_cols[1]:
    h_rel = (
        f"{ultimo_lead_info['vendedor_nome']} recebeu há pouco"
        if ultimo_lead_info
        else ""
    )
    render_kpi_card(
        "clock", "Último Lead Recebido", metricas["ultimo_lead"] or "--", h_rel
    )
with k_cols[2]:
    render_kpi_card(
        "next", "Próximo Vendedor na Fila", proximo["nome"] if proximo else "---"
    )
with k_cols[3]:
    render_kpi_card("team", "Vendedores Ativos", len(vendedores_ativos))

st.markdown("")

# ============================================
# SEÇÃO 2: OPERAÇÕES (Fila SaaS + Timeline)
# ============================================


st.markdown(
    '<div style="color:white; font-size:16px; font-weight:600; margin-top:30px;">Fila de Distribuição</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div style="color:#94a3b8; font-size:12px; margin-bottom:5px;">Arraste para reordenar a fila</div>',
    unsafe_allow_html=True,
)

if vendedores_ativos:
    v_sorted = sorted(vendedores_ativos, key=lambda x: x["criado_em"])
    if proximo:
        idx = next((i for i, v in enumerate(v_sorted) if v["id"] == proximo["id"]), 0)
        v_sorted = v_sorted[idx:] + v_sorted[:idx]

    nomes = [v["nome"] for v in v_sorted]

    nova_ordem = sort_items(
        nomes,
        direction="horizontal",
        key="fila_final_full_v1",
    )

    novos_ids = [next(v["id"] for v in v_sorted if v["nome"] == n) for n in nova_ordem]
    if novos_ids != [v["id"] for v in v_sorted]:
        reordenar_vendedores(loja["loja_id"], novos_ids)
        st.rerun()
else:
    st.info("Nenhum vendedor disponível.")

st.markdown(
    '<div style="font-size:16px; font-weight:600; margin-top:30px; margin-bottom:5px;">Atividades Recentes</div>',
    unsafe_allow_html=True,
)
with st.container(border=False, height=280):
    ativs = get_atividades_recentes(loja["loja_id"], limite=8)
    if ativs:
        timeline_html = '<div style="background: rgba(30, 41, 59, 0.2); border-radius: 8px; padding: 15px;">'
        for i, a in enumerate(ativs):
            icon = "➢"
            line = (
                '<div style="position: absolute; left: 10px; top: 25px; bottom: 0; width: 1.5px; background: #334155;"></div>'
                if i < len(ativs) - 1
                else ""
            )
            timeline_html += f'<div style="display: flex; gap: 12px; position: relative; padding-bottom: 15px;">{line}<div style="z-index: 1; color: #f59e0b; font-size:12px;">{icon}</div><div><div style="font-size: 12px; color: #f1f5f9; font-weight: 500;">{a["descricao"]}</div><div style="font-size: 10px; color: #94a3b8;">{a["criado_em"]}</div></div></div>'
        timeline_html += "</div>"
        st.markdown(timeline_html, unsafe_allow_html=True)

st.markdown("---")

# ============================================
# 5. SEÇÃO DE ANALYTICS (GRID COMPLETO)
# ============================================
st.markdown("### Inteligência de Dados")
c_f1, c_f2, _ = st.columns([1, 1, 3])
d_ini = c_f1.date_input("Início", value=date.today() - timedelta(days=30))
d_fim = c_f2.date_input("Fim", value=date.today())

col_trend, col_funnel = st.columns([1, 1], gap="small")
with col_trend:
    with st.container(border=True):
        leads_dia = get_leads_por_dia(
            loja_id=loja["loja_id"], data_inicio=d_ini, data_fim=d_fim
        )
        if leads_dia:
            df_dia = pd.DataFrame(leads_dia)
            st.markdown(
                f'<div style="font-weight:600;margin-bottom:10px;">Fluxo de Leads (Total: {int(df_dia["total"].sum())})</div>',
                unsafe_allow_html=True,
            )
            fig_t = px.line(
                df_dia, x="data", y="total", line_shape="spline", markers=True
            )
            fig_t.update_traces(line_color=c["primary"])
            fig_t.update_layout(
                **plotly_defaults, height=250, margin=dict(l=0, r=0, t=10, b=0)
            )
            st.plotly_chart(fig_t, use_container_width=True)

with col_funnel:
    with st.container(border=True):
        st.markdown(
            '<div style="font-weight:600;margin-bottom:10px;">Funil de Vendas</div>',
            unsafe_allow_html=True,
        )
        f_data = get_metricas_funil(
            loja_id=loja["loja_id"], data_inicio=d_ini, data_fim=d_fim
        )
        fig_f = go.Figure(
            go.Funnel(
                y=["Leads", "Atendidos", "Vendas"],
                x=[f_data["novo"], f_data["atendido"], f_data["venda_concretizada"]],
                marker=dict(color=[c["primary"], "#2563EB", "#10B981"]),
            )
        )
        fig_f.update_layout(
            **plotly_defaults, height=250, margin=dict(l=40, r=40, t=10, b=10)
        )
        st.plotly_chart(fig_f, use_container_width=True)

col_orig, col_hora = st.columns(2, gap="small")
with col_orig:
    with st.container(border=True):
        st.markdown(
            '<div style="font-size:14px;font-weight:600;margin-bottom:10px;">Leads por Origem</div>',
            unsafe_allow_html=True,
        )
        origens = get_leads_por_origem_comparativo(
            loja_id=loja["loja_id"], data_inicio=d_ini, data_fim=d_fim
        )
        if origens.get("atual"):
            df_o = pd.DataFrame(
                list(origens["atual"].items()), columns=["Origem", "Total"]
            ).sort_values("Total", ascending=True)
            fig_o = px.bar(df_o, y="Origem", x="Total", orientation="h")
            fig_o.update_traces(marker_color=c["primary"])
            fig_o.update_layout(
                **plotly_defaults, height=200, margin=dict(l=0, r=10, t=0, b=0)
            )
            st.plotly_chart(fig_o, use_container_width=True)

with col_hora:
    with st.container(border=True):
        st.markdown(
            '<div style="font-size:14px;font-weight:600;margin-bottom:10px;">Leads por Hora</div>',
            unsafe_allow_html=True,
        )
        horas = get_leads_por_hora(
            loja_id=loja["loja_id"], data_inicio=d_ini, data_fim=d_fim
        )
        if horas:
            df_h = pd.DataFrame(horas)
            fig_h = px.bar(df_h, x="hora_formatada", y="total")
            fig_h.update_traces(marker_color=c["primary"])
            fig_h.update_layout(
                **plotly_defaults, height=200, margin=dict(l=0, r=0, t=0, b=0)
            )
            st.plotly_chart(fig_h, use_container_width=True)

st.caption("Lead Automation System | v2.3 Final")
