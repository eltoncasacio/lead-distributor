#!/usr/bin/env python3
"""Portaria v3 — avalia o prompt contra a amostra rotulada pelo dono.

  python3 portaria/avaliar.py --modelo nvidia/nemotron-3-super-120b-a12b:free     (gratuito, texto MASCARADO)
  python3 portaria/avaliar.py                                                    (prompt.MODELO, producao)

Requer OPENROUTER_API_KEY no .env e portaria/amostra_para_rotular.csv com
ROTULO_HUMANO preenchido (lead / nao_lead / duvida). O CSV tem mensagens
REAIS de clientes e esta no .gitignore.

Modelo `:free` -> nomes, telefones, e-mails e links sao MASCARADOS antes de
sair da maquina (provedores gratuitos podem guardar o texto). Modelo pago ->
texto como em producao.

PORTAO (spec 07): zero mensagens rotuladas `lead` ou `duvida` que acabem
ignoradas (nao_lead depois das travas). E o unico erro caro. O que nao passa
no portao nao sobe.
"""
import csv, json, pathlib, re, sys, time, urllib.error, urllib.request

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
from portaria import prompt as P

RAIZ = AQUI.parent
ENV = dict(l.split("=", 1) for l in (RAIZ / ".env").read_text().splitlines() if "=" in l and not l.startswith("#"))
CHAVE = ENV.get("OPENROUTER_API_KEY", "").strip()
if not CHAVE: sys.exit("OPENROUTER_API_KEY nao esta no .env")
MODELO = sys.argv[sys.argv.index("--modelo") + 1] if "--modelo" in sys.argv else P.MODELO
GRATIS = MODELO.endswith(":free")
LIMITE = int(sys.argv[sys.argv.index("--limite") + 1]) if "--limite" in sys.argv else None


# Palavras que aparecem no nome do perfil mas nao sao dado pessoal (empresa,
# plataforma, a propria loja) — mascarar escondia a pista de "fornecedor".
NAO_E_NOME = {"webmotors", "claro", "renato", "motors", "pesquisa", "olx", "icarros", "napista",
              "mobiauto", "info", "verifica", "banco", "loja", "time", "suporte", "comercial"}
GATILHO = r"(?i)(me chamo|meu nome é|meu nome e|aqui é o|aqui é a|aqui e o|aqui e a|prazer,?|cliente:)"


def mascarar(texto: str, nome: str) -> str:
    """Tira dado pessoal antes de mandar para modelo gratuito. Prefere mascarar a mais."""
    t = re.sub(r"https?://\S+|www\.\S+", "<LINK>", texto)
    t = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "<EMAIL>", t)
    t = re.sub(r"\d[\d\s().-]{6,}\d", "<NUMERO>", t)
    # aviso de portal: "Cliente: Fulano de Tal Mensagem: ..."
    t = re.sub(r"(?i)(cliente:)\s*.*?\s+(mensagem:)", r"\1 <NOME> \2", t)
    # nome depois de gatilho, ate pontuacao ou palavra de ligacao (ate 6 palavras, qualquer caixa)
    t = re.sub(GATILHO + r"\s+((?:(?!estava\b|e\b|eu\b|da\b|do\b|que\b)[\wÀ-ú]+\s*){1,6}?)(?=[,.!?]|\s+(?:estava|e|eu|da|do|que|mensagem:)\b|$)",
               lambda m: m.group(1) + " <NOME>", t)
    # "Fulano De Tal, seu contrato..." (nome no comeco seguido de virgula)
    t = re.sub(r"^((?:[A-ZÀ-Ú][\wÀ-ú]+\s+){1,5}[A-ZÀ-Ú]?[\wÀ-ú]+),", "<NOME>,", t)
    for parte in sorted({p for p in re.split(r"\s+", nome or "") if len(p) >= 3 and p.lower() not in NAO_E_NOME},
                        key=len, reverse=True):
        t = re.sub(r"\b" + re.escape(parte) + r"\b", "<NOME>", t, flags=re.I)
    return t


def chamar(texto):
    corpo = P.corpo_requisicao(texto, MODELO, com_esforco=not GRATIS)
    for tentativa in range(6):
        req = urllib.request.Request(P.URL, data=json.dumps(corpo).encode(),
                                     headers={"content-type": "application/json", "authorization": f"Bearer {CHAVE}",
                                              "x-title": "lead-distributor portaria (avaliacao)"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=90) as r: return json.loads(r.read()), time.time() - t0
        except urllib.error.HTTPError as e:
            corpo_erro = e.read().decode()[:400]
            if e.code == 429:
                time.sleep(15 * (tentativa + 1)); continue
            if e.code == 404 and "data policy" in corpo_erro.lower():
                sys.exit("O OpenRouter bloqueou o modelo gratuito pela politica de dados da conta.\n"
                         "Em openrouter.ai/settings/privacy, permitir endpoints gratuitos que podem registrar prompts\n"
                         "(o texto vai mascarado). Detalhe: " + corpo_erro)
            return {"erro": f"HTTP {e.code}: {corpo_erro}"}, time.time() - t0
        except Exception as e:
            return {"erro": str(e)}, time.time() - t0
    return {"erro": "429 persistente"}, 0


def main():
    linhas = list(csv.DictReader(open(AQUI / "amostra_para_rotular.csv", encoding="utf-8")))
    linhas = [l for l in linhas if l.get("ROTULO_HUMANO") in ("lead", "nao_lead", "duvida")]
    if LIMITE: linhas = linhas[:LIMITE]
    print(f"modelo: {MODELO} ({'GRATUITO, texto mascarado' if GRATIS else 'pago, texto real'}) | {len(linhas)} mensagens\n")
    perigoso, filtrou, deixou_passar, erros, custo, lat = [], 0, [], 0, 0.0, []
    total_nao = sum(1 for l in linhas if l["ROTULO_HUMANO"] == "nao_lead")
    for i, l in enumerate(linhas, 1):
        texto = l["mensagem"]
        if GRATIS: texto = mascarar(texto, l.get("nome_no_lead", ""))
        resp, dt = chamar(texto); lat.append(dt)
        if "erro" in resp: erros += 1
        u = resp.get("usage") or {}
        if u.get("cost") is not None: custo += float(u["cost"])
        r = P.aplicar_travas(P.extrair(resp), texto)
        acao = P.decidir(r); rot = l["ROTULO_HUMANO"]
        if rot in ("lead", "duvida") and acao == "ignorar":
            perigoso.append((i, texto[:90], r["motivo"][:80]))
        if rot == "nao_lead":
            if acao == "ignorar": filtrou += 1
            else: deixou_passar.append((i, texto[:70], r["classificacao"], r.get("trava")))
        if "--verboso" in sys.argv or (rot == "nao_lead") or acao == "ignorar":
            print(f"{i:3} rotulo={rot:8} ia={r['classificacao']:8} acao={acao:10} {dt:4.1f}s | {texto[:70]!r}"
                  + (f"  [trava: {r['trava']}]" if r.get("trava") else ""))
        if GRATIS: time.sleep(3)   # limite de requisicoes dos modelos gratuitos
    print(f"\nERRO PERIGOSO (cliente ignorado): {len(perigoso)}  <- portao: tem de ser 0")
    for p in perigoso: print(f"   #{p[0]} {p[1]!r}\n      motivo da IA: {p[2]}")
    print(f"nao-lead filtrados: {filtrou}/{total_nao} (os que passaram so vao para o vendedor, como hoje)")
    for d in deixou_passar: print(f"   passou #{d[0]} {d[1]!r} -> {d[2]} {('[trava: ' + d[3] + ']') if d[3] else ''}")
    print(f"respostas com erro da API: {erros} (contam como duvida = distribui)")
    print(f"custo: US$ {custo:.4f} | latencia media {sum(lat)/max(len(lat),1):.1f}s, pior {max(lat or [0]):.1f}s")
    print("\nPORTAO:", "PASSOU" if not perigoso else "NAO PASSOU")


if __name__ == "__main__":
    main()
