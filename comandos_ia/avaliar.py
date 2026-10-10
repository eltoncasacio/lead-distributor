#!/usr/bin/env python3
"""Avalia o interpretador de comandos contra frases de teste, chamando a API de verdade.

  python3 comandos_ia/avaliar.py                                    prompt.PROVEDOR / prompt.MODELO
  python3 comandos_ia/avaliar.py --modelo anthropic/claude-opus-5.5
  python3 comandos_ia/avaliar.py --provedor anthropic --modelo claude-haiku-5-5

Requer OPENROUTER_API_KEY (ou ANTHROPIC_API_KEY, com --provedor anthropic) no .env.
Cada rodada custa dinheiro (centavos) — o custo medido sai no fim.

Usa HTTP puro, e nao o SDK, de proposito: o que esta sob teste e o corpo exato
que o no HTTP do n8n envia (prompt.corpo_requisicao).

Acerto = a acao (e o nome, quando importa) que o Postgres de fato usaria depois
das MESMAS travas de executar_comando_ia e igual ao esperado. Classificacao do
erro:
  ~   seguro    — caiu no texto original ou pediu esclarecimento: nada errado acontece
  XX  perigoso  — outra acao ou outro vendedor: bloqueia subir
"""
import json, pathlib, re, sys, time, unicodedata, urllib.error, urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import prompt as P

RAIZ = pathlib.Path(__file__).resolve().parents[1]
ENV = dict(l.split("=", 1) for l in (RAIZ / ".env").read_text().splitlines() if "=" in l and not l.startswith("#"))
PROVEDOR = sys.argv[sys.argv.index("--provedor") + 1] if "--provedor" in sys.argv else P.PROVEDOR
VAR = {"openrouter": "OPENROUTER_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}[PROVEDOR]
CHAVE = ENV.get(VAR, "").strip()
if not CHAVE: sys.exit(f"{VAR} nao esta no .env")
MODELO = sys.argv[sys.argv.index("--modelo") + 1] if "--modelo" in sys.argv else P.MODELO

VENDEDORES = ["Giu", "Japa", "Diego", "André"]
PRECO = {"claude-opus-5-5": (4.0, 20.0), "claude-haiku-5-5": (0.10, 0.50),
         "anthropic/claude-opus-5.5": (4.0, 20.0), "anthropic/claude-haiku-5.5": (0.10, 0.50)}

# (papel, mensagem, esperado). esperado = (acao, nome) ou um conjunto de
# alternativas aceitaveis. acao "original" = deve cair no texto original
# (nenhum, ou sugestao barrada). nome None = nao importa.
CASOS = [
    ("gerente", "menu", ("menu", None)),
    ("gerente", "o que eu posso fazer aqui?", ("menu", None)),
    ("gerente", "listar vendedores", ("listar_vendedores", None)),
    ("gerente", "lsitar vendedores", ("listar_vendedores", None)),
    ("gerente", "me mostra a equipe", ("listar_vendedores", None)),
    # palavra solta = ver aquilo (execucao 9238, 10/10: "Vendedores" virou pergunta)
    ("gerente", "Vendedores", ("listar_vendedores", None)),
    ("gerente", "equipe", ("listar_vendedores", None)),
    ("gerente", "fila", ("listar_vendedores", None)),
    ("gerente", "resumo", ("status", None)),
    ("vendedor", "leads", ("meus_leads", None)),
    # do teste real da Maria (10/10)
    ("gerente", "Adiciona vendedor ton 19999746219", ("inserir", "ton")),
    ("gerente", "Quantas lojas existem?", ("original", None)),
    ("gerente", "quem ta recebendo lead?", ("listar_vendedores", None)),
    ("gerente", "status", ("status", None)),
    ("gerente", "como tá a loja hoje", ("status", None)),
    ("gerente", "statsu", ("status", None)),
    ("gerente", "leads", ("leads", None)),
    ("gerente", "quais leads chegaram?", ("leads", None)),
    ("gerente", "pausa a giu", ("pausar", "Giu")),
    ("gerente", "tira a giu da fila hoje que ela tá de folga", ("pausar", "Giu")),
    ("gerente", "pausar giuu", ("pausar", "Giu")),
    ("gerente", "o japinha vai sair mais cedo, para de mandar lead pra ele", ("pausar", "Japa")),
    ("gerente", "volta o andre", ("reativar", "André")),
    ("gerente", "despausa o André", ("reativar", "André")),
    ("gerente", "a Giu voltou, pode mandar lead pra ela", ("reativar", "Giu")),
    ("gerente", "o diego saiu da empresa, remove ele", ("excluir", "Diego")),
    ("gerente", "exclui o diego", ("excluir", "Diego")),
    ("gerente", "cadastra o Marcos 19 98123-4567", ("inserir", "Marcos")),
    ("gerente", "novo vendedor: Paula Souza, (19) 99888-7766", ("inserir", "Paula Souza")),
    ("gerente", "sim", ("sim", None)),
    ("gerente", "pode", ("sim", None)),
    ("gerente", "isso mesmo, manda ver", ("sim", None)),
    ("gerente", "confirma", ("sim", None)),
    ("gerente", "não", ("nao", None)),
    ("gerente", "cancela isso", ("nao", None)),
    ("gerente", "bom dia", ("original", None)),
    ("gerente", "obrigado!", ("original", None)),
    ("gerente", "qual o preço do onix prata?", ("original", None)),
    ("vendedor", "meus leads", ("meus_leads", None)),
    ("vendedor", "tem lead novo pra mim?", ("meus_leads", None)),
    ("vendedor", "como eu tô?", ("status", None)),
    ("vendedor", "pausa a giu", ("original", None)),
    ("vendedor", "valeu", ("original", None)),
    # ambiguos: o certo e perguntar (ou, no minimo, nao executar outra coisa)
    ("gerente", "tira ele da fila", {("esclarecer", None)}),
    ("gerente", "mexe na giu", {("esclarecer", None)}),
    ("gerente", "a giu", {("esclarecer", None), ("original", None)}),
    ("gerente", "tira a giu", {("esclarecer", None), ("pausar", "Giu")}),
    ("gerente", "remove o joão", {("esclarecer", None), ("excluir", "João")}),
    # sem telefone o banco responde "e preciso o telefone": inserir e a leitura certa
    ("gerente", "coloca o Pedro na fila", {("esclarecer", None), ("original", None), ("inserir", "Pedro")}),
    # pausar x excluir: excluir so quando for explicitamente definitivo
    ("gerente", "a giu entrou de férias", {("pausar", "Giu"), ("esclarecer", None)}),
    ("gerente", "demiti o japa", {("excluir", "Japa")}),
    ("gerente", "o andré não trabalha mais aqui", {("excluir", "André")}),
    ("gerente", "para de mandar lead pro diego", {("pausar", "Diego")}),
    ("gerente", "Paulo 19 98888-1111", {("esclarecer", None), ("inserir", "Paulo")}),
    ("gerente", "pausa a giu e o diego", {("esclarecer", None), ("pausar", "Giu")}),
]

dig = lambda s: re.sub(r"\D", "", s or "")
norm = lambda s: " ".join(unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower().split())


def travas(texto, sug):
    """Espelho de executar_comando_ia: (acao efetiva, nome, motivo)."""
    if not sug: return "original", "", "sem_sugestao"
    a, nome, tel = sug["acao"], sug["nome"], dig(sug["telefone"])
    if a == "nenhum": return "original", "", "nenhum"
    if tel and tel not in dig(texto) and tel not in "55" + dig(texto): return "original", "", "telefone_inventado"
    if a == "inserir" and (not nome or norm(nome) not in norm(texto)): return "original", "", "nome_inventado"
    if a == "esclarecer" and not sug["pergunta"]: return "original", "", "esclarecer_sem_pergunta"
    return a, nome, "sugestao_usada" if a != "esclarecer" else "esclarecer"


def chamar(texto, papel):
    corpo = P.corpo_requisicao(texto, papel, VENDEDORES, MODELO, PROVEDOR)
    req = urllib.request.Request(P.URL[PROVEDOR], data=json.dumps(corpo).encode(), headers=P.headers(CHAVE, MODELO, PROVEDOR))
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60) as r: resp = json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode()[:600]}")
    return resp, time.time() - t0


def bate(a, nome, esperado):
    alts = esperado if isinstance(esperado, set) else {esperado}
    return any(a == ea and (en is None or norm(nome) == norm(en)) for ea, en in alts)


def main():
    print(f"provedor: {PROVEDOR} | modelo: {MODELO} | esforco: {P.ESFORCO} | {len(CASOS)} frases\n")
    ok = seguro = perigoso = 0; tin = tout = 0; lat = []; custo_real = []
    for papel, texto, esperado in CASOS:
        resp, dt = chamar(texto, papel); lat.append(dt)
        u = resp.get("usage", {})
        tin += u.get("input_tokens", u.get("prompt_tokens", 0)); tout += u.get("output_tokens", u.get("completion_tokens", 0))
        if u.get("cost") is not None: custo_real.append(float(u["cost"]))
        sug = P.extrair_comando(resp, PROVEDOR)
        a, nome, motivo = travas(texto, sug)
        if bate(a, nome, esperado):
            ok += 1; marca = "ok "
        elif a in ("original", "esclarecer"):
            seguro += 1; marca = "~  "
        else:
            perigoso += 1; marca = "XX "
        mostra = f"{a} {nome}".strip() + (f" — {sug['pergunta']!r}" if sug and a == "esclarecer" else "")
        print(f"{marca} [{papel[:3]}] {texto!r:50} -> {mostra:45} ({motivo}, {dt:.1f}s)"
              + ("" if marca == "ok " else f"   esperado {esperado}"))
    pin, pout = PRECO.get(MODELO, (0, 0))
    custo = sum(custo_real) if custo_real else (tin * pin + tout * pout) / 1e6
    print(f"\nacertos: {ok}/{len(CASOS)} | erro seguro: {seguro} | ERRO PERIGOSO: {perigoso}")
    print(f"tokens: {tin} entrada, {tout} saida | custo da rodada: US$ {custo:.4f} (~US$ {custo/len(CASOS):.5f} por mensagem)"
          + (" [custo real informado pelo OpenRouter]" if custo_real else " [estimado pela tabela de precos]"))
    print(f"latencia: media {sum(lat)/len(lat):.1f}s, pior {max(lat):.1f}s")


if __name__ == "__main__":
    main()
