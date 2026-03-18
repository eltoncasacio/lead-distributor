"""
Dashboard SaaS Premium: Operacional + Analytics
Layout Final: KPIs (SaaS Style) -> (Fila SaaS | Timeline) -> Analytics Grid
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime, timedelta
import zoneinfo
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

_TZ_SP = zoneinfo.ZoneInfo("America/Sao_Paulo")


def _tempo_relativo(iso_str: str) -> str:
    """Converte timestamp ISO para texto relativo em pt-BR (timezone SP)."""
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00")).astimezone(_TZ_SP)
    agora = datetime.now(_TZ_SP)
    delta = agora - dt
    segundos = int(delta.total_seconds())
    if segundos < 60:
        return "agora"
    minutos = segundos // 60
    if minutos < 60:
        return f"há {minutos} min"
    horas = minutos // 60
    if horas < 24:
        return f"há {horas} hora" if horas == 1 else f"há {horas} horas"
    dias = horas // 24
    if dias == 1:
        return "ontem"
    return f"há {dias} dias"


def _formatar_data_atividade(iso_str: str) -> str:
    """Formata timestamp ISO para exibição legível em pt-BR (ex: 'Hoje, 13:11' ou '07/03, 09:45')."""
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00")).astimezone(_TZ_SP)
    agora = datetime.now(_TZ_SP)
    if dt.date() == agora.date():
        return f"Hoje, {dt.strftime('%H:%M')}"
    if dt.date() == (agora - timedelta(days=1)).date():
        return f"Ontem, {dt.strftime('%H:%M')}"
    return f"{dt.strftime('%d/%m')}, {dt.strftime('%H:%M')}"


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
    
    /* Fila horizontal — forcar em todos os niveis */
    [data-testid="stVerticalBlock"] > div:has(.sortable-component) > div,
    .sortable-component,
    .sortable-component > div,
    .sortable-component.vertical,
    .sortable-container,
    .sortable-container-body {{
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        align-items: center !important;
    }}

    .sortable-container-body {{
        background: transparent !important;
        min-height: auto !important;
        padding: 15px 5px !important;
    }}

    /* Esconder hint de acessibilidade do sortables */
    div[role="status"][aria-live] {{
        display: none !important;
    }}

    /* Esconder mensagem de acessibilidade do drag */
    [data-rbd-live-announcer]{{
        display:none !important;
    }}

    [aria-live="assertive"]{{
        display:none !important;
    }}

    div[role="status"]{{
        display:none !important;
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
    if ultimo_lead_info:
        _tempo = _tempo_relativo(ultimo_lead_info["recebido_em"])
        h_rel = f"{ultimo_lead_info['vendedor_nome']} recebeu {_tempo}"
    else:
        h_rel = ""
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
    '<div style="color:white; font-size:16px; font-weight:600; margin-top:50px;">Fila de Distribuição <span style="color:#94a3b8; font-size:12px;"> (Arraste para reordenar a fila)</span></div>',
    unsafe_allow_html=True,
)

if vendedores_ativos:
    v_sorted = sorted(vendedores_ativos, key=lambda x: x["ordem_fila"])
    if proximo:
        idx = next((i for i, v in enumerate(v_sorted) if v["id"] == proximo["id"]), 0)
        v_sorted = v_sorted[idx:] + v_sorted[:idx]

    nomes = [v["nome"] for v in v_sorted]

    _fila_css = f"""
        /* Forcar layout horizontal em todos os niveis */
        .sortable-component,
        .sortable-component > div,
        .sortable-component.vertical {{
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
            gap: 0px !important;
            position: relative !important;
            align-items: center !important;
            width: 100% !important;
        }}
        .sortable-container::-webkit-scrollbar {{ display: none; }}

        .sortable-container-body {{
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            align-items: center !important;
            background: 1e293b !important;
            position: relative !important;
            padding: 15px 10px !important;
            min-height: auto !important;
            border-radius: 12px;
        }}

        /* Linha do tempo de fundo */
        .sortable-container-body::before {{
            content: '';
            position: absolute;
            top: 50%;
            left: 70px;
            right: 70px;
            height: 15px;
            background: linear-gradient(90deg, rgba(245,158,11,0.18), rgba(55,65,81,0.08));
            transform: translateY(-50%);
            z-index: 0;
            pointer-events: none;
        }}

        .sortable-item {{
            flex: 0 0 auto !important;
            width: 130px !important;
            height: 78px !important;
            background: {c["surface"]} !important;
            border: 1.5px solid {c["border_light"]} !important;
            border-radius: 12px !important;
            display: flex !important;
            flex-direction: column !important;
            align-items: center !important;
            justify-content: center !important;
            color: {c["text"]} !important;
            font-size: 14px !important;
            font-weight: 600 !important;
            margin: 24px 20px !important;
            padding: 0 !important;
            position: relative !important;
            cursor: grab !important;
            z-index: 1 !important;
            transition: border-color 0.2s, box-shadow 0.2s !important;
        }}

        .sortable-item:hover {{
            border-color: {c["text_subtle"]} !important;
        }}

        /* Seta -> entre os cards */
        .sortable-item:not(:last-child)::after {{
            content: '→';
            position: absolute;
            right: -20px;
            top: 50%;
            transform: translateX(50%) translateY(-50%);
            color: {c["text_subtle"]};
            font-size: 18px;
            font-weight: 600;
            pointer-events: none;
            z-index: 2;
        }}

        /* Card do proximo vendedor */
        .sortable-item:first-child {{
            border-color: {c["primary"]} !important;
            box-shadow: 0 0 16px rgba(245,158,11,0.12) !important;
            padding-bottom: 14px !important;
        }}

        /* Badge PROXIMO */
        .sortable-item:first-child::before {{
            content: 'PROXIMO';
            position: absolute;
            bottom: 7px;
            background: {c["primary"]};
            color: #000;
            font-size: 8px;
            font-weight: 800;
            padding: 2px 10px;
            border-radius: 3px;
            letter-spacing: 0.6px;
            white-space: nowrap;
            text-transform: uppercase;
        }}

        /* Esconder texto de acessibilidade do dnd-kit */
        div[id^="DndDescribedBy"],
        div[id^="DndLiveRegion"],
        #root > div[style*="display"] {{
            display: none !important;
            visibility: hidden !important;
            position: absolute !important;
            width: 0 !important;
            height: 0 !important;
            overflow: hidden !important;
        }}
    """

    nova_ordem = sort_items(
        nomes,
        direction="horizontal",
        custom_style=_fila_css,
        key="fila_final_full_v1",
    )

    novos_ids = [next(v["id"] for v in v_sorted if v["nome"] == n) for n in nova_ordem]
    if novos_ids != [v["id"] for v in v_sorted]:
        reordenar_vendedores(loja["loja_id"], novos_ids)
        st.rerun()
else:
    st.info("Nenhum vendedor disponível.")

st.markdown(
    '<div style="font-size:16px; font-weight:600; margin-top:20px; margin-bottom:5px;">Atividades Recentes</div>',
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
            data_fmt = _formatar_data_atividade(a["criado_em"])
            timeline_html += f'<div style="display: flex; gap: 12px; position: relative; padding-bottom: 15px;">{line}<div style="z-index: 1; color: #f59e0b; font-size:12px;">{icon}</div><div><div style="font-size: 12px; color: #f1f5f9; font-weight: 500;">{a["descricao"]}</div><div style="font-size: 10px; color: #94a3b8;">{data_fmt}</div></div></div>'
        timeline_html += "</div>"
        st.markdown(timeline_html, unsafe_allow_html=True)

st.markdown("---")

# ============================================
# 5. SEÇÃO DE ANALYTICS (GRID COMPLETO)
# ============================================
st.markdown("### Inteligência de Dados")


def _set_filtro_hoje():
    st.session_state["analytics_d_ini"] = date.today()
    st.session_state["analytics_d_fim"] = date.today()


if "analytics_d_ini" not in st.session_state:
    st.session_state["analytics_d_ini"] = date.today() - timedelta(days=30)
if "analytics_d_fim" not in st.session_state:
    st.session_state["analytics_d_fim"] = date.today()

c_f1, c_f2, c_f3, _ = st.columns([1, 1, 0.5, 2.52])
d_ini = c_f1.date_input("Início", key="analytics_d_ini", format="DD/MM/YYYY")
d_fim = c_f2.date_input("Fim", key="analytics_d_fim", format="DD/MM/YYYY")
c_f3.markdown("<div style='height:27px'></div>", unsafe_allow_html=True)
c_f3.button("Hoje", use_container_width=True, on_click=_set_filtro_hoje)

col_trend, col_funnel = st.columns([1, 1], gap="small")
with col_trend:
    with st.container(border=True):
        leads_dia = get_leads_por_dia(
            loja_id=loja["loja_id"], data_inicio=d_ini, data_fim=d_fim
        )
        if leads_dia:
            df_dia = pd.DataFrame(leads_dia).sort_values("data")
            df_dia["data_fmt"] = pd.to_datetime(df_dia["data"]).dt.strftime("%d/%m")
            st.markdown(
                f'<div style="font-weight:600;margin-bottom:10px;">Fluxo de Leads (Total: {int(df_dia["total"].sum())})</div>',
                unsafe_allow_html=True,
            )
            if len(df_dia) == 1:
                fig_t = px.bar(df_dia, x="data_fmt", y="total")
                fig_t.update_traces(marker_color=c["primary"])
            else:
                fig_t = px.line(
                    df_dia, x="data_fmt", y="total", line_shape="spline", markers=True
                )
                fig_t.update_traces(line_color=c["primary"])
            fig_t.update_traces(hovertemplate="total=%{y}<extra></extra>")
            fig_t.update_layout(
                **plotly_defaults,
                height=250,
                margin=dict(l=0, r=0, t=10, b=0),
                xaxis_title=None,
                yaxis_title=None,
                yaxis=dict(dtick=1),
            )
            st.plotly_chart(fig_t, use_container_width=True)
        else:
            st.markdown(
                '<div style="font-weight:600;margin-bottom:10px;">Fluxo de Leads</div>',
                unsafe_allow_html=True,
            )
            st.caption("Nenhum lead no periodo selecionado.")

with col_funnel:
    with st.container(border=True):
        st.markdown(
            '<div style="font-weight:600;margin-bottom:10px;">Funil de Vendas</div>',
            unsafe_allow_html=True,
        )
        f_data = get_metricas_funil(
            loja_id=loja["loja_id"], data_inicio=d_ini, data_fim=d_fim
        )
        _total_leads = f_data["negociando"] + f_data["sem_resposta"] + f_data["sem_interesse"] + f_data["vendido"]
        fig_f = go.Figure(
            go.Funnel(
                y=["Leads", "Negociando", "Vendido"],
                x=[_total_leads, f_data["negociando"], f_data["vendido"]],
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
        else:
            st.caption("Nenhum lead no periodo selecionado.")

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
            fig_h = px.bar(df_h, x="hora_formatada", y="total", labels={"hora_formatada": "Hora"})
            fig_h.update_traces(marker_color=c["primary"])
            fig_h.update_layout(
                **plotly_defaults, height=200, margin=dict(l=0, r=0, t=0, b=0)
            )
            st.plotly_chart(fig_h, use_container_width=True)
        else:
            st.caption("Nenhum lead no periodo selecionado.")

st.caption("Lead Automation System | v2.3 Final")
