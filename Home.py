"""
App shell: login + navegacao com st.navigation().
Dashboard e a pagina padrao apos login.
"""
import streamlit as st
from utils.auth import validar_codigo, salvar_sessao, obter_loja_logada, esconder_sidebar_se_deslogado
from utils.ui import inject_global_css
from dotenv import load_dotenv

# Carregar .env (dev local)
load_dotenv()

# Configuracao da pagina (unica chamada no app inteiro)
st.set_page_config(
    page_title="Sistema de Leads",
    page_icon=":busts_in_silhouette:",
    layout="wide",
)

# CSS global
inject_global_css()

# Verificar login
loja = obter_loja_logada()

if not loja:
    # --- DESLOGADO: formulario de login ---
    esconder_sidebar_se_deslogado()

    # Centralizar formulario
    _, col_center, _ = st.columns([1, 2, 1])
    with col_center:
        st.title("Sistema de Distribuicao de Leads")
        st.markdown("### Login")

        with st.form("login_form"):
            codigo = st.text_input(
                "Codigo de Acesso",
                placeholder="Ex: AUT-20260304-X7Y2",
                help="Codigo unico da sua loja",
            )
            submit = st.form_submit_button("Entrar", use_container_width=True)

            if submit:
                if not codigo:
                    st.error("Por favor, digite o codigo de acesso.")
                else:
                    with st.spinner("Validando codigo..."):
                        loja_data = validar_codigo(codigo)

                        if loja_data:
                            salvar_sessao(loja_data)
                            # Unreachable: salvar_sessao() chama st.stop()
                        else:
                            st.error("Codigo invalido ou loja inativa.")

        st.markdown("---")
        st.caption("Sistema desenvolvido para gerenciamento de leads via WhatsApp")

    st.stop()

# --- LOGADO: navegacao ---

# CSS para mini-sidebar (sidebar recolhida mostra so icones)
st.markdown(
    """
    <style>
    /* Sidebar recolhida: versao estreita em vez de esconder */
    section[data-testid="stSidebar"][aria-expanded="false"] {
        width: 4.5rem !important;
        min-width: 4.5rem !important;
        max-width: 4.5rem !important;
        transform: none !important;
    }

    /* Conteudo interno: cortar texto que excede a largura */
    section[data-testid="stSidebar"][aria-expanded="false"] > div {
        overflow: hidden !important;
    }

    /* Ajustar margem do conteudo principal */
    section[data-testid="stSidebar"][aria-expanded="false"] ~ section[data-testid="stMain"] {
        margin-left: 4.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Definir paginas (Dashboard = primeira = padrao)
pg = st.navigation([
    st.Page("pages/1_📊_Dashboard.py", title="Dashboard", icon=":material/dashboard:"),
    st.Page("pages/2_👨‍💼_Gerentes.py", title="Gerentes", icon=":material/supervisor_account:"),
    st.Page("pages/3_👤_Vendedores.py", title="Vendedores", icon=":material/group:"),
    st.Page("pages/4_Leads.py", title="Leads", icon=":material/leaderboard:"),
])

# Executar pagina selecionada
pg.run()
