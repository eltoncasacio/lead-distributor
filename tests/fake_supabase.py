"""Supabase falso para testes — grava o que foi pedido, nao fala com a rede.

Imita a cadeia do supabase-py (`.table().update().eq().eq().execute()`) guardando
cada chamada, para os testes conseguirem afirmar coisas como "este UPDATE levou
filtro de loja_id junto".

Tambem guarda linhas falsas por tabela, para `.select()` devolver algo
plausivel. O filtro aplicado em `.eq()` e de verdade: se o teste pedir uma linha
de outra loja, a consulta devolve vazio — que e exatamente o comportamento que
queremos provar.
"""
from typing import Any, Dict, List, Optional


class Resposta:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count


class Consulta:
    """Uma consulta em construcao. Registra a operacao e os filtros."""

    def __init__(self, fake: "FakeSupabase", tabela: str):
        self.fake = fake
        self.tabela = tabela
        self.operacao: Optional[str] = None
        self.payload: Any = None
        self.filtros: List[tuple] = []
        self.colunas: Optional[str] = None
        self._ordem = None
        self._limite = None

    # --- operacoes ---
    def select(self, colunas="*", **kw):
        self.operacao = "select"
        self.colunas = colunas
        return self

    def update(self, payload):
        self.operacao = "update"
        self.payload = payload
        return self

    def insert(self, payload):
        self.operacao = "insert"
        self.payload = payload
        return self

    def delete(self):
        self.operacao = "delete"
        return self

    # --- filtros e modificadores ---
    def eq(self, coluna, valor):
        self.filtros.append(("eq", coluna, valor))
        return self

    def is_(self, coluna, valor):
        self.filtros.append(("is", coluna, valor))
        return self

    def neq(self, coluna, valor):
        self.filtros.append(("neq", coluna, valor))
        return self

    def gte(self, coluna, valor):
        self.filtros.append(("gte", coluna, valor))
        return self

    def lte(self, coluna, valor):
        self.filtros.append(("lte", coluna, valor))
        return self

    def order(self, coluna, desc=False):
        self._ordem = (coluna, desc)
        return self

    def limit(self, n):
        self._limite = n
        return self

    def range(self, ini, fim):
        self._limite = fim - ini + 1
        return self

    # --- execucao ---
    def _casa(self, linha) -> bool:
        for tipo, col, val in self.filtros:
            if tipo == "eq" and linha.get(col) != val:
                return False
            if tipo == "is" and val == "null" and linha.get(col) is not None:
                return False
            if tipo == "neq" and linha.get(col) == val:
                return False
        return True

    def execute(self):
        self.fake.chamadas.append(self)
        linhas = self.fake.dados.get(self.tabela, [])
        casadas = [l for l in linhas if self._casa(l)]

        if self.operacao == "select":
            if self._limite:
                casadas = casadas[: self._limite]
            return Resposta(list(casadas), count=len(casadas))

        if self.operacao == "update":
            for l in casadas:
                l.update(self.payload)
            return Resposta(list(casadas))

        if self.operacao == "delete":
            self.fake.dados[self.tabela] = [
                l for l in linhas if not self._casa(l)
            ]
            return Resposta(list(casadas))

        if self.operacao == "insert":
            novas = self.payload if isinstance(self.payload, list) else [self.payload]
            self.fake.dados.setdefault(self.tabela, []).extend(novas)
            return Resposta(list(novas))

        return Resposta([])


class FakeSupabase:
    def __init__(self, dados: Optional[Dict[str, List[dict]]] = None):
        self.dados = dados or {}
        self.chamadas: List[Consulta] = []
        self.rpcs: List[tuple] = []

    def table(self, nome):
        return Consulta(self, nome)

    def rpc(self, nome, params=None):
        self.rpcs.append((nome, params or {}))
        return Resposta([{}])

    # --- ajudantes para os testes ---
    def escritas(self, tabela=None):
        """Chamadas que modificaram dados."""
        return [
            c for c in self.chamadas
            if c.operacao in ("update", "insert", "delete")
            and (tabela is None or c.tabela == tabela)
        ]

    def filtrou_por(self, consulta: Consulta, coluna: str) -> bool:
        return any(col == coluna for _, col, _ in consulta.filtros)
