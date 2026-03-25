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
            format="DD/MM/YYYY",
        )

    with col_fim:
        data_fim = st.date_input(
            "Data final:",
            value=date.today(),
            max_value=date.today(),
            key="data_fim_leads",
            format="DD/MM/YYYY",
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
            ["Todas", "iCarros", "NaPista", "Mobiauto", "Facebook", "OLX", "Mercado Livre", "WhatsApp Direto"],
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
negociando = len([l for l in leads_lista if l["status_lead"] == "negociando"])
sem_resposta = len([l for l in leads_lista if l["status_lead"] == "sem_resposta"])
sem_interesse = len([l for l in leads_lista if l["status_lead"] == "sem_interesse"])
vendido = len([l for l in leads_lista if l["status_lead"] == "vendido"])

# Tabs individuais por status
tab_todos, tab_negociando, tab_sem_resposta, tab_sem_interesse, tab_vendido = st.tabs(
    [
        f"Todos ({todos})",
        f"Negociando ({negociando})",
        f"Sem Resposta ({sem_resposta})",
        f"Sem Interesse ({sem_interesse})",
        f"Vendido ({vendido})",
    ]
)


def render_leads_table_filtrada(leads, tab_key="todos"):
    """
    Renderiza tabela de leads com coluna Status editavel.
    """
    if not leads:
        info_message("Nenhum lead encontrado")
        return

    df = pd.DataFrame(leads)
    df["recebido_em"] = pd.to_datetime(df["recebido_em"], format="ISO8601", utc=True)
    df["Data/Hora"] = df["recebido_em"].dt.tz_convert("America/Sao_Paulo").dt.strftime("%d/%m/%Y %H:%M")

    colunas = [
        "status_lead",
        "Data/Hora",
        "nome_cliente",
        "numero_cliente",
        "anuncio",
        "origem",
        "vendedor_nome",
    ]

    df_exibir = df[colunas].copy()

    nomes_colunas = [
        "Status",
        "Data/Hora",
        "Cliente",
        "Telefone",
        "Anuncio",
        "Origem",
        "Vendedor",
    ]

    df_exibir.columns = nomes_colunas

    # === INICIALIZAR SESSION STATE PARA AUTO-SAVE ===
    session_key = f"leads_ultimo_hash_{tab_key}_{hash(str(leads))}"

    if session_key not in st.session_state:
        st.session_state[session_key] = None

    if "leads_salvamento_em_progresso" not in st.session_state:
        st.session_state.leads_salvamento_em_progresso = False

    # === RENDERIZAR DATA EDITOR ===
    status_options = [
        "negociando",
        "sem_resposta",
        "sem_interesse",
        "vendido",
    ]

    editor_key = f"editor_leads_{tab_key}"

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

    if (
        hash_original != hash_editado
        and hash_editado != st.session_state[session_key]
        and not st.session_state.leads_salvamento_em_progresso
    ):
        st.session_state.leads_salvamento_em_progresso = True

        mudancas = 0
        supabase = get_cached_supabase_client()

        try:
            status_map = {
                "negociando": "Negociando",
                "sem_resposta": "Sem Resposta",
                "sem_interesse": "Sem Interesse",
                "vendido": "Vendido",
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

            st.session_state[session_key] = hash_editado

            if mudancas > 0:
                st.toast(f"✓ {mudancas} lead(s) atualizado(s)", icon="✅")
                time.sleep(0.3)

        except Exception as e:
            st.session_state[session_key] = hash_original
            st.toast(f"❌ Erro ao salvar: {str(e)}", icon="🚫")

        finally:
            st.session_state.leads_salvamento_em_progresso = False

        st.rerun()

    st.caption(f"Total: {len(leads)} leads")


with tab_todos:
    with st.container(border=True):
        st.markdown("#### Todos os Leads")
        render_leads_table_filtrada(leads_lista, tab_key="todos")

with tab_negociando:
    with st.container(border=True):
        st.markdown("#### Leads em Negociacao")
        leads_negociando = [l for l in leads_lista if l["status_lead"] == "negociando"]
        render_leads_table_filtrada(leads_negociando, tab_key="negociando")

with tab_sem_resposta:
    with st.container(border=True):
        st.markdown("#### Leads Sem Resposta")
        leads_sem_resposta = [l for l in leads_lista if l["status_lead"] == "sem_resposta"]
        render_leads_table_filtrada(leads_sem_resposta, tab_key="sem_resposta")

with tab_sem_interesse:
    with st.container(border=True):
        st.markdown("#### Leads Sem Interesse")
        leads_sem_interesse = [l for l in leads_lista if l["status_lead"] == "sem_interesse"]
        render_leads_table_filtrada(leads_sem_interesse, tab_key="sem_interesse")

with tab_vendido:
    with st.container(border=True):
        st.markdown("#### Vendas Concretizadas")
        leads_vendido = [l for l in leads_lista if l["status_lead"] == "vendido"]
        render_leads_table_filtrada(leads_vendido, tab_key="vendido")

# ============================================
# DICAS E INFORMACOES
# ============================================

st.divider()

with st.expander("Dicas de Uso"):
    st.markdown("""
    **Como usar esta pagina:**
    1. Use os **filtros** no topo para encontrar leads especificos
    2. Navegue pelas **tabs** para ver diferentes contextos:
       - **Todos**: Visao completa de todos os leads
       - **Negociando / Sem Resposta / Sem Interesse / Vendido**: Filtros por status
    3. Clique em uma celula da coluna **Status** para alterar em qualquer tab
    4. **Salvamento automatico**: Mudancas sao salvas instantaneamente

    **Status disponiveis:**
    - **Negociando**: Lead encaminhado ao vendedor, em negociacao
    - **Sem Resposta**: Cliente nao respondeu ao contato do vendedor
    - **Sem Interesse**: Cliente respondeu mas nao tem interesse
    - **Vendido**: Venda fechada com sucesso

    **Notas:**
    - Salvamento e instantaneo - sem necessidade de botao
    - Se houver erro (ex: sem internet), uma notificacao de erro aparecera
    - Atualize a pagina (F5) se quiser garantir dados mais recentes
    """)
