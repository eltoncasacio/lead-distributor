"""Fixtures dos testes. Nenhum teste fala com o Supabase real."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.fake_supabase import FakeSupabase  # noqa: E402

LOJA_A = "aaaaaaaa-0000-0000-0000-000000000001"
LOJA_B = "bbbbbbbb-0000-0000-0000-000000000002"

VEND_A = "11111111-0000-0000-0000-00000000000a"
VEND_B = "22222222-0000-0000-0000-00000000000b"
GER_A = "33333333-0000-0000-0000-00000000000a"
GER_B = "44444444-0000-0000-0000-00000000000b"


def _mundo():
    """Duas lojas, cada uma com um vendedor e um gerente."""
    return {
        "lojas": [
            {"id": LOJA_A, "nome": "Loja A", "ativa": True, "proximo_vendedor_id": VEND_A},
            {"id": LOJA_B, "nome": "Loja B", "ativa": True, "proximo_vendedor_id": VEND_B},
        ],
        "vendedores": [
            {"id": VEND_A, "loja_id": LOJA_A, "nome": "Ana",
             "numero_whatsapp": "5519900000001", "status": "ativo", "ordem_fila": 1},
            {"id": VEND_B, "loja_id": LOJA_B, "nome": "Bruno",
             "numero_whatsapp": "5519900000002", "status": "ativo", "ordem_fila": 1},
        ],
        "gerentes": [
            {"id": GER_A, "loja_id": LOJA_A, "nome": "Gerente A",
             "numero_whatsapp": "5519900000003", "ativo": True},
            {"id": GER_B, "loja_id": LOJA_B, "nome": "Gerente B",
             "numero_whatsapp": "5519900000004", "ativo": True},
        ],
        "atividades": [],
    }


@pytest.fixture
def fake(monkeypatch):
    """Substitui o cliente Supabase dentro de utils.queries por um falso."""
    import utils.queries as q

    cliente = FakeSupabase(_mundo())
    monkeypatch.setattr(q, "get_cached_supabase_client", lambda: cliente)
    return cliente


@pytest.fixture
def queries():
    import utils.queries as q
    return q
