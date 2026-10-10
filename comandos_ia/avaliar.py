#!/usr/bin/env python3
"""Avalia o tradutor de comandos contra frases de teste, chamando a API de verdade.

  python3 comandos_ia/avaliar.py                                    prompt.PROVEDOR / prompt.MODELO
  python3 comandos_ia/avaliar.py --modelo anthropic/claude-haiku-5.5
  python3 comandos_ia/avaliar.py --provedor anthropic --modelo claude-haiku-5-5

Requer OPENROUTER_API_KEY (ou ANTHROPIC_API_KEY, com --provedor anthropic) no .env. Cada rodada custa dinheiro (poucos
centavos: ~40 frases curtas) — o custo medido sai no fim.

Usa HTTP puro, e nao o SDK, de proposito: o que esta sob teste e o corpo exato
que o no HTTP do n8n envia (prompt.corpo_requisicao), byte a byte.

O que conta como acerto: a sugestao da IA, depois das MESMAS travas do
Postgres (executar_comando_ia), e igual ao esperado. Erro "seguro" (a IA nao
entendeu e devolveu vazio, entao vale o texto original) e contado a parte do
erro "perigoso" (comando diferente do pedido) — so o segundo bloqueia subir.
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
# Precos por 1M tokens (entrada, saida), da referencia da API em 2026-10.
PRECO = {"claude-opus-5-5": (4.0, 20.0), "claude-haiku-5-5": (0.10, 0.50), "claude-sonnet-5-5": (2.0, 10.0),
         "anthropic/claude-opus-5.5": (4.0, 20.0), "anthropic/claude-haiku-5.5": (0.10, 0.50),
         "anthropic/claude-sonnet-5.5": (2.0, 10.0)}

# (papel, mensagem, esperado). Esperado "" = nao e comando.
CASOS = [
    ("gerente", "menu", "menu"),
    ("gerente", "o que eu posso fazer aqui?", "menu"),
    ("gerente", "listar vendedores", "listar vendedores"),
    ("gerente", "lsitar vendedores", "listar vendedores"),
    ("gerente", "me mostra a equipe", "listar vendedores"),
    ("gerente", "quem ta recebendo lead?", "listar vendedores"),
    ("gerente", "status", "status"),
    ("gerente", "como tá a loja hoje", "status"),
    ("gerente", "statsu", "status"),
    ("gerente", "leads", "leads"),
    ("gerente", "quais leads chegaram?", "leads"),
    ("gerente", "pausa a giu", "pausar Giu"),
    ("gerente", "tira a giu da fila hoje que ela tá de folga", "pausar Giu"),
    ("gerente", "pausar giuu", "pausar Giu"),
    ("gerente", "o japinha vai sair mais cedo, para de mandar lead pra ele", "pausar Japa"),
    ("gerente", "volta o andre", "reativar André"),
    ("gerente", "despausa o André", "reativar André"),
    ("gerente", "a Giu voltou, pode mandar lead pra ela", "reativar Giu"),
    ("gerente", "o diego saiu da empresa, remove ele", "excluir vendedor Diego"),
    ("gerente", "exclui o diego", "excluir vendedor Diego"),
    ("gerente", "cadastra o Marcos 19 98123-4567", "inserir vendedor Marcos 19 98123-4567"),
    ("gerente", "novo vendedor: Paula Souza, (19) 99888-7766", "inserir vendedor Paula Souza 19 99888-7766"),
    ("gerente", "coloca o Pedro na fila", "inserir vendedor Pedro"),
    ("gerente", "sim", "sim"),
    ("gerente", "pode", "sim"),
    ("gerente", "isso mesmo, manda ver", "sim"),
    ("gerente", "confirma", "sim"),
    ("gerente", "não", "nao"),
    ("gerente", "cancela isso", "nao"),
    ("gerente", "bom dia", ""),
    ("gerente", "obrigado!", ""),
    ("gerente", "qual o preço do onix prata?", ""),
    ("vendedor", "meus leads", "meus leads"),
    ("vendedor", "tem lead novo pra mim?", "meus leads"),
    ("vendedor", "como eu tô?", "status"),
    ("vendedor", "pausa a giu", ""),
    ("vendedor", "valeu", ""),
]

VERBOS = {"menu", "ajuda", "status", "leads", "meus", "listar", "inserir", "pausar", "despausar", "reativar", "excluir", "sim", "nao"}
dig = lambda s: re.sub(r"\D", "", s or "")
norm = lambda s: " ".join(unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower().split())


def travas(texto, sug):
    """Espelho de executar_comando_ia: o que o Postgres de fato executaria."""
    if not sug: return texto, "sem_sugestao"
    if norm(sug).split(" ")[0] not in VERBOS: return texto, "verbo_desconhecido"
    if dig(sug) and dig(sug) not in dig(texto) and dig(sug) not in "55" + dig(texto): return texto, "telefone_inventado"
    return sug, "sugestao_usada"


def chamar(texto, papel):
    corpo = P.corpo_requisicao(texto, papel, VENDEDORES, MODELO, PROVEDOR)
    req = urllib.request.Request(P.URL[PROVEDOR], data=json.dumps(corpo).encode(), headers=P.headers(CHAVE, MODELO, PROVEDOR))
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60) as r: resp = json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode()[:600]}")
    return resp, time.time() - t0


CUSTO_REAL = []


def main():
    print(f"provedor: {PROVEDOR} | modelo: {MODELO} | esforco: {P.ESFORCO} | {len(CASOS)} frases\n")
    ok = seguro = perigoso = 0; tin = tout = 0; lat = []
    for papel, texto, esperado in CASOS:
        resp, dt = chamar(texto, papel); lat.append(dt)
        u = resp.get("usage", {})
        tin += u.get("input_tokens", u.get("prompt_tokens", 0)); tout += u.get("output_tokens", u.get("completion_tokens", 0))
        custo_or = u.get("cost")   # OpenRouter devolve o custo real da chamada
        if custo_or is not None: CUSTO_REAL.append(float(custo_or))
        sug = P.extrair_comando(resp, PROVEDOR)
        final, motivo = travas(texto, sug)
        alvo = esperado if esperado else texto   # sem comando: deve cair no texto original
        if norm(final) == norm(alvo) or (dig(final) and norm(re.sub(r"[\d()\- ]+$", "", final)) == norm(re.sub(r"[\d()\- ]+$", "", alvo)) and dig(final)[-8:] == dig(alvo)[-8:]):
            ok += 1; marca = "ok "
        elif final == texto:
            seguro += 1; marca = "~  "   # IA nao ajudou, mas nada errado acontece
        else:
            perigoso += 1; marca = "XX "
        print(f"{marca} [{papel[:3]}] {texto!r:55} -> {str(sug)!r:40} ({motivo}, {dt:.1f}s)" + ("" if marca == "ok " else f"   esperado {esperado!r}"))
    pin, pout = PRECO.get(MODELO, (0, 0))
    custo = (tin * pin + tout * pout) / 1e6
    print(f"\nacertos: {ok}/{len(CASOS)} | erro seguro (cai no texto original): {seguro} | ERRO PERIGOSO: {perigoso}")
    if CUSTO_REAL: custo = sum(CUSTO_REAL)
    print(f"tokens: {tin} entrada, {tout} saida | custo da rodada: US$ {custo:.4f} (~US$ {custo/len(CASOS):.5f} por mensagem)"
          + (" [custo real informado pelo OpenRouter]" if CUSTO_REAL else " [estimado pela tabela de precos]"))
    print(f"latencia: media {sum(lat)/len(lat):.1f}s, pior {max(lat):.1f}s")


if __name__ == "__main__":
    main()
