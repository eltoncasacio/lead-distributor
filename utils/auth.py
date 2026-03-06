"""
Sistema de autenticação baseado em código da loja.
Usa session_state + query_params para persistir login entre refreshes.
"""
import streamlit as st
from typing import Optional
from .supabase_client import get_cached_supabase_client


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
    Salva dados da loja no session_state e faz rerun.
    Nada após esta chamada será executado.

    Args:
        loja: dict com loja_id e nome
    """
    st.session_state["logged_in"] = True
    st.session_state["loja_id"] = loja["loja_id"]
    st.session_state["loja_nome"] = loja["nome"]
    st.query_params["s"] = loja["loja_id"]
    st.rerun()


def logout():
    """
    Limpa session_state e faz rerun.
    Nada após esta chamada será executado.
    """
    for key in ["logged_in", "loja_id", "loja_nome"]:
        if key in st.session_state:
            del st.session_state[key]
    st.query_params.clear()
    st.rerun()


def restaurar_sessao():
    """
    Restaura sessão a partir do query param ?s=<loja_id>.
    Valida se a loja existe e está ativa antes de restaurar.
    """
    if st.session_state.get("logged_in"):
        return

    sid = st.query_params.get("s")
    if not sid:
        return

    supabase = get_cached_supabase_client()
    response = (
        supabase.table("lojas")
        .select("id, nome")
        .eq("id", sid)
        .eq("ativa", True)
        .execute()
    )

    if response.data:
        loja = response.data[0]
        st.session_state["logged_in"] = True
        st.session_state["loja_id"] = loja["id"]
        st.session_state["loja_nome"] = loja["nome"]
    else:
        st.query_params.clear()


def obter_loja_logada() -> Optional[dict]:
    """
    Retorna dados da loja logada ou None.
    Restaura de query param se necessário.

    Returns:
        dict com loja_id e nome, ou None se não logado
    """
    restaurar_sessao()

    if not st.session_state.get("logged_in"):
        return None

    # Re-sync query param (st.navigation pode limpar entre renders)
    st.query_params["s"] = st.session_state["loja_id"]

    return {
        "loja_id": st.session_state.get("loja_id"),
        "nome": st.session_state.get("loja_nome"),
    }


def esconder_sidebar_se_deslogado():
    """
    Esconde o menu lateral se o usuário não estiver logado.
    Use isso no início de páginas públicas (como login).
    """
    restaurar_sessao()
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
    Guarda para páginas que requerem autenticação.
    Restaura sessão de query param e bloqueia se não logado.
    """
    restaurar_sessao()
    if not st.session_state.get("logged_in"):
        st.warning("Por favor, faça login para acessar esta página.")
        st.stop()
