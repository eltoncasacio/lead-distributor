"""Isolamento multi-loja em utils/queries.py.

Por que estes testes existem: o isolamento entre lojas nao e garantido pelo
banco. O RLS esta habilitado mas nega tudo para `anon`, e o sistema acessa com
a `service_role`, que passa por cima. **A unica defesa e o codigo lembrar de
filtrar por `loja_id`** — ver docs/specs/regras-de-negocio/04.

Em 2026-09-23 uma revisao achou 5 funcoes que nao filtravam. Com uma loja so,
nao havia o que vazar; com duas, a loja A editaria dado da loja B. Estes testes
existem para que isso nao volte.

Os testes sobem um mundo com DUAS lojas e tentam, de proposito, mexer na loja
errada. Nenhum teste fala com o Supabase real.
"""
import ast
import io
import os

import pytest

from tests.conftest import GER_A, GER_B, LOJA_A, LOJA_B, VEND_A, VEND_B


# ---------------------------------------------------------------- vendedores

def test_editar_vendedor_nao_alcanca_outra_loja(fake, queries):
    """Loja A tentando editar o vendedor da loja B nao pode surtir efeito."""
    queries.editar_vendedor(LOJA_A, VEND_B, "Invadido", "5519999999999")

    bruno = next(v for v in fake.dados["vendedores"] if v["id"] == VEND_B)
    assert bruno["nome"] == "Bruno", "vendedor da loja B foi alterado pela loja A"
    assert bruno["numero_whatsapp"] == "5519900000002"


def test_editar_vendedor_funciona_na_propria_loja(fake, queries):
    """E o caminho feliz precisa continuar funcionando."""
    queries.editar_vendedor(LOJA_A, VEND_A, "Ana Maria", "5519911111111")

    ana = next(v for v in fake.dados["vendedores"] if v["id"] == VEND_A)
    assert ana["nome"] == "Ana Maria"
    assert ana["numero_whatsapp"] == "5519911111111"


def test_alterar_status_vendedor_nao_alcanca_outra_loja(fake, queries):
    queries.alterar_status_vendedor(LOJA_A, VEND_B, "removido")

    bruno = next(v for v in fake.dados["vendedores"] if v["id"] == VEND_B)
    assert bruno["status"] == "ativo", "loja A removeu vendedor da loja B"


def test_alterar_status_vendedor_funciona_na_propria_loja(fake, queries):
    queries.alterar_status_vendedor(LOJA_A, VEND_A, "inativo")

    ana = next(v for v in fake.dados["vendedores"] if v["id"] == VEND_A)
    assert ana["status"] == "inativo"


# ------------------------------------------------------------------ gerentes

def test_editar_gerente_nao_alcanca_outra_loja(fake, queries):
    queries.editar_gerente(GER_B, "Invadido", "5519999999999", LOJA_A)

    g = next(x for x in fake.dados["gerentes"] if x["id"] == GER_B)
    assert g["nome"] == "Gerente B"


def test_deletar_gerente_nao_alcanca_outra_loja(fake, queries):
    """O pior caso: DELETE de verdade, sem soft-delete."""
    queries.deletar_gerente(GER_B, LOJA_A)

    ids = [x["id"] for x in fake.dados["gerentes"]]
    assert GER_B in ids, "loja A apagou o gerente da loja B"


def test_deletar_gerente_funciona_na_propria_loja(fake, queries):
    queries.deletar_gerente(GER_A, LOJA_A)

    ids = [x["id"] for x in fake.dados["gerentes"]]
    assert GER_A not in ids
    assert GER_B in ids


def test_desativar_gerente_nao_alcanca_outra_loja(fake, queries):
    queries.desativar_gerente(GER_B, LOJA_A)

    g = next(x for x in fake.dados["gerentes"] if x["id"] == GER_B)
    assert g["ativo"] is True


# ------------------------------------------------- toda escrita leva o filtro

ESCRITAS_ESPERADAS = [
    ("editar_vendedor", lambda q: q.editar_vendedor(LOJA_A, VEND_A, "x", "5519900000009")),
    ("alterar_status_vendedor", lambda q: q.alterar_status_vendedor(LOJA_A, VEND_A, "ativo")),
    ("editar_gerente", lambda q: q.editar_gerente(GER_A, "x", "5519900000009", LOJA_A)),
    ("desativar_gerente", lambda q: q.desativar_gerente(GER_A, LOJA_A)),
    ("deletar_gerente", lambda q: q.deletar_gerente(GER_A, LOJA_A)),
]


@pytest.mark.parametrize("nome,chamar", ESCRITAS_ESPERADAS, ids=[n for n, _ in ESCRITAS_ESPERADAS])
def test_toda_escrita_carrega_filtro_de_loja(fake, queries, nome, chamar):
    """Nao basta o resultado estar certo: o filtro tem que estar na consulta.

    Sem isto, uma funcao poderia passar nos testes acima por sorte do dado
    falso e ainda assim mandar um UPDATE sem `loja_id` para o banco real.
    """
    chamar(queries)

    escritas = [c for c in fake.escritas() if c.tabela in ("vendedores", "gerentes")]
    assert escritas, "%s nao executou nenhuma escrita" % nome

    for c in escritas:
        colunas = [col for _, col, _ in c.filtros]
        assert "loja_id" in colunas, (
            "%s fez %s em `%s` sem filtro de loja_id (filtros: %s)"
            % (nome, c.operacao, c.tabela, colunas)
        )


# --------------------------------------------------- trava contra regressao

TABELAS_POR_LOJA = {
    "vendedores", "gerentes", "leads", "atividades",
    "mensagens_prontas", "mensagens_recebidas",
}

# Filtram a tabela `lojas` pela propria PK, ou validam posse explicitamente.
# Conferidas uma a uma em 2026-09-23.
ISENTAS = {
    "atualizar_proximo_vendedor_da_loja",
    "reordenar_vendedores",
    "obter_proximo_vendedor",
    "get_limite_leads",
}


def _funcoes_suspeitas():
    caminho = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "utils", "queries.py",
    )
    src = io.open(caminho, encoding="utf-8").read()
    linhas = src.splitlines()
    achados = []

    for no in ast.parse(src).body:
        if not isinstance(no, ast.FunctionDef) or no.name in ISENTAS:
            continue
        corpo = "\n".join(linhas[no.lineno - 1:no.end_lineno])

        mexe = any('.table("%s")' % t in corpo for t in TABELAS_POR_LOJA)
        if not mexe:
            continue

        amarra = (
            '.eq("loja_id"' in corpo
            or "p_loja_id" in corpo
            or '"loja_id":' in corpo
            or '"loja_id" :' in corpo
        )
        opt_in = "if loja_id:" in corpo or "loja_id: str = None" in corpo

        if not amarra or opt_in:
            achados.append((no.name, no.lineno,
                            "filtro opt-in" if opt_in else "sem filtro de loja_id"))
    return achados


def test_nenhuma_funcao_nova_sem_amarra_de_loja():
    """Varre utils/queries.py inteiro procurando a proxima regressao.

    Se voce adicionou uma funcao e este teste quebrou: ou falta
    `.eq("loja_id", loja_id)`, ou o filtro esta dentro de um `if` (a guarda
    precisa ser incondicional — `loja_id` nunca e parametro opcional).
    """
    achados = _funcoes_suspeitas()
    assert not achados, "funcoes sem amarra de loja_id:\n" + "\n".join(
        "  linha %d  %s — %s" % (ln, nome, motivo) for nome, ln, motivo in achados
    )
