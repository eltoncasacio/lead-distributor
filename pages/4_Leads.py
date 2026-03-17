"""
Pagina de gerenciamento de leads com tabs, filtros e edicao inline de status.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import time
from utils.ui import (
    render_page_header,
    loading_spinner,
    success_message,
    info_message,
    inject_global_css,
)
from utils.auth import obter_loja_logada
from utils.queries import (
    get_leads_lista,
    listar_vendedores,
    registrar_atividade,
)
from utils.supabase_client import get_cached_supabase_client
from st_keyup import st_keyup

# Header compacto
render_page_header("Leads")

# CSS global
inject_global_css()

loja = obter_loja_logada()

# ============================================
# FILTROS COMPACTOS EM EXPANDER
# ============================================

with st.expander("Filtros", expanded=True):
    col_inicio, col_fim, col_vendedor, col_origem = st.columns(4)

    with col_inicio:
        data_inicio = st.date_input(
            "Data inicial:",
            value=date.today() - timedelta(days=30),
            max_value=date.today(),
            key="data_inicio_leads",
        )

    with col_fim:
        data_fim = st.date_input(
            "Data final:",
            value=date.today(),
            max_value=date.today(),
            key="data_fim_leads",
        )

    with col_vendedor:
        vendedores = listar_vendedores(loja["loja_id"], incluir_inativos=True)
        # Excluir vendedores removidos do filtro
        vendedores_visiveis = [v for v in vendedores if v["status"] != "removido"]
        vendedores_opcoes = ["Todos"] + [v["nome"] for v in vendedores_visiveis]
        filtro_vendedor = st.selectbox(
            "Vendedor:", vendedores_opcoes, key="filtro_vendedor"
        )

    with col_origem:
        filtro_origem = st.selectbox(
            "Origem:",
            ["Todas", "iCarros", "NaPista", "Mobiauto", "WhatsApp Direto"],
            key="filtro_origem",
        )

    busca_texto = st_keyup(
        "Buscar por nome, telefone ou anuncio:",
        key="busca_leads",
        placeholder="Digite para filtrar...",
        debounce=300,
    )

# Validação de datas
if data_inicio > data_fim:
    st.error("⚠️ Data inicial não pode ser maior que data final")
    st.stop()


# ============================================
# BUSCAR LEADS COM FILTROS
# ============================================

# Buscar vendedor_id se filtro ativo (apenas vendedores visiveis)
vendedor_id_filtro = None
if filtro_vendedor != "Todos":
    vendedor_selecionado = next(
        (v for v in vendedores_visiveis if v["nome"] == filtro_vendedor), None
    )
    if vendedor_selecionado:
        vendedor_id_filtro = vendedor_selecionado["id"]

# Buscar todos leads com filtros
with loading_spinner("Carregando leads..."):
    leads_lista = get_leads_lista(
        loja["loja_id"],
        data_inicio=data_inicio,
        data_fim=data_fim,
        vendedor_id=vendedor_id_filtro,
        origem=filtro_origem if filtro_origem != "Todas" else None,
    )

# Filtro por texto (nome, telefone ou anuncio)
if busca_texto:
    _termo = busca_texto.lower()
    leads_lista = [
        l for l in leads_lista
        if _termo in (l.get("nome_cliente") or "").lower()
        or _termo in (l.get("numero_cliente") or "").lower()
        or _termo in (l.get("anuncio") or "").lower()
    ]

# Indicador de período selecionado
duracao = (data_fim - data_inicio).days + 1
st.caption(
    f"**Período:** {data_inicio.strftime('%d/%m/%Y')} - "
    f"{data_fim.strftime('%d/%m/%Y')} ({duracao} dia{'s' if duracao != 1 else ''}) | "
    f"**Total:** {len(leads_lista)} lead{'s' if len(leads_lista) != 1 else ''} "
)

# ============================================
# TABS POR STATUS INDIVIDUAL
# ============================================

# Criar contadores para cada status
todos = len(leads_lista)
novos = len([l for l in leads_lista if l["status_lead"] == "novo"])
atendidos = len([l for l in leads_lista if l["status_lead"] == "atendido"])
negociando = len([l for l in leads_lista if l["status_lead"] == "negociando"])
desistiu = len([l for l in leads_lista if l["status_lead"] == "desistiu"])
vendas = len([l for l in leads_lista if l["status_lead"] == "venda_concretizada"])

# Tabs individuais por status
tab_todos, tab_novo, tab_atendido, tab_negociando, tab_desistiu, tab_venda = st.tabs(
    [
        f"Todos ({todos})",
        f"Novo ({novos})",
        f"Atendido ({atendidos})",
        f"Negociando ({negociando})",
        f"Desistiu ({desistiu})",
        f"Venda ({vendas})",
    ]
)


def render_leads_table_filtrada(leads, mostrar_coluna_status=True, editavel=True):
    """
    Renderiza tabela de leads com opcao de ocultar coluna Status.
    """
    if not leads:
        info_message("Nenhum lead encontrado")
        return

    df = pd.DataFrame(leads)
    df["recebido_em"] = pd.to_datetime(df["recebido_em"], format="ISO8601")
    df["Data/Hora"] = df["recebido_em"].dt.strftime("%d/%m/%Y %H:%M")

    # Colunas base (Status primeiro quando presente)
    if mostrar_coluna_status:
        colunas = [
            "status_lead",
            "Data/Hora",
            "nome_cliente",
            "numero_cliente",
            "anuncio",
            "origem",
            "vendedor_nome",
        ]
    else:
        colunas = [
            "Data/Hora",
            "nome_cliente",
            "numero_cliente",
            "anuncio",
            "origem",
            "vendedor_nome",
        ]

    df_exibir = df[colunas].copy()

    # Renomear colunas
    if mostrar_coluna_status:
        nomes_colunas = [
            "Status",
            "Data/Hora",
            "Cliente",
            "Telefone",
            "Anuncio",
            "Origem",
            "Vendedor",
        ]
    else:
        nomes_colunas = [
            "Data/Hora",
            "Cliente",
            "Telefone",
            "Anuncio",
            "Origem",
            "Vendedor",
        ]

    df_exibir.columns = nomes_colunas

    if editavel and mostrar_coluna_status:
        # === INICIALIZAR SESSION STATE PARA AUTO-SAVE ===
        # Key única por contexto de filtro para suportar múltiplas instâncias
        session_key = f"leads_ultimo_hash_{hash(str(leads))}"

        if session_key not in st.session_state:
            st.session_state[session_key] = None

        if "leads_salvamento_em_progresso" not in st.session_state:
            st.session_state.leads_salvamento_em_progresso = False

        # === RENDERIZAR DATA EDITOR ===
        status_options = [
            "novo",
            "atendido",
            "negociando",
            "desistiu",
            "venda_concretizada",
        ]

        # Key estável (não baseada em hash dos dados para manter estado do widget)
        editor_key = f"editor_leads_{mostrar_coluna_status}"

        edited_df = st.data_editor(
            df_exibir,
            column_config={
                "Status": st.column_config.SelectboxColumn(
                    "Status",
                    options=status_options,
                    required=True,
                ),
            },
            disabled=[c for c in nomes_colunas if c != "Status"],
            hide_index=True,
            use_container_width=True,
            key=editor_key,
        )

        # === DETECTAR MUDANÇAS E AUTO-SAVE ===
        hash_original = hash(str(df_exibir.to_dict()))
        hash_editado = hash(str(edited_df.to_dict()))

        # Condições para auto-save:
        # 1. Houve mudança REAL (hash diferente do original)
        # 2. Hash editado é diferente do último salvo (evitar re-save após rerun)
        # 3. Não estamos em meio a salvamento (prevenir loop infinito)
        if (
            hash_original != hash_editado
            and hash_editado != st.session_state[session_key]
            and not st.session_state.leads_salvamento_em_progresso
        ):
            # Marcar salvamento em progresso (previne concorrência)
            st.session_state.leads_salvamento_em_progresso = True

            # Contar mudanças para feedback
            mudancas = 0

            # Cliente Supabase
            supabase = get_cached_supabase_client()

            try:
                # Comparar row-by-row para salvar apenas o que mudou
                status_map = {
                    "novo": "Novo",
                    "atendido": "Atendido",
                    "negociando": "Negociando",
                    "desistiu": "Desistiu",
                    "venda_concretizada": "Venda Fechada",
                }

                for idx, row in edited_df.iterrows():
                    status_original = df_exibir.iloc[idx]["Status"]
                    status_novo = row["Status"]

                    if status_original != status_novo:
                        lead_id = leads[idx]["id"]
                        supabase.table("leads").update({"status_lead": status_novo}).eq(
                            "id", lead_id
                        ).execute()
                        mudancas += 1

                        # Registrar atividade
                        nome_cliente = leads[idx].get("nome_cliente", "N/A")
                        anuncio = leads[idx].get("anuncio", "WhatsApp Direto")
                        vendedor_nome = leads[idx].get("vendedor_nome", "N/A")
                        status_label = status_map.get(status_novo, status_novo)
                        descricao = (
                            f"Lead {nome_cliente} - {anuncio} - "
                            f"Status alterado para {status_label} "
                            f"(Vendedor {vendedor_nome})"
                        )
                        registrar_atividade(
                            loja["loja_id"],
                            "status_lead_alterado",
                            descricao,
                        )

                # Atualizar tracking APENAS após sucesso total
                st.session_state[session_key] = hash_editado

                # Feedback visual não-intrusivo
                if mudancas > 0:
                    st.toast(f"✓ {mudancas} lead(s) atualizado(s)", icon="✅")
                    time.sleep(0.3)  # Dar tempo para toast ser visto antes do rerun

            except Exception as e:
                # Rollback tracking em caso de erro
                st.session_state[session_key] = hash_original
                st.toast(f"❌ Erro ao salvar: {str(e)}", icon="🚫")

            finally:
                # SEMPRE resetar flag, mesmo em caso de erro
                st.session_state.leads_salvamento_em_progresso = False

            # Rerun para atualizar UI com dados frescos do banco
            st.rerun()

    else:
        # Modo somente leitura (tabs de status específico)
        st.dataframe(df_exibir, use_container_width=True, hide_index=True)

    st.caption(f"Total: {len(leads)} leads")


# Tab TODOS: Mostra coluna Status editavel
with tab_todos:
    with st.container(border=True):
        st.markdown("#### Todos os Leads")
        render_leads_table_filtrada(
            leads_lista, mostrar_coluna_status=True, editavel=True
        )

# Tabs por status: SEM coluna Status (redundante)
with tab_novo:
    with st.container(border=True):
        st.markdown("#### Leads Novos")
        leads_novos = [l for l in leads_lista if l["status_lead"] == "novo"]
        render_leads_table_filtrada(
            leads_novos, mostrar_coluna_status=False, editavel=False
        )

with tab_atendido:
    with st.container(border=True):
        st.markdown("#### Leads Atendidos")
        leads_atendidos = [l for l in leads_lista if l["status_lead"] == "atendido"]
        render_leads_table_filtrada(
            leads_atendidos, mostrar_coluna_status=False, editavel=False
        )

with tab_negociando:
    with st.container(border=True):
        st.markdown("#### Leads em Negociacao")
        leads_negociando = [l for l in leads_lista if l["status_lead"] == "negociando"]
        render_leads_table_filtrada(
            leads_negociando, mostrar_coluna_status=False, editavel=False
        )

with tab_desistiu:
    with st.container(border=True):
        st.markdown("#### Leads que Desistiram")
        leads_desistiu = [l for l in leads_lista if l["status_lead"] == "desistiu"]
        render_leads_table_filtrada(
            leads_desistiu, mostrar_coluna_status=False, editavel=False
        )

with tab_venda:
    with st.container(border=True):
        st.markdown("#### Vendas Concretizadas")
        leads_venda = [
            l for l in leads_lista if l["status_lead"] == "venda_concretizada"
        ]
        render_leads_table_filtrada(
            leads_venda, mostrar_coluna_status=False, editavel=False
        )

# ============================================
# DICAS E INFORMACOES
# ============================================

st.divider()

with st.expander("Dicas de Uso"):
    st.markdown("""
    **Como usar esta pagina:**
    1. Use os **filtros** no topo para encontrar leads especificos
    2. Navegue pelas **tabs** para ver diferentes contextos:
       - **Todos**: Visao completa de todos os leads (editavel)
       - **Novo / Atendido / Negociando / Desistiu / Venda**: Filtros por status (somente leitura)
    3. Na tab **Todos**, clique em uma celula da coluna **Status** para alterar
    4. **Salvamento automatico**: Mudancas sao salvas instantaneamente ✨
       - Uma notificacao aparecera confirmando o salvamento
       - Nao e necessario clicar em nenhum botao

    **Status disponiveis:**
    - **Novo**: Lead recem-chegado, ainda nao foi atendido
    - **Atendido**: Vendedor ja entrou em contato inicial
    - **Negociando**: Cliente demonstrou interesse, negociacao em andamento
    - **Desistiu**: Cliente nao tem mais interesse na compra
    - **Venda Concretizada**: Venda fechada com sucesso

    **Notas:**
    - Apenas a tab **Todos** permite edicao
    - Salvamento e instantaneo - sem necessidade de botao
    - Se houver erro (ex: sem internet), uma notificacao de erro aparecera
    - Atualize a pagina (F5) se quiser garantir dados mais recentes
    """)
