"""
Sistema de autenticação baseado em código da loja.
Usa session_state + cookies para persistir login entre refreshes.
"""
import streamlit as st
import streamlit.components.v1 as components
from typing import Optional
from .supabase_client import get_cached_supabase_client


def _get_cookie(name: str) -> Optional[str]:
    """Lê um cookie server-side via st.context.cookies."""
    return st.context.cookies.get(name)


def validar_codigo(codigo: str) -> Optional[dict]:
    """
    Valida código de acesso e retorna dados da loja.

    Args:
        codigo: Código de acesso (ex: AUT-20260304-X7Y2)

    Returns:
        dict com loja_id e nome, ou None se inválido
    """
    supabase = get_cached_supabase_client()

    # Buscar código no banco
    response = (
        supabase.table("loja_acesso")
        .select("loja_id, lojas(id, nome, ativa)")
        .eq("codigo_acesso", codigo.strip())
        .execute()
    )

    if not response.data:
        return None

    acesso = response.data[0]
    loja = acesso["lojas"]

    # Verificar se loja está ativa
    if not loja or not loja.get("ativa"):
        return None

    # Atualizar último acesso
    supabase.table("loja_acesso").update(
        {"ultimo_acesso_em": "now()"}
    ).eq("loja_id", loja["id"]).execute()

    return {
        "loja_id": loja["id"],
        "nome": loja["nome"],
    }


def salvar_sessao(loja: dict):
    """
    Salva dados da loja no session_state + cookies.
    Chama st.stop() internamente — nada após esta chamada será executado.

    Args:
        loja: dict com loja_id e nome
    """
    max_age = 30 * 24 * 60 * 60  # 30 dias
    loja_id = loja["loja_id"]
    loja_nome = loja["nome"]

    # Session state (para o run atual, antes do reload)
    st.session_state["logged_in"] = True
    st.session_state["loja_id"] = loja_id
    st.session_state["loja_nome"] = loja_nome

    # Cookie (persistente) + reload via JS
    js = f"""
    <script>
    document.cookie = "loja_id={loja_id}; path=/; max-age={max_age}; SameSite=Strict";
    document.cookie = "loja_nome={loja_nome}; path=/; max-age={max_age}; SameSite=Strict";
    window.parent.location.reload();
    </script>
    """
    components.html(js, height=0)
    st.stop()


def logout():
    """
    Limpa session_state e cookies.
    Chama st.stop() internamente — nada após esta chamada será executado.
    """
    # Limpar session state
    for key in ["logged_in", "loja_id", "loja_nome"]:
        if key in st.session_state:
            del st.session_state[key]

    # Limpar cookies + reload via JS
    js = """
    <script>
    document.cookie = "loja_id=; path=/; max-age=0; SameSite=Strict";
    document.cookie = "loja_nome=; path=/; max-age=0; SameSite=Strict";
    window.parent.location.reload();
    </script>
    """
    components.html(js, height=0)
    st.stop()


def restaurar_sessao_de_cookie():
    """
    Tenta restaurar sessão a partir de cookies.
    Chama isso no início de cada página.
    """
    # Se já está logado no session_state, não precisa restaurar
    if st.session_state.get("logged_in"):
        return

    # Tentar ler cookies
    loja_id = _get_cookie("loja_id")
    loja_nome = _get_cookie("loja_nome")

    if loja_id and loja_nome:
        # Restaurar sessão
        st.session_state["logged_in"] = True
        st.session_state["loja_id"] = loja_id
        st.session_state["loja_nome"] = loja_nome


def obter_loja_logada() -> Optional[dict]:
    """
    Retorna dados da loja logada ou None.
    Restaura de cookie se necessário.

    Returns:
        dict com loja_id e nome, ou None se não logado
    """
    # Tentar restaurar de cookie primeiro
    restaurar_sessao_de_cookie()

    if not st.session_state.get("logged_in"):
        return None

    return {
        "loja_id": st.session_state.get("loja_id"),
        "nome": st.session_state.get("loja_nome"),
    }


def esconder_sidebar_se_deslogado():
    """
    Esconde o menu lateral se o usuário não estiver logado.
    Use isso no início de páginas públicas (como login).
    """
    restaurar_sessao_de_cookie()
    if not st.session_state.get("logged_in"):
        st.markdown(
            """
            <style>
                [data-testid="stSidebar"] {
                    display: none;
                }
            </style>
            """,
            unsafe_allow_html=True
        )


def require_login():
    """
    Decorator para páginas que requerem autenticação.
    Redireciona para login se não estiver logado.
    """
    if not st.session_state.get("logged_in"):
        st.warning("Por favor, faça login para acessar esta página.")
        st.stop()
