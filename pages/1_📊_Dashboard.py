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

# Header compacto
render_page_header("Dashboard")
inject_global_css()

loja = obter_loja_logada()
c = get_colors()

# ============================================
# HEADER BAR: filtro de data + total de leads
# ============================================

col_filter1, col_filter2, col_spacer, col_total = st.columns([1.5, 1.5, 3, 2], gap="small")

with col_filter1:
    data_inicio = st.date_input(
        "De",
        value=date.today() - timedelta(days=30),
        max_value=date.today(),
        key="data_inicio_global"
    )

with col_filter2:
    data_fim = st.date_input(
        "Ate",
        value=date.today(),
        max_value=date.today(),
        key="data_fim_global"
    )

if data_inicio > data_fim:
    st.error("Data inicial nao pode ser maior que data final")
    st.stop()

# Total de leads do periodo + limite do plano
with col_total:
    limite = get_limite_leads(loja["loja_id"])
    leads_periodo = get_leads_por_dia(loja["loja_id"], data_inicio=data_inicio, data_fim=data_fim)
    total_periodo = sum(d["total"] for d in leads_periodo) if leads_periodo else 0
    if limite:
        st.markdown(
            f'<div style="text-align:right;padding-top:28px;">'
            f'<span style="color:{c["text_muted"]};font-size:13px;">Total de Leads</span><br>'
            f'<span style="color:{c["primary"]};font-size:24px;font-weight:700;">{total_periodo}</span>'
            f'<span style="color:{c["text_subtle"]};font-size:16px;">/{limite}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div style="text-align:right;padding-top:28px;">'
            f'<span style="color:{c["text_muted"]};font-size:13px;">Total de Leads</span><br>'
            f'<span style="color:{c["primary"]};font-size:24px;font-weight:700;">{total_periodo}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )


# ============================================
# SECAO 1: KPI CARDS
# ============================================

with loading_spinner("Carregando metricas..."):
    metricas = get_metricas_hoje(loja["loja_id"])
    vendedores = listar_vendedores(loja["loja_id"])
    proximo = obter_proximo_vendedor(loja["loja_id"])

vendedores_ativos = [v for v in vendedores if v["status"] == "ativo"]


def render_kpi_card(icon: str, label: str, value, subtitle: str = ""):
    sub_html = f'<div style="color:{c["text_subtle"]};font-size:12px;margin-top:2px;">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f"""
        <div style="background:{c["surface"]};border:1px solid {c["border"]};border-radius:12px;
                    padding:20px;text-align:center;">
            <div style="font-size:28px;margin-bottom:4px;">{icon}</div>
            <div style="color:{c["text_muted"]};font-size:12px;text-transform:uppercase;
                        letter-spacing:0.5px;">{label}</div>
            <div style="color:{c["text"]};font-size:28px;font-weight:700;margin:4px 0;">{value}</div>
            {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


kpi1, kpi2, kpi3, kpi4 = st.columns(4, gap="medium")

with kpi1:
    render_kpi_card(
        icon="&#128229;",
        label="Leads Hoje",
        value=metricas["total_leads"],
        subtitle="recebidos hoje",
    )

with kpi2:
    ultimo = metricas["ultimo_lead"] if metricas["ultimo_lead"] else "---"
    render_kpi_card(
        icon="&#128340;",
        label="Ultimo Lead",
        value=ultimo,
        subtitle="horario",
    )

with kpi3:
    proximo_nome = proximo["nome"] if proximo else "Nenhum"
    render_kpi_card(
        icon="&#128100;",
        label="Proximo na Fila",
        value=proximo_nome,
        subtitle="recebe o proximo lead",
    )

with kpi4:
    render_kpi_card(
        icon="&#128101;",
        label="Vendedores Ativos",
        value=len(vendedores_ativos),
        subtitle=f"de {len(vendedores)} total",
    )

st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

# ============================================
# SECAO 2: FILA + ATIVIDADES (lado a lado)
# ============================================

col_fila, col_atividades = st.columns([1.2, 1], gap="medium")

# --- FILA DE DISTRIBUICAO ---
with col_fila:
    st.markdown(
        f"""
        <div style="background:{c["surface"]};border:1px solid {c["primary"]};border-radius:12px;
                    padding:20px;min-height:420px;">
            <div style="color:{c["text"]};font-size:18px;font-weight:600;margin-bottom:16px;">
                Fila de Distribuicao
            </div>
        """,
        unsafe_allow_html=True,
    )

    if len(vendedores_ativos) > 1:
        vendedores_ativos_sorted = sorted(vendedores_ativos, key=lambda x: x["criado_em"])

        if proximo:
            idx = next((i for i, v in enumerate(vendedores_ativos_sorted) if v["id"] == proximo["id"]), 0)
            vendedores_ativos_sorted = vendedores_ativos_sorted[idx:] + vendedores_ativos_sorted[:idx]

        ordem_original_ids = [v["id"] for v in vendedores_ativos_sorted]
        if "ordem_original_dashboard" not in st.session_state:
            st.session_state.ordem_original_dashboard = ordem_original_ids

        nomes = [v["nome"] for v in vendedores_ativos_sorted]
        usar_horizontal = len(nomes) <= 8

        st.markdown(
            f'<div style="display:inline-block;background:{c["primary"]};color:#000;'
            f'font-size:11px;font-weight:700;padding:2px 8px;border-radius:4px;'
            f'margin-bottom:8px;text-transform:uppercase;letter-spacing:0.5px;">PROXIMO</div>',
            unsafe_allow_html=True,
        )

        nova_ordem_nomes = sort_items(
            nomes,
            multi_containers=False,
            direction="horizontal" if usar_horizontal else "vertical",
            key="reorder_vendedores_dashboard",
            custom_style=get_sortable_style(horizontal=usar_horizontal),
        )

        # JS: destacar primeiro item com gradient amber
        st.components.v1.html(f"""
        <script>
        (function() {{
            function styleFirst() {{
                try {{
                    var frames = window.parent.document.querySelectorAll('iframe');
                    for (var i = 0; i < frames.length; i++) {{
                        try {{
                            var doc = frames[i].contentDocument;
                            if (!doc) continue;
                            var items = doc.querySelectorAll('li');
                            if (items.length < 2) continue;
                            for (var j = 0; j < items.length; j++) {{
                                if (j === 0) {{
                                    items[j].style.background = 'linear-gradient(135deg, {c["primary"]}, {c["primary_dark"]})';
                                    items[j].style.color = '#000';
                                    items[j].style.fontWeight = '700';
                                    items[j].style.border = 'none';
                                }} else {{
                                    items[j].style.background = '{c["surface"]}';
                                    items[j].style.color = '{c["text"]}';
                                    items[j].style.fontWeight = '500';
                                    items[j].style.border = '1px solid {c["border"]}';
                                }}
                            }}
                            var parent = items[0].parentElement;
                            if (parent && !parent._obs) {{
                                parent._obs = true;
                                new MutationObserver(function() {{
                                    setTimeout(styleFirst, 50);
                                }}).observe(parent, {{childList: true, subtree: true}});
                            }}
                        }} catch(e) {{}}
                    }}
                }} catch(e) {{}}
            }}
            setTimeout(styleFirst, 300);
            setTimeout(styleFirst, 800);
            setTimeout(styleFirst, 1500);
        }})();
        </script>
        """, height=0)

        st.caption("Arraste para reordenar a fila")

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

    elif len(vendedores_ativos) == 1:
        vendedor = vendedores_ativos[0]
        st.markdown(
            f'<div style="display:inline-block;background:{c["primary"]};color:#000;'
            f'font-size:11px;font-weight:700;padding:2px 8px;border-radius:4px;'
            f'margin-bottom:8px;text-transform:uppercase;">PROXIMO</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div style="background:linear-gradient(135deg,{c["primary"]},{c["primary_dark"]});'
            f'color:#000;padding:10px 18px;border-radius:8px;font-weight:700;'
            f'font-size:14px;display:inline-block;">{vendedor["nome"]}</div>',
            unsafe_allow_html=True,
        )
        st.caption("Apenas 1 vendedor ativo.")
    else:
        st.warning("Nenhum vendedor ativo.")

    # Fechar div do container amber
    st.markdown("</div>", unsafe_allow_html=True)

# --- ATIVIDADES RECENTES ---
with col_atividades:
    with st.container(border=True):
        col_header, col_refresh = st.columns([5, 1])
        with col_header:
            st.markdown(f'<div style="font-size:18px;font-weight:600;color:{c["text"]};">Atividades Recentes</div>', unsafe_allow_html=True)
        with col_refresh:
            if st.button("&#128260;", key="refresh_atividades", help="Atualizar atividades"):
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
            for ativ in atividades:
                timestamp = pd.to_datetime(ativ["criado_em"])
                agora = pd.Timestamp.now(tz="America/Sao_Paulo")
                minutos = int((agora - timestamp).total_seconds() / 60)

                if minutos < 60:
                    tempo_str = f"ha {minutos} min"
                elif minutos < 1440:
                    tempo_str = f"ha {minutos // 60}h"
                else:
                    tempo_str = f"ha {minutos // 1440}d"

                icon = ICON_MAP.get(ativ.get("tipo", ""), "&#128196;")

                atividades_html.append(
                    f'<div style="display:flex;align-items:flex-start;padding:10px 0;'
                    f'border-bottom:1px solid {c["border"]};">'
                    f'<div style="color:{c["primary"]};font-size:14px;margin-right:10px;'
                    f'min-width:20px;text-align:center;">{icon}</div>'
                    f'<div style="flex:1;">'
                    f'<div style="color:{c["text_muted"]};font-size:13px;line-height:1.5;">'
                    f'{ativ["descricao"]}</div>'
                    f'<div style="color:{c["text_subtle"]};font-size:11px;margin-top:2px;">'
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
            <div id="atividades-container" style="max-height:360px;overflow-y:auto;padding-right:8px;">
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
            #atividades-container::-webkit-scrollbar-thumb:hover {{
                background: {c["scrollbar_thumb_hover"]};
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
                trigger.addEventListener('click', () => {{
                    const buttons = window.parent.document.querySelectorAll('button[kind="secondary"]');
                    const btn = Array.from(buttons).find(b => b.textContent.includes('Carregar mais'));
                    if (btn) btn.click();
                }});
            }}
            </script>
            """
            st.components.v1.html(html_code, height=400, scrolling=False)

            if st.session_state.atividades_has_more:
                st.markdown(
                    '<style>div[data-testid="column"] > div > button[kind="secondary"]'
                    "{position:absolute;opacity:0;pointer-events:none;height:0;width:0;overflow:hidden;}</style>",
                    unsafe_allow_html=True,
                )
                if st.button("Carregar mais atividades", key="carregar_mais_atividades_trigger", type="secondary"):
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

st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

# ============================================
# SECAO 3: ANALYTICS (grid, sem tabs)
# ============================================

st.markdown(f'<div style="color:{c["text"]};font-size:20px;font-weight:600;margin-bottom:16px;">Analises</div>', unsafe_allow_html=True)

# --- ROW 1: Tendencia + Funil ---
col_tendencia, col_funil = st.columns([1.4, 1], gap="medium")

plotly_defaults = get_plotly_layout_defaults()

with col_tendencia:
    with st.container(border=True):
        st.markdown(f'<div style="font-size:16px;font-weight:600;color:{c["text"]};margin-bottom:12px;">Tendencia de Leads</div>', unsafe_allow_html=True)

        leads_dia = get_leads_por_dia(loja["loja_id"], data_inicio=data_inicio, data_fim=data_fim)

        if leads_dia:
            df_dia = pd.DataFrame(leads_dia)
            df_dia["data"] = pd.to_datetime(df_dia["data"])

            fig = px.line(df_dia, x="data", y="total", markers=True, line_shape="spline")
            fig.update_layout(
                **plotly_defaults,
                showlegend=False,
                xaxis_title=None,
                yaxis_title="Leads",
                height=280,
                margin=dict(l=0, r=0, t=10, b=0),
            )
            fig.update_traces(line_color=c["primary"], marker=dict(size=7, color=c["primary"]))
            st.plotly_chart(fig, use_container_width=True)

            # Stats inline
            total_t = df_dia["total"].sum()
            media_t = df_dia["total"].mean()
            pico_row = df_dia.loc[df_dia["total"].idxmax()]
            pico_data = pico_row["data"].strftime("%d/%m")

            s1, s2, s3 = st.columns(3)
            with s1:
                st.metric("Total", total_t)
            with s2:
                st.metric("Media/dia", f"{media_t:.1f}")
            with s3:
                st.metric("Dia de Pico", f"{pico_data} ({int(pico_row['total'])})")
        else:
            st.info("Nenhum lead no periodo")

with col_funil:
    with st.container(border=True):
        st.markdown(f'<div style="font-size:16px;font-weight:600;color:{c["text"]};margin-bottom:12px;">Funil de Vendas</div>', unsafe_allow_html=True)

        metricas_funil = get_metricas_funil(loja["loja_id"], data_inicio=data_inicio, data_fim=data_fim)

        novo = metricas_funil["novo"]
        atendido = metricas_funil["atendido"]
        negociando = metricas_funil["negociando"]
        venda = metricas_funil["venda_concretizada"]
        desistiu = metricas_funil["desistiu"]

        taxa_atendimento = (atendido / novo * 100) if novo > 0 else 0
        taxa_negociacao = (negociando / atendido * 100) if atendido > 0 else 0
        taxa_venda = (venda / negociando * 100) if negociando > 0 else 0

        f1, f2, f3 = st.columns(3)
        with f1:
            st.metric("% Atendidos", f"{taxa_atendimento:.0f}%")
        with f2:
            st.metric("% Negociando", f"{taxa_negociacao:.0f}%")
        with f3:
            st.metric("% Vendas", f"{taxa_venda:.0f}%")

        if novo > 0:
            stages = ["Novo", "Atendido", "Negociando", "Venda"]
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
                height=250,
                margin=dict(l=0, r=0, t=10, b=0),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sem dados para funil")

# --- ROW 2: Origem + Hora ---
col_origem, col_hora = st.columns(2, gap="medium")

with col_origem:
    with st.container(border=True):
        st.markdown(f'<div style="font-size:16px;font-weight:600;color:{c["text"]};margin-bottom:12px;">Leads por Origem</div>', unsafe_allow_html=True)

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

            # Deltas vs periodo anterior
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
        st.markdown(f'<div style="font-size:16px;font-weight:600;color:{c["text"]};margin-bottom:12px;">Leads por Hora</div>', unsafe_allow_html=True)

        leads_hora = get_leads_por_hora(loja["loja_id"], data_inicio=data_inicio, data_fim=data_fim)

        if leads_hora:
            df_hora = pd.DataFrame(leads_hora)

            fig = px.bar(
                df_hora,
                x="hora_formatada",
                y="total",
                color="total",
                color_continuous_scale=[
                    [0, c["surface"]],
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
