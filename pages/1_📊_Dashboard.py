"""
Dashboard com layout profissional: metricas em grid, containers com borda, tabs.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
from streamlit_sortables import sort_items
from utils.ui import render_page_header, loading_spinner, error_message, inject_global_css, SORTABLE_CUSTOM_STYLE
from utils.auth import obter_loja_logada
from utils.queries import (
    get_metricas_hoje,
    get_leads_por_dia,
    get_leads_por_hora,
    get_leads_por_origem_comparativo,
    listar_vendedores,
    obter_proximo_vendedor,
    get_atividades_recentes,
    reordenar_vendedores,
)

# Header compacto
render_page_header("Dashboard")

# CSS global
inject_global_css()

loja = obter_loja_logada()

# ============================================
# SECAO 1: NORTH STAR METRICS
# ============================================

with loading_spinner("Carregando metricas..."):
    metricas = get_metricas_hoje(loja["loja_id"])
    vendedores = listar_vendedores(loja["loja_id"])
    proximo = obter_proximo_vendedor(loja["loja_id"])

col1, col2, col3, col4 = st.columns([1, 1, 2, 1], gap="medium")

with col1:
    st.metric(
        label="Leads Hoje",
        value=metricas["total_leads"],
        help="Total de leads recebidos hoje (metrica principal)"
    )

with col2:
    ultimo = metricas["ultimo_lead"] if metricas["ultimo_lead"] else "—"
    st.metric(
        label="Ultimo Lead",
        value=ultimo,
        help="Horario do ultimo lead recebido"
    )

with col3:
    proximo_nome = proximo["nome"] if proximo else "Nenhum"
    st.metric(
        label="Proximo Vendedor",
        value=proximo_nome,
        help="Vendedor que recebera o proximo lead"
    )

with col4:
    vendedores_ativos = [v for v in vendedores if v["status"] == "ativo"]
    st.metric(
        label="Vendedores Ativos",
        value=len(vendedores_ativos),
        help="Total de vendedores na fila de distribuicao"
    )

st.divider()

# ============================================
# SECAO 2: FILA DE DISTRIBUICAO
# ============================================

with st.container(border=True):
    st.subheader("Fila de Distribuicao")

    vendedores_ativos = [v for v in vendedores if v["status"] == "ativo"]

    if len(vendedores_ativos) > 1:
        # Ordenar por ordem_fila atual
        vendedores_ativos_sorted = sorted(vendedores_ativos, key=lambda x: x["ordem_fila"])

        # Ordem ORIGINAL para deteccao de mudanca
        ordem_original_ids = [v['id'] for v in vendedores_ativos_sorted]
        if "ordem_original_dashboard" not in st.session_state:
            st.session_state.ordem_original_dashboard = ordem_original_ids

        # --- Visual da fila com setas ---
        queue_parts = []
        for i, v in enumerate(vendedores_ativos_sorted):
            if i > 0:
                queue_parts.append(
                    '<span style="color:#4b5563;font-size:16px;margin:0 6px;">→</span>'
                )
            if i == 0:
                # Primeiro: dourado, recebe proximo lead
                queue_parts.append(
                    f'<span style="background:linear-gradient(135deg,#d4a853,#b8922e);'
                    f'color:#111318;padding:8px 16px;border-radius:8px;font-weight:700;'
                    f'font-size:14px;display:inline-block;white-space:nowrap;">'
                    f'{v["nome"]}</span>'
                )
            else:
                queue_parts.append(
                    f'<span style="background:#1a1d24;border:1px solid #272b33;color:#9ca3af;'
                    f'padding:8px 16px;border-radius:8px;font-weight:400;'
                    f'font-size:14px;display:inline-block;white-space:nowrap;">'
                    f'{v["nome"]}</span>'
                )

        indicator = (
            '<span style="color:#d4a853;font-size:20px;margin-right:8px;'
            'display:inline-flex;align-items:center;">→</span>'
        )
        queue_html = (
            f'<div style="display:flex;align-items:center;flex-wrap:wrap;'
            f'gap:4px;margin:12px 0 4px 0;">'
            f'{indicator}{"".join(queue_parts)}</div>'
            f'<div style="color:#6b7280;font-size:12px;margin-left:32px;'
            f'margin-top:4px;">próximo lead</div>'
        )
        st.markdown(queue_html, unsafe_allow_html=True)

        st.markdown("#####")

        # --- Drag-drop para reordenar ---
        with st.expander("Reordenar fila"):
            nomes = [v['nome'] for v in vendedores_ativos_sorted]

            nova_ordem_nomes = sort_items(
                nomes,
                multi_containers=False,
                direction="vertical",
                key="reorder_vendedores_dashboard",
                custom_style=SORTABLE_CUSTOM_STYLE
            )

            # Mapear nomes para IDs
            nova_ordem_ids = []
            for nome in nova_ordem_nomes:
                vendedor = next((v for v in vendedores_ativos_sorted if v["nome"] == nome), None)
                if vendedor:
                    nova_ordem_ids.append(vendedor["id"])

            # Detectar mudanca REAL
            ordem_mudou = nova_ordem_ids != st.session_state.ordem_original_dashboard

            # Auto-save quando ordem mudar
            if ordem_mudou and len(nova_ordem_ids) == len(vendedores_ativos):
                try:
                    reordenar_vendedores(loja["loja_id"], nova_ordem_ids)
                    st.session_state.ordem_original_dashboard = nova_ordem_ids
                    st.rerun()
                except Exception as e:
                    error_message(f"Erro ao salvar: {str(e)}")

    elif len(vendedores_ativos) == 1:
        vendedor = vendedores_ativos[0]
        indicator = (
            '<span style="color:#d4a853;font-size:20px;margin-right:8px;">→</span>'
            f'<span style="background:linear-gradient(135deg,#d4a853,#b8922e);'
            f'color:#111318;padding:8px 16px;border-radius:8px;font-weight:700;'
            f'font-size:14px;display:inline-block;">{vendedor["nome"]}</span>'
        )
        st.markdown(
            f'<div style="display:flex;align-items:center;margin:12px 0;">{indicator}</div>'
            f'<div style="color:#6b7280;font-size:12px;margin-left:32px;">proximo lead</div>',
            unsafe_allow_html=True
        )
        st.caption("Apenas 1 vendedor ativo.")
    else:
        st.warning("Nenhum vendedor ativo.")

# ============================================
# SECAO 3: ATIVIDADES RECENTES (SCROLL INFINITO)
# ============================================

with st.container(border=True):
    # Header com botão de refresh
    col_header, col_refresh = st.columns([5, 1])
    with col_header:
        st.subheader("Atividades Recentes")
    with col_refresh:
        if st.button("🔄", key="refresh_atividades", help="Atualizar atividades"):
            st.session_state.atividades_todas = []
            st.session_state.atividades_has_more = True
            st.session_state.atividades_loaded = False
            st.rerun()

    # Inicializar state para scroll infinito
    if "atividades_todas" not in st.session_state:
        st.session_state.atividades_todas = []
    if "atividades_has_more" not in st.session_state:
        st.session_state.atividades_has_more = True
    if "atividades_loaded" not in st.session_state:
        st.session_state.atividades_loaded = False

    # Carregar primeira leva de atividades
    BATCH_SIZE = 20
    if not st.session_state.atividades_loaded:
        st.session_state.atividades_todas = get_atividades_recentes(
            loja["loja_id"],
            limite=BATCH_SIZE,
            offset=0
        )
        st.session_state.atividades_has_more = len(st.session_state.atividades_todas) == BATCH_SIZE
        st.session_state.atividades_loaded = True

    atividades = st.session_state.atividades_todas

    if atividades:
        # Gerar HTML das atividades
        atividades_html = []
        for i, ativ in enumerate(atividades):
            timestamp = pd.to_datetime(ativ["timestamp"])
            agora = pd.Timestamp.now(tz='America/Sao_Paulo')

            # Tempo relativo
            tempo_delta = agora - timestamp
            minutos = int(tempo_delta.total_seconds() / 60)

            if minutos < 60:
                tempo_str = f"ha {minutos} min"
            elif minutos < 1440:
                tempo_str = f"ha {minutos // 60}h"
            else:
                tempo_str = f"ha {minutos // 1440}d"

            # Status legivel
            status_map = {
                "novo": "Novo",
                "atendido": "Atendido",
                "negociando": "Negociando",
                "desistiu": "Desistiu",
                "venda_concretizada": "Venda Fechada"
            }
            status_texto = status_map.get(ativ["status_lead"], ativ["status_lead"])

            # HTML da atividade
            if ativ["tipo"] == "novo_lead":
                texto = f"<strong>{ativ['nome_cliente']}</strong> → {ativ['vendedor_nome']} ({tempo_str})"
            else:
                texto = f"<strong>{ativ['nome_cliente']}</strong> mudou para <strong>{status_texto}</strong> ({tempo_str})"

            atividades_html.append(
                f'<div class="atividade-item">{texto}</div>'
            )

        # Adicionar indicador "Carregar mais" se houver mais dados
        if st.session_state.atividades_has_more:
            atividades_html.append(
                '<div id="load-more-trigger" class="load-more-btn">Carregar mais atividades ↓</div>'
            )

        # Componente HTML com scroll
        html_code = f"""
        <div id="atividades-container" style="max-height: 400px; overflow-y: auto; padding-right: 8px;">
            {''.join(atividades_html)}
        </div>

        <style>
        #atividades-container {{
            scrollbar-width: thin;
            scrollbar-color: #4b5563 #1a1d24;
        }}
        #atividades-container::-webkit-scrollbar {{
            width: 6px;
        }}
        #atividades-container::-webkit-scrollbar-track {{
            background: #1a1d24;
            border-radius: 3px;
        }}
        #atividades-container::-webkit-scrollbar-thumb {{
            background: #4b5563;
            border-radius: 3px;
        }}
        #atividades-container::-webkit-scrollbar-thumb:hover {{
            background: #6b7280;
        }}
        .atividade-item {{
            padding: 10px 0;
            color: #9ca3af;
            font-size: 14px;
            border-bottom: 1px solid #1a1d24;
            line-height: 1.5;
        }}
        .atividade-item:last-of-type {{
            border-bottom: none;
        }}
        .load-more-btn {{
            padding: 12px;
            text-align: center;
            color: #d4a853;
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            border-top: 1px solid #272b33;
            margin-top: 8px;
            transition: background-color 0.2s;
        }}
        .load-more-btn:hover {{
            background-color: #1a1d24;
        }}
        </style>

        <script>
        // Detectar scroll no final e clicar automaticamente no trigger
        const container = document.getElementById('atividades-container');
        const trigger = document.getElementById('load-more-trigger');

        if (container && trigger) {{
            // Intersection Observer para detectar quando trigger fica visível
            const observer = new IntersectionObserver((entries) => {{
                entries.forEach(entry => {{
                    if (entry.isIntersecting) {{
                        // Simular clique no botão "Carregar mais" do Streamlit
                        const buttons = window.parent.document.querySelectorAll('button[kind="secondary"]');
                        const loadMoreBtn = Array.from(buttons).find(btn =>
                            btn.textContent.includes('Carregar mais atividades')
                        );
                        if (loadMoreBtn) {{
                            loadMoreBtn.click();
                        }}
                    }}
                }});
            }}, {{
                root: container,
                threshold: 0.1
            }});

            observer.observe(trigger);

            // Click manual no trigger também funciona
            trigger.addEventListener('click', () => {{
                const buttons = window.parent.document.querySelectorAll('button[kind="secondary"]');
                const loadMoreBtn = Array.from(buttons).find(btn =>
                    btn.textContent.includes('Carregar mais atividades')
                );
                if (loadMoreBtn) {{
                    loadMoreBtn.click();
                }}
            }});
        }}
        </script>
        """

        # Renderizar componente
        st.components.v1.html(html_code, height=450, scrolling=False)

        # Botão invisível para trigger de scroll (acionado via JavaScript)
        if st.session_state.atividades_has_more:
            # CSS para ocultar o botão
            st.markdown(
                """
                <style>
                button[kind="secondary"]:has-text("Carregar mais atividades") {
                    display: none !important;
                }
                /* Fallback: ocultar por posição se seletor :has-text não funcionar */
                div[data-testid="column"] > div > button[kind="secondary"] {
                    position: absolute;
                    opacity: 0;
                    pointer-events: none;
                    height: 0;
                    width: 0;
                    overflow: hidden;
                }
                </style>
                """,
                unsafe_allow_html=True
            )

            if st.button(
                "Carregar mais atividades",
                key="carregar_mais_atividades_trigger",
                type="secondary",
            ):
                # Carregar próximo batch
                novo_offset = len(st.session_state.atividades_todas)
                novas_atividades = get_atividades_recentes(
                    loja["loja_id"],
                    limite=BATCH_SIZE,
                    offset=novo_offset
                )

                if novas_atividades:
                    st.session_state.atividades_todas.extend(novas_atividades)
                    st.session_state.atividades_has_more = len(novas_atividades) == BATCH_SIZE
                else:
                    st.session_state.atividades_has_more = False

                st.rerun()

        # Info sobre total carregado
        total_str = f"Mostrando {len(atividades)} atividades"
        if st.session_state.atividades_has_more:
            total_str += " (role para carregar mais)"
        st.caption(total_str)
    else:
        st.info("Nenhuma atividade hoje")

st.divider()

# ============================================
# SECAO 4: ANALISES (Tabs)
# ============================================

st.markdown("### Analises")

tab1, tab2, tab3 = st.tabs(["Tendencia", "Por Origem", "Por Hora"])

with tab1:
    st.markdown("#### Tendencia de Leads")

    # Filtros de data customizados
    col_inicio, col_fim = st.columns(2)
    with col_inicio:
        data_inicio = st.date_input(
            "Data inicial",
            value=date.today() - timedelta(days=30),
            max_value=date.today(),
            key="data_inicio_tendencia"
        )
    with col_fim:
        data_fim = st.date_input(
            "Data final",
            value=date.today(),
            max_value=date.today(),
            key="data_fim_tendencia"
        )

    # Validação
    if data_inicio > data_fim:
        st.error("Data inicial não pode ser maior que data final")
        st.stop()

    leads_dia = get_leads_por_dia(loja["loja_id"], data_inicio=data_inicio, data_fim=data_fim)

    if leads_dia:
        df_dia = pd.DataFrame(leads_dia)
        df_dia["data"] = pd.to_datetime(df_dia["data"])

        fig = px.line(
            df_dia,
            x="data",
            y="total",
            markers=True,
            line_shape="spline"
        )
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            xaxis_title=None,
            yaxis_title="Leads",
            height=350,
            margin=dict(l=0, r=0, t=20, b=0)
        )
        fig.update_traces(line_color="#d4a853", marker=dict(size=8, color="#d4a853"))
        st.plotly_chart(fig, use_container_width=True)

        # Estatisticas
        total_periodo = df_dia["total"].sum()
        media_dia = df_dia["total"].mean()
        st.caption(f"**Total:** {total_periodo} leads | **Media/dia:** {media_dia:.1f}")
    else:
        st.info("Nenhum lead no periodo")

with tab2:
    st.markdown("#### Leads por Origem")

    # Filtros de data customizados
    col_inicio, col_fim = st.columns(2)
    with col_inicio:
        data_inicio_origem = st.date_input(
            "Data inicial",
            value=date.today() - timedelta(days=30),
            max_value=date.today(),
            key="data_inicio_origem"
        )
    with col_fim:
        data_fim_origem = st.date_input(
            "Data final",
            value=date.today(),
            max_value=date.today(),
            key="data_fim_origem"
        )

    # Validação
    if data_inicio_origem > data_fim_origem:
        st.error("Data inicial não pode ser maior que data final")
        st.stop()

    # Indicador de período anterior
    duracao = (data_fim_origem - data_inicio_origem).days
    periodo_anterior_inicio = data_inicio_origem - timedelta(days=duracao)
    periodo_anterior_fim = data_inicio_origem - timedelta(days=1)
    st.caption(
        f"**Período atual:** {data_inicio_origem.strftime('%d/%m/%Y')} - "
        f"{data_fim_origem.strftime('%d/%m/%Y')} ({duracao + 1} dias) | "
        f"**Período anterior:** {periodo_anterior_inicio.strftime('%d/%m/%Y')} - "
        f"{periodo_anterior_fim.strftime('%d/%m/%Y')}"
    )

    dados_origem = get_leads_por_origem_comparativo(loja["loja_id"], data_inicio=data_inicio_origem, data_fim=data_fim_origem)
    atual = dados_origem["atual"]
    anterior = dados_origem["anterior"]
    total = sum(atual.values())

    if total > 0:
        # Cores fixas por origem
        cores_origem = {
            "WhatsApp Direto": "#d4a853",
            "NaPista": "#6b7280",
            "iCarros": "#4a90a4",
        }

        # Ordenar por quantidade (maior primeiro)
        origens_ordenadas = sorted(atual.keys(), key=lambda o: atual[o], reverse=True)

        col_donut, col_metricas = st.columns([2, 1], gap="large")

        with col_donut:
            labels = origens_ordenadas
            values = [atual[o] for o in origens_ordenadas]
            colors = [cores_origem.get(o, "#9ca3af") for o in origens_ordenadas]

            fig = go.Figure(data=[go.Pie(
                labels=labels,
                values=values,
                hole=0.5,
                marker=dict(colors=colors),
                textposition="inside",
                textinfo="percent+label",
                hovertemplate="%{label}<br>%{value} leads<br>%{percent}<extra></extra>",
            )])

            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
                height=350,
                margin=dict(l=0, r=0, t=20, b=0),
                annotations=[
                    dict(
                        text=f"<b>{total}</b><br><span style='font-size:12px'>Leads<br>Totais</span>",
                        x=0.5, y=0.5,
                        font=dict(size=24, color="white"),
                        showarrow=False,
                    )
                ],
            )
            st.plotly_chart(fig, use_container_width=True)

        with col_metricas:
            for origem in origens_ordenadas:
                qtd_atual = atual[origem]
                qtd_anterior = anterior.get(origem, 0)
                delta = qtd_atual - qtd_anterior
                share = (qtd_atual / total) * 100

                st.metric(
                    label=origem,
                    value=qtd_atual,
                    delta=delta,
                    delta_color="normal",
                    help=f"{share:.0f}% do total de leads no periodo",
                )
    else:
        st.info("Sem dados no periodo")

with tab3:
    st.markdown("#### Horarios de Maior Volume")

    # Filtros de data customizados
    col_inicio, col_fim = st.columns(2)
    with col_inicio:
        data_inicio_hora = st.date_input(
            "Data inicial",
            value=date.today() - timedelta(days=30),
            max_value=date.today(),
            key="data_inicio_hora"
        )
    with col_fim:
        data_fim_hora = st.date_input(
            "Data final",
            value=date.today(),
            max_value=date.today(),
            key="data_fim_hora"
        )

    # Validação
    if data_inicio_hora > data_fim_hora:
        st.error("Data inicial não pode ser maior que data final")
        st.stop()

    leads_hora = get_leads_por_hora(loja["loja_id"], data_inicio=data_inicio_hora, data_fim=data_fim_hora)

    if leads_hora:
        df_hora = pd.DataFrame(leads_hora)

        fig = px.bar(
            df_hora,
            x="hora_formatada",
            y="total",
            color="total",
            color_continuous_scale=[[0, "#272b33"], [0.5, "#d4a853"], [1, "#f5d78e"]],
            text="total"
        )
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            xaxis_title="Hora do Dia",
            yaxis_title="Total de Leads",
            height=350,
            margin=dict(l=0, r=0, t=20, b=0),
            xaxis=dict(tickangle=-45, tickmode="linear")
        )
        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True)

        # Estatisticas
        hora_pico = df_hora.loc[df_hora["total"].idxmax()]
        st.caption(f"**Horario de Pico:** {hora_pico['hora_formatada']} com {int(hora_pico['total'])} leads")
    else:
        st.info("Sem dados no periodo")

# Footer
st.divider()
st.caption("**Dica:** Use os filtros de periodo para ajustar as analises. Acesse 'Leads' para gerenciar status.")
