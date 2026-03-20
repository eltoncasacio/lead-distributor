"""
App shell: login + navegacao com st.navigation().
Dashboard e a pagina padrao apos login.
"""

import streamlit as st
from utils.auth import (
    validar_codigo,
    salvar_sessao,
    obter_loja_logada,
    esconder_sidebar_se_deslogado,
)
from utils.ui import inject_global_css, show_sidebar_info
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
        st.subheader("Sistema de Distribuição de Leads", text_alignment="center")
        st.markdown("# Login", text_alignment="center")

        with st.form("login_form"):
            codigo = st.text_input(
                "Codigo de Acesso",
                placeholder="Ex: AUT-20260304-X7Y2",
                help="Codigo único da sua loja",
            )
            submit = st.form_submit_button("Entrar", use_container_width=True)

            if submit:
                if not codigo:
                    st.error("Por favor, digite o código de acesso.")
                else:
                    with st.spinner("Validando código..."):
                        loja_data = validar_codigo(codigo)

                        if loja_data:
                            salvar_sessao(loja_data)
                            # Unreachable: salvar_sessao() chama st.stop()
                        else:
                            st.error("Código inválido ou loja inativa.")

        st.markdown("---")
        st.caption(
            "Sistema desenvolvido para gerenciamento de leads via WhatsApp",
            text_alignment="center",
        )

    st.stop()

# --- LOGADO: navegacao ---

# CSS para mini-sidebar (sidebar recolhida mostra so icones)
st.markdown(
    """
    <style>
    /* Sidebar expandida: mais estreita */
    section[data-testid="stSidebar"][aria-expanded="true"] {
        width: 14rem !important;
        min-width: 14rem !important;
        max-width: 14rem !important;
    }

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

    /* === Sidebar flex layout: header acima do nav, logout no fundo === */
    [data-testid="stSidebarContent"] {
        display: flex !important;
        flex-direction: column !important;
        height: 100% !important;
    }

    /* Mover header acima do nav (order -1 < nav order 0) */
    [data-testid="stSidebarContent"] > :has(#sidebar-header) {
        order: -1 !important;
    }

    /* Esconder header inteiro quando sidebar recolhida */
    section[data-testid="stSidebar"][aria-expanded="false"] #sidebar-header {
        display: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Header da sidebar: logo + nome da loja
with st.sidebar:
    nome_loja = loja["nome"].upper()
    st.markdown(
        f"""
        <div id="sidebar-header" style="padding: 0.75rem 0.5rem 1rem 0.5rem; text-align: center;">
            <div style="
                display: inline-flex;
                align-items: center;
                justify-content: center;
                width: 48px;
                height: 48px;
                background: #F1F5F9;
                border-radius: 12px;
                margin-bottom: 0.5rem;
            ">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none"
                     stroke="#64748B" stroke-width="1.8"
                     stroke-linecap="round" stroke-linejoin="round">
                    <path d="M5 17h2m10 0h2M2 9l2-6h16l2 6"/>
                    <path d="M2 9h20v5a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V9z"/>
                    <circle cx="7" cy="17" r="2"/>
                    <circle cx="17" cy="17" r="2"/>
                </svg>
            </div>
            <div style="
                font-family: 'Outfit', sans-serif;
                font-weight: 700;
                font-size: 0.95rem;
                color: #272B30;
                letter-spacing: 0.02em;
                line-height: 1.2;
            ">{nome_loja}</div>
            <div style="
                font-family: 'Inter', sans-serif;
                font-weight: 500;
                font-size: 0.65rem;
                color: #94A3B8;
                letter-spacing: 0.08em;
                margin-top: 2px;
            ">LEAD MANAGER</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Definir paginas (Dashboard = primeira = padrao)
pg = st.navigation(
    [
        st.Page(
            "pages/1_📊_Dashboard.py", title="Dashboard", icon=":material/dashboard:"
        ),
        st.Page("pages/4_Leads.py", title="Leads", icon=":material/leaderboard:"),
        st.Page(
            "pages/2_👨‍💼_Gerentes.py",
            title="Gerentes",
            icon=":material/supervisor_account:",
        ),
        st.Page(
            "pages/3_👤_Vendedores.py", title="Vendedores", icon=":material/group:"
        ),
    ]
)

# Sidebar: info da conta + botao Sair
show_sidebar_info()

# Executar pagina selecionada
pg.run()
