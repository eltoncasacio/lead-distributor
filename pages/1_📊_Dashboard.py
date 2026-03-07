"""
Dashboard com layout redesenhado: KPI cards, fila+timeline lado a lado, analytics em grid.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
from streamlit_sortables import sort_items
from utils.ui import render_page_header, loading_spinner, error_message, inject_global_css, get_sortable_style
from utils.auth import obter_loja_logada
from utils.theme import get_colors, get_plotly_layout_defaults
from utils.queries import (
    get_metricas_hoje,
    get_leads_por_dia,
    get_leads_por_hora,
    get_leads_por_origem_comparativo,
    listar_vendedores,
    obter_proximo_vendedor,
    get_atividades_recentes,
    reordenar_vendedores,
    get_metricas_funil,
    get_limite_leads,
)

render_page_header("Dashboard")
inject_global_css()

loja = obter_loja_logada()
c = get_colors()
plotly_defaults = get_plotly_layout_defaults()

# ============================================
# HEADER BAR: filtro de data + total de leads
# ============================================

with loading_spinner("Carregando metricas..."):
    metricas = get_metricas_hoje(loja["loja_id"])
    vendedores = listar_vendedores(loja["loja_id"])
    proximo = obter_proximo_vendedor(loja["loja_id"])
    limite = get_limite_leads(loja["loja_id"])

vendedores_ativos = [v for v in vendedores if v["status"] == "ativo"]

col_filter1, col_filter2, col_total = st.columns([1.5, 1.5, 5], gap="small")

with col_filter1:
    data_inicio = st.date_input(
        "De",
        value=date.today() - timedelta(days=30),
        max_value=date.today(),
        key="data_inicio_global",
    )

with col_filter2:
    data_fim = st.date_input(
        "Ate",
        value=date.today(),
        max_value=date.today(),
        key="data_fim_global",
    )

if data_inicio > data_fim:
    st.error("Data inicial nao pode ser maior que data final")
    st.stop()

leads_periodo = get_leads_por_dia(loja["loja_id"], data_inicio=data_inicio, data_fim=data_fim)
total_periodo = sum(d["total"] for d in leads_periodo) if leads_periodo else 0

with col_total:
    total_txt = f"{total_periodo}/{limite}" if limite else str(total_periodo)
    st.markdown(
        f'<div style="padding-top:28px;">'
        f'<span style="color:{c["text_muted"]};font-size:14px;">Total de Leads: </span>'
        f'<span style="color:{c["text"]};font-size:14px;font-weight:600;">{total_txt}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

# ============================================
# SECAO 1: KPI CARDS (icone top-left, texto left-aligned)
# ============================================

MESES_PT = {1:"Jan",2:"Fev",3:"Mar",4:"Abr",5:"Mai",6:"Jun",7:"Jul",8:"Ago",9:"Set",10:"Out",11:"Nov",12:"Dez"}


# SVG icons (outlined, monocromo)
_SVG_PEOPLE = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>'
_SVG_CLOCK = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>'
_SVG_PERSON = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>'
_SVG_TEAM = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="19" y1="8" x2="19" y2="14"/><line x1="22" y1="11" x2="16" y2="11"/></svg>'


def _icon_box(svg_template: str, amber: bool = False) -> str:
    bg = c["primary"] if amber else c["border"]
    stroke = "#000" if amber else c["text_muted"]
    svg = svg_template.format(color=stroke)
    return (
        f'<div style="display:inline-flex;align-items:center;justify-content:center;'
        f'width:40px;height:40px;border-radius:10px;background:{bg};">{svg}</div>'
    )


def render_kpi_card(icon_html: str, label: str, value, subtitle: str = ""):
    sub = f'<div style="color:{c["text_subtle"]};font-size:12px;margin-top:6px;">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f"""
        <div style="background:{c["surface"]};border:1px solid {c["border"]};border-radius:12px;
                    padding:20px;">
            <div style="margin-bottom:14px;">{icon_html}</div>
            <div style="color:{c["text_muted"]};font-size:12px;margin-bottom:4px;">{label}</div>
            <div style="color:{c["text"]};font-size:28px;font-weight:700;line-height:1.1;">{value}</div>
            {sub}
        </div>
        """,
        unsafe_allow_html=True,
    )


# Calcular delta vs ontem
_hoje_str = date.today().isoformat()
_ontem_str = (date.today() - timedelta(days=1)).isoformat()
_leads_hoje = next((d["total"] for d in leads_periodo if d["data"] == _hoje_str), 0)
_leads_ontem = next((d["total"] for d in leads_periodo if d["data"] == _ontem_str), 0)
if _leads_ontem > 0:
    _delta_pct = ((_leads_hoje - _leads_ontem) / _leads_ontem) * 100
    _delta_sinal = "+" if _delta_pct >= 0 else ""
    _delta_cor = c["success"] if _delta_pct >= 0 else c["error"]
    _delta_txt = f'<span style="color:{_delta_cor}">{_delta_sinal}{_delta_pct:.0f}% vs ontem</span>'
elif _leads_hoje > 0:
    _delta_txt = f'<span style="color:{c["success"]}">+{_leads_hoje} vs ontem</span>'
else:
    _delta_txt = ""

kpi1, kpi2, kpi3, kpi4 = st.columns(4, gap="medium")

with kpi1:
    render_kpi_card(
        _icon_box(_SVG_PEOPLE),
        "Leads Hoje",
        metricas["total_leads"],
        _delta_txt,
    )

with kpi2:
    ultimo = metricas["ultimo_lead"] if metricas["ultimo_lead"] else "--"
    render_kpi_card(
        _icon_box(_SVG_CLOCK),
        "Ultimo Lead Recebido",
        ultimo,
    )

with kpi3:
    proximo_nome = proximo["nome"] if proximo else "Nenhum"
    render_kpi_card(
        _icon_box(_SVG_PERSON, amber=True),
        "Proximo Vendedor na Fila",
        proximo_nome,
    )

with kpi4:
    render_kpi_card(
        _icon_box(_SVG_TEAM),
        "Vendedores Ativos",
        len(vendedores_ativos),
    )

st.markdown("")

# ============================================
# SECAO 2: FILA + ATIVIDADES (lado a lado)
# ============================================

col_fila, col_atividades = st.columns([1.2, 1], gap="medium")

# --- FILA DE DISTRIBUICAO ---
with col_fila:
    # CSS para tornar a borda deste container amber
    st.markdown(
        f"""<style>
        /* Amber border no primeiro container dentro da coluna da fila */
        [data-testid="stVerticalBlock"] > div:nth-child(1) > [data-testid="stVerticalBlockBorderWrapper"] {{
            border-color: {c["primary"]} !important;
        }}
        </style>""",
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        st.markdown(
            f'<div style="color:{c["text"]};font-size:18px;font-weight:600;margin-bottom:8px;">'
            f'Fila de Distribuicao</div>',
            unsafe_allow_html=True,
        )

        if len(vendedores_ativos) >= 1:
            vendedores_ativos_sorted = sorted(vendedores_ativos, key=lambda x: x["criado_em"])

            if proximo:
                idx = next((i for i, v in enumerate(vendedores_ativos_sorted) if v["id"] == proximo["id"]), 0)
                vendedores_ativos_sorted = vendedores_ativos_sorted[idx:] + vendedores_ativos_sorted[:idx]

            ordem_original_ids = [v["id"] for v in vendedores_ativos_sorted]
            if "ordem_original_dashboard" not in st.session_state:
                st.session_state.ordem_original_dashboard = ordem_original_ids

            nomes = [v["nome"] for v in vendedores_ativos_sorted]

            # Sortable vertical com estilo customizado
            sortable_style = f"""
                background-color: {c["surface"]};
                border: 1px solid {c["border"]};
                border-radius: 8px;
                padding: 14px 16px;
                margin: 6px 0;
                color: {c["text"]};
                font-weight: 500;
                font-size: 15px;
                cursor: grab;
                transition: all 0.15s ease;
                list-style: none;
            """

            nova_ordem_nomes = sort_items(
                nomes,
                multi_containers=False,
                direction="vertical",
                key="reorder_vendedores_dashboard",
                custom_style=sortable_style,
            )

            # JS: numerar itens, badge NEXT no primeiro, styling amber
            st.components.v1.html(f"""
            <script>
            (function() {{
                function styleItems() {{
                    try {{
                        var frames = window.parent.document.querySelectorAll('iframe');
                        for (var i = 0; i < frames.length; i++) {{
                            try {{
                                var doc = frames[i].contentDocument;
                                if (!doc) continue;
                                var items = doc.querySelectorAll('li');
                                if (items.length < 1) continue;
                                for (var j = 0; j < items.length; j++) {{
                                    var li = items[j];
                                    // Remover numeracao/badge anterior (evitar duplicatas)
                                    var old = li.querySelectorAll('.q-num,.q-badge');
                                    old.forEach(function(el) {{ el.remove(); }});

                                    li.style.position = 'relative';
                                    li.style.paddingLeft = '44px';
                                    li.style.paddingRight = '16px';

                                    // Numero
                                    var num = document.createElement('span');
                                    num.className = 'q-num';
                                    num.textContent = (j+1);
                                    num.style.cssText = 'position:absolute;left:14px;top:50%;transform:translateY(-50%);color:{c["text_muted"]};font-weight:600;font-size:15px;';
                                    li.insertBefore(num, li.firstChild);

                                    if (j === 0) {{
                                        li.style.background = '{c["surface"]}';
                                        li.style.border = '1px solid {c["primary"]}';
                                        li.style.fontWeight = '700';
                                        // Badge NEXT
                                        var badge = document.createElement('span');
                                        badge.className = 'q-badge';
                                        badge.textContent = 'NEXT';
                                        badge.style.cssText = 'position:absolute;right:12px;top:50%;transform:translateY(-50%);background:{c["primary"]};color:#000;font-size:11px;font-weight:700;padding:3px 10px;border-radius:4px;letter-spacing:0.5px;';
                                        li.appendChild(badge);
                                    }} else {{
                                        li.style.background = '{c["surface"]}';
                                        li.style.border = '1px solid {c["border"]}';
                                        li.style.fontWeight = '500';
                                    }}
                                }}
                                var parent = items[0].parentElement;
                                if (parent && !parent._obs) {{
                                    parent._obs = true;
                                    new MutationObserver(function() {{
                                        setTimeout(styleItems, 50);
                                    }}).observe(parent, {{childList: true, subtree: true}});
                                }}
                            }} catch(e) {{}}
                        }}
                    }} catch(e) {{}}
                }}
                setTimeout(styleItems, 300);
                setTimeout(styleItems, 800);
                setTimeout(styleItems, 1500);
            }})();
            </script>
            """, height=0)

            st.caption("Arraste para reordenar a fila")

            # Detectar mudanca e auto-save
            nova_ordem_ids = []
            for nome in nova_ordem_nomes:
                vendedor = next((v for v in vendedores_ativos_sorted if v["nome"] == nome), None)
                if vendedor:
                    nova_ordem_ids.append(vendedor["id"])

            ordem_mudou = nova_ordem_ids != st.session_state.ordem_original_dashboard

            if ordem_mudou and len(nova_ordem_ids) == len(vendedores_ativos):
                try:
                    reordenar_vendedores(loja["loja_id"], nova_ordem_ids)
                    st.session_state.ordem_original_dashboard = nova_ordem_ids
                    st.session_state.atividades_loaded = False
                    st.rerun()
                except Exception as e:
                    error_message(f"Erro ao salvar: {str(e)}")

        else:
            st.warning("Nenhum vendedor ativo.")

# --- ATIVIDADES RECENTES ---
with col_atividades:
    with st.container(border=True):
        col_header, col_refresh = st.columns([5, 1])
        with col_header:
            st.markdown(
                f'<div style="font-size:18px;font-weight:600;color:{c["text"]};">'
                f'Atividades Recentes</div>',
                unsafe_allow_html=True,
            )
        with col_refresh:
            if st.button("&#128260;", key="refresh_atividades", help="Atualizar"):
                st.session_state.atividades_todas = []
                st.session_state.atividades_has_more = True
                st.session_state.atividades_loaded = False
                st.rerun()

        if "atividades_todas" not in st.session_state:
            st.session_state.atividades_todas = []
        if "atividades_has_more" not in st.session_state:
            st.session_state.atividades_has_more = True
        if "atividades_loaded" not in st.session_state:
            st.session_state.atividades_loaded = False

        BATCH_SIZE = 20
        if not st.session_state.atividades_loaded:
            st.session_state.atividades_todas = get_atividades_recentes(
                loja["loja_id"], limite=BATCH_SIZE, offset=0
            )
            st.session_state.atividades_has_more = len(st.session_state.atividades_todas) == BATCH_SIZE
            st.session_state.atividades_loaded = True

        atividades = st.session_state.atividades_todas

        # Icones SVG-like por tipo de atividade
        ICON_MAP = {
            "novo_lead": "&#128229;",
            "status_lead_alterado": "&#128260;",
            "vendedor_adicionado": "&#10133;",
            "vendedor_removido": "&#10060;",
            "vendedor_inativado": "&#9199;",
            "vendedor_reativado": "&#9654;&#65039;",
            "fila_reordenada": "&#128256;",
        }

        if atividades:
            atividades_html = []
            for i, ativ in enumerate(atividades):
                timestamp = pd.to_datetime(ativ["criado_em"])
                agora = pd.Timestamp.now(tz="America/Sao_Paulo")
                minutos = int((agora - timestamp).total_seconds() / 60)

                if minutos < 1:
                    tempo_str = "Agora"
                elif minutos < 60:
                    tempo_str = f"Ha {minutos} minutos"
                elif minutos < 1440:
                    tempo_str = f"Ha {minutos // 60} horas"
                else:
                    tempo_str = f"Ha {minutos // 1440} dias"

                icon = ICON_MAP.get(ativ.get("tipo", ""), "&#128196;")
                # Dot color: amber for first, gray for rest
                dot_color = c["primary"] if i == 0 else c["text_subtle"]

                atividades_html.append(
                    f'<div style="display:flex;align-items:flex-start;padding:12px 0;'
                    f'border-bottom:1px solid {c["border"]};">'
                    # Icon
                    f'<div style="font-size:16px;margin-right:12px;min-width:24px;text-align:center;'
                    f'margin-top:2px;">{icon}</div>'
                    # Dot connector
                    f'<div style="display:flex;flex-direction:column;align-items:center;margin-right:12px;'
                    f'min-width:12px;padding-top:6px;">'
                    f'<div style="width:8px;height:8px;border-radius:50%;background:{dot_color};"></div>'
                    f'<div style="width:1px;height:24px;background:{c["border"]};margin-top:4px;"></div>'
                    f'</div>'
                    # Content
                    f'<div style="flex:1;">'
                    f'<div style="color:{c["text"]};font-size:13px;line-height:1.5;font-weight:500;">'
                    f'{ativ["descricao"]}</div>'
                    f'<div style="color:{c["text_subtle"]};font-size:11px;margin-top:3px;">'
                    f'{tempo_str}</div>'
                    f'</div></div>'
                )

            if st.session_state.atividades_has_more:
                atividades_html.append(
                    f'<div id="load-more-trigger" style="padding:12px;text-align:center;'
                    f'color:{c["primary"]};font-size:13px;font-weight:500;cursor:pointer;'
                    f'border-top:1px solid {c["border"]};margin-top:8px;">Carregar mais &#8595;</div>'
                )

            html_code = f"""
            <div id="atividades-container" style="max-height:380px;overflow-y:auto;padding-right:8px;">
                {''.join(atividades_html)}
            </div>
            <style>
            #atividades-container {{
                scrollbar-width: thin;
                scrollbar-color: {c["scrollbar_thumb"]} {c["scrollbar_track"]};
            }}
            #atividades-container::-webkit-scrollbar {{ width: 6px; }}
            #atividades-container::-webkit-scrollbar-track {{
                background: {c["scrollbar_track"]}; border-radius: 3px;
            }}
            #atividades-container::-webkit-scrollbar-thumb {{
                background: {c["scrollbar_thumb"]}; border-radius: 3px;
            }}
            </style>
            <script>
            const container = document.getElementById('atividades-container');
            const trigger = document.getElementById('load-more-trigger');
            if (container && trigger) {{
                const observer = new IntersectionObserver((entries) => {{
                    entries.forEach(entry => {{
                        if (entry.isIntersecting) {{
                            const buttons = window.parent.document.querySelectorAll('button[kind="secondary"]');
                            const btn = Array.from(buttons).find(b => b.textContent.includes('Carregar mais'));
                            if (btn) btn.click();
                        }}
                    }});
                }}, {{ root: container, threshold: 0.1 }});
                observer.observe(trigger);
            }}
            </script>
            """
            st.components.v1.html(html_code, height=420, scrolling=False)

            if st.session_state.atividades_has_more:
                st.markdown(
                    '<style>div[data-testid="column"] > div > button[kind="secondary"]'
                    "{position:absolute;opacity:0;pointer-events:none;height:0;width:0;overflow:hidden;}</style>",
                    unsafe_allow_html=True,
                )
                if st.button("Carregar mais atividades", key="carregar_mais_trigger", type="secondary"):
                    novo_offset = len(st.session_state.atividades_todas)
                    novas = get_atividades_recentes(loja["loja_id"], limite=BATCH_SIZE, offset=novo_offset)
                    if novas:
                        st.session_state.atividades_todas.extend(novas)
                        st.session_state.atividades_has_more = len(novas) == BATCH_SIZE
                    else:
                        st.session_state.atividades_has_more = False
                    st.rerun()

            st.caption(f"Mostrando {len(atividades)} atividades")
        else:
            st.info("Nenhuma atividade registrada")

st.markdown("")

# ============================================
# SECAO 3: ANALYTICS (grid, sem tabs)
# ============================================

# --- ROW 1: Tendencia (~60%) + Funil (~40%) ---
col_tendencia, col_funil = st.columns([1.4, 1], gap="medium")

with col_tendencia:
    with st.container(border=True):
        leads_dia = get_leads_por_dia(loja["loja_id"], data_inicio=data_inicio, data_fim=data_fim)

        if leads_dia:
            df_dia = pd.DataFrame(leads_dia)
            df_dia["data"] = pd.to_datetime(df_dia["data"])

            total_t = int(df_dia["total"].sum())
            media_t = df_dia["total"].mean()
            pico_row = df_dia.loc[df_dia["total"].idxmax()]
            pico_data_str = f"{int(pico_row['data'].day)} {MESES_PT[pico_row['data'].month]}"
            pico_val = int(pico_row["total"])

            # Header com titulo + stats inline (como no mockup)
            st.markdown(
                f"""
                <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px;">
                    <div style="color:{c["text"]};font-size:16px;font-weight:600;">Tendencia de Leads</div>
                    <div style="display:flex;gap:12px;">
                        <div style="background:{c["surface_hover"]};border:1px solid {c["border"]};
                                    border-radius:6px;padding:6px 12px;text-align:center;">
                            <div style="color:{c["text_muted"]};font-size:10px;">Total:</div>
                            <div style="color:{c["text"]};font-size:14px;font-weight:600;">{total_t}</div>
                        </div>
                        <div style="background:{c["surface_hover"]};border:1px solid {c["border"]};
                                    border-radius:6px;padding:6px 12px;text-align:center;">
                            <div style="color:{c["text_muted"]};font-size:10px;">Media Diaria:</div>
                            <div style="color:{c["text"]};font-size:14px;font-weight:600;">{media_t:.1f}</div>
                        </div>
                        <div style="background:{c["surface_hover"]};border:1px solid {c["border"]};
                                    border-radius:6px;padding:6px 12px;text-align:center;">
                            <div style="color:{c["text_muted"]};font-size:10px;">Dia de Pico:</div>
                            <div style="color:{c["text"]};font-size:14px;font-weight:600;">{pico_data_str} ({pico_val} leads)</div>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Annotation no pico
            fig = px.line(df_dia, x="data", y="total", markers=True, line_shape="spline")
            fig.update_layout(
                **plotly_defaults,
                showlegend=False,
                xaxis_title=None,
                yaxis_title=None,
                height=280,
                margin=dict(l=0, r=0, t=30, b=0),
            )
            fig.update_traces(line_color=c["primary"], marker=dict(size=7, color=c["primary"]))

            # Annotation no dia de pico
            fig.add_annotation(
                x=pico_row["data"],
                y=pico_val,
                text=f"Dia de Pico: {pico_data_str} ({pico_val} leads)",
                showarrow=True,
                arrowhead=2,
                arrowcolor=c["text_muted"],
                font=dict(size=11, color=c["text"]),
                bgcolor=c["surface"],
                bordercolor=c["border"],
                borderwidth=1,
                borderpad=4,
                ax=0,
                ay=-35,
            )

            st.plotly_chart(fig, use_container_width=True)
        else:
            st.markdown(
                f'<div style="color:{c["text"]};font-size:16px;font-weight:600;margin-bottom:12px;">'
                f'Tendencia de Leads</div>',
                unsafe_allow_html=True,
            )
            st.info("Nenhum lead no periodo")

with col_funil:
    with st.container(border=True):
        st.markdown(
            f'<div style="color:{c["text"]};font-size:16px;font-weight:600;margin-bottom:12px;">'
            f'Funnel de Vendas</div>',
            unsafe_allow_html=True,
        )

        metricas_funil = get_metricas_funil(loja["loja_id"], data_inicio=data_inicio, data_fim=data_fim)

        novo = metricas_funil["novo"]
        atendido = metricas_funil["atendido"]
        negociando = metricas_funil["negociando"]
        venda = metricas_funil["venda_concretizada"]

        taxa_atendimento = (atendido / novo * 100) if novo > 0 else 0
        taxa_negociacao = (negociando / atendido * 100) if atendido > 0 else 0
        taxa_venda = (venda / negociando * 100) if negociando > 0 else 0

        # Big numbers no topo (como mockup: 35  18  52%)
        st.markdown(
            f"""
            <div style="display:flex;gap:16px;margin-bottom:12px;">
                <div style="background:{c["surface_hover"]};border:1px solid {c["border"]};
                            border-radius:8px;padding:10px 16px;min-width:60px;text-align:center;">
                    <div style="color:{c["text"]};font-size:24px;font-weight:700;">{novo}</div>
                </div>
                <div style="background:{c["surface_hover"]};border:1px solid {c["border"]};
                            border-radius:8px;padding:10px 16px;min-width:60px;text-align:center;">
                    <div style="color:{c["text"]};font-size:24px;font-weight:700;">{atendido}</div>
                </div>
                <div style="background:{c["surface_hover"]};border:1px solid {c["border"]};
                            border-radius:8px;padding:10px 16px;min-width:60px;text-align:center;">
                    <div style="color:{c["text"]};font-size:24px;font-weight:700;">{taxa_atendimento:.0f}%</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        f1, f2, f3 = st.columns(3)
        with f1:
            st.metric("% Atendidos", f"{taxa_atendimento:.1f}%")
        with f2:
            st.metric("% Negociando", f"{taxa_negociacao:.1f}%")
        with f3:
            st.metric("% Vendas", f"{taxa_venda:.1f}%")

        if novo > 0:
            stages = ["Leads", "Contatados", "Negociando", "Vendas"]
            values = [novo, atendido, negociando, venda]

            fig = go.Figure(go.Funnel(
                y=stages,
                x=values,
                textposition="inside",
                textinfo="value+percent initial",
                marker=dict(
                    color=[c["primary"], c["primary_dark"], "#b45309", "#92400e"],
                    line=dict(width=2, color=c["background"]),
                ),
                connector={"line": {"color": c["border"], "width": 2}},
            ))
            fig.update_layout(
                **plotly_defaults,
                height=220,
                margin=dict(l=0, r=0, t=10, b=0),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sem dados para funil")

# --- ROW 2: Origem + Hora ---
col_origem, col_hora = st.columns(2, gap="medium")

with col_origem:
    with st.container(border=True):
        st.markdown(
            f'<div style="color:{c["text"]};font-size:16px;font-weight:600;margin-bottom:12px;">'
            f'Leads por Origem</div>',
            unsafe_allow_html=True,
        )

        dados_origem = get_leads_por_origem_comparativo(loja["loja_id"], data_inicio=data_inicio, data_fim=data_fim)
        atual = dados_origem["atual"]
        total_orig = sum(atual.values())

        if total_orig > 0:
            origens_sorted = sorted(atual.keys(), key=lambda o: atual[o], reverse=True)
            labels = origens_sorted
            values = [atual[o] for o in origens_sorted]
            cores = [c["primary"], c["primary_dark"], c["text_subtle"]]

            fig = go.Figure(go.Bar(
                y=labels,
                x=values,
                orientation="h",
                marker=dict(color=cores[:len(labels)]),
                text=values,
                textposition="auto",
                textfont=dict(color=c["text"]),
            ))
            fig.update_layout(
                **plotly_defaults,
                showlegend=False,
                height=250,
                margin=dict(l=0, r=20, t=10, b=0),
                xaxis_title=None,
                yaxis_title=None,
                yaxis=dict(autorange="reversed"),
            )
            st.plotly_chart(fig, use_container_width=True)

            anterior = dados_origem["anterior"]
            delta_parts = []
            for o in origens_sorted:
                d = atual[o] - anterior.get(o, 0)
                sinal = "+" if d > 0 else ""
                delta_parts.append(f"{o}: {sinal}{d}")
            st.caption(f"vs periodo anterior: {' | '.join(delta_parts)}")
        else:
            st.info("Sem dados no periodo")

with col_hora:
    with st.container(border=True):
        st.markdown(
            f'<div style="color:{c["text"]};font-size:16px;font-weight:600;margin-bottom:12px;">'
            f'Leads por Hora</div>',
            unsafe_allow_html=True,
        )

        leads_hora = get_leads_por_hora(loja["loja_id"], data_inicio=data_inicio, data_fim=data_fim)

        if leads_hora:
            df_hora = pd.DataFrame(leads_hora)

            fig = px.bar(
                df_hora,
                x="hora_formatada",
                y="total",
                color="total",
                color_continuous_scale=[
                    [0, c["border"]],
                    [0.5, c["primary"]],
                    [1, c["primary_light"]],
                ],
                text="total",
            )
            fig.update_layout(
                **plotly_defaults,
                showlegend=False,
                coloraxis_showscale=False,
                height=250,
                margin=dict(l=0, r=0, t=10, b=0),
                xaxis_title=None,
                yaxis_title=None,
                xaxis=dict(tickangle=-45, tickmode="linear"),
            )
            fig.update_traces(textposition="outside")
            st.plotly_chart(fig, use_container_width=True)

            hora_pico = df_hora.loc[df_hora["total"].idxmax()]
            st.caption(f"Pico: {hora_pico['hora_formatada']} ({int(hora_pico['total'])} leads)")
        else:
            st.info("Sem dados no periodo")

# Footer
st.divider()
st.caption("Use os filtros de data no topo para ajustar todas as analises.")
