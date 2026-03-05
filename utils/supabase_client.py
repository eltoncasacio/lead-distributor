"""
Cliente Supabase configurado para o app.
Suporta dev local (.env) e deploy (streamlit secrets).
"""
import os
from supabase import create_client, Client
import streamlit as st


def get_supabase_client() -> Client:
    """
    Retorna cliente Supabase configurado.
    Prioridade: streamlit secrets -> .env -> erro
    """
    url = None
    key = None

    # Tentar streamlit secrets (deploy)
    try:
        if hasattr(st, "secrets"):
            url = st.secrets.get("SUPABASE_URL")
            key = st.secrets.get("SUPABASE_SERVICE_KEY")
    except Exception:
        pass

    # Tentar .env (dev local)
    if not url or not key:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")

    if not url or not key:
        raise ValueError(
            "Credenciais Supabase não encontradas. "
            "Configure .env (dev local) ou .streamlit/secrets.toml (deploy).\n"
            "Veja SETUP.md para instruções."
        )

    return create_client(url, key)


# Singleton (cacheia o cliente)
@st.cache_resource
def get_cached_supabase_client() -> Client:
    """Cliente Supabase com cache (evita reconexões)."""
    return get_supabase_client()
