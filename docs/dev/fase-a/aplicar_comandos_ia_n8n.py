#!/usr/bin/env python3
"""Liga a IA (comandos_ia/prompt.py) na frente dos comandos por WhatsApp.

Hoje:   Nao E Lead -> Executar Comando (rpc/executar_comando) -> ...
Depois: Nao E Lead -> Buscar Nomes Vendedores -> Montar Pedido IA -> Interpretar (IA) -> Ler Sugestao IA
                   -> Executar Comando (rpc/executar_comando_ia, com p_sugestao) -> ...

- Buscar Nomes Vendedores: GET vendedores da loja (nao removidos), so `nome`,
  pela credencial Supabase. A IA precisa dos nomes para entender apelido.
- Interpretar (IA): POST no OpenRouter com o corpo de prompt.corpo_requisicao,
  pela credencial "OpenRouter comandos" (chave fora do workflow).
- Ler Sugestao IA: tira {acao, nome, telefone, pergunta} da resposta; se algo
  falhou, sugestao = null.
- Os quatro nos usam onError=continueRegularOutput: IA fora do ar, timeout ou
  resposta estranha nunca derrubam o comando — vale o texto original, igual a
  sem IA. As travas ficam em executar_comando_ia, no Postgres.

  python3 aplicar_comandos_ia_n8n.py                      simula
  python3 aplicar_comandos_ia_n8n.py --criar-credencial   cria a credencial do OpenRouter no n8n
  python3 aplicar_comandos_ia_n8n.py --aplicar
  python3 aplicar_comandos_ia_n8n.py --reverter

Requer no .env: N8N_API_KEY e OPENROUTER_API_KEY. Precisa de
executar_comando_ia(uuid,text,text,jsonb) ja aplicada no banco."""
import datetime, json, pathlib, sys, urllib.request, uuid

RAIZ = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / "comandos_ia"))
import prompt as P

ENV = {}
for linha in (RAIZ / ".env").read_text().splitlines():
    if "=" in linha and not linha.lstrip().startswith("#"):
        k, v = linha.split("=", 1)
        ENV[k.strip()] = v.strip().strip('"').strip("'")
KEY = ENV.get("N8N_API_KEY")
if not KEY: sys.exit("erro: .env precisa de N8N_API_KEY")
B, WID = "https://n8n.yavoh.cloud/api/v1", "Qj200sqS9544ao3d"
BK = RAIZ / ".n8n_backups"; BK.mkdir(mode=0o700, exist_ok=True)
ESTADO = BK / "comandos_ia_estado.json"
A1 = json.loads((BK / "a1_estado.json").read_text())
CRED_SB = {"httpCustomAuth": {"id": A1["cred_id"], "name": "Supabase Leads service_role"}}
CRED_OR_NOME = "OpenRouter comandos"

NOMES, MONTAR, IA, LER, EXEC = ("Buscar Nomes Vendedores", "Montar Pedido IA", "Interpretar (IA)",
                                 "Ler Sugestão IA", "Executar Comando")


def req(m, p, body=None):
    r = urllib.request.Request(f"{B}/{p}", method=m, data=json.dumps(body).encode() if body is not None else None)
    r.add_header("X-N8N-API-KEY", KEY)
    if body is not None: r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=60) as x: return json.loads(x.read())


def estado():
    return json.loads(ESTADO.read_text()) if ESTADO.exists() else {}


def salvar_estado(**kw):
    e = estado(); e.update(kw); ESTADO.write_text(json.dumps(e, indent=1)); ESTADO.chmod(0o600)


def criar_credencial():
    if "cred_or_id" in estado():
        print(f"credencial ja criada: {estado()['cred_or_id']}"); return
    chave = ENV.get("OPENROUTER_API_KEY")
    if not chave: sys.exit("erro: .env precisa de OPENROUTER_API_KEY")
    c = req("POST", "credentials", {"name": CRED_OR_NOME, "type": "httpHeaderAuth",
                                     "data": {"name": "Authorization", "value": f"Bearer {chave}"}})
    salvar_estado(cred_or_id=c["id"])
    print(f"credencial criada: id {c['id']} | '{CRED_OR_NOME}'")


def montar_js():
    """Codigo do no 'Montar Pedido IA': o corpo de prompt.corpo_requisicao, com o
    texto do usuario montado aqui. Usa montar_usuario com marcadores trocados por
    split/join — o texto final e identico ao que avaliar.py testou. Fica num no
    de codigo (e nao numa expressao {{ }}) porque o corpo tem '}}' aninhados."""
    base = P.corpo_requisicao("<<TEXTO>>", "<<PAPEL>>", ["<<VEND>>"], P.MODELO, "openrouter")
    usuario = base["messages"][1]["content"]
    return (
        "// Gerado por docs/dev/fase-a/aplicar_comandos_ia_n8n.py a partir de comandos_ia/prompt.py.\n"
        "// NAO editar aqui: mude o prompt.py, rode avaliar.py e reaplique.\n"
        f"const corpo = {json.dumps(base, ensure_ascii=False, indent=1)};\n"
        f"const modelo = {json.dumps(usuario, ensure_ascii=False)};\n"
        "let nomes = [];\n"
        "try { nomes = ($('" + NOMES + "').item.json.body || []).map(v => v.nome).filter(Boolean); } catch (e) { nomes = []; }\n"
        "const usuario = modelo\n"
        "  .split('<<VEND>>').join(nomes.length ? nomes.join(', ') : '(nenhum)')\n"
        "  .split('<<PAPEL>>').join($('Identificar Remetente').item.json.papel || '')\n"
        "  .split('<<TEXTO>>').join(($('Normaliza Dados').item.json.mensagemTexto || '').slice(0, " + str(P.LIMITE_TEXTO) + "));\n"
        "corpo.messages[1].content = usuario;\n"
        "return { json: { corpo } };\n"
    )


LER_JS = """// Sugestao estruturada da IA, ou null se a IA falhou/recusou/cortou.
// As travas de verdade ficam em executar_comando_ia (Postgres).
const r = $('""" + IA + """').item.json;
let sugestao = null;
try {
  const c = r.choices[0];
  if (c.finish_reason === 'stop') {
    const d = JSON.parse(c.message.content);
    if (d && typeof d === 'object' && typeof d.acao === 'string') sugestao = d;
  }
} catch (e) { sugestao = null; }
return { json: { sugestao } };"""


def transformar(wf):
    N = {n["name"]: n for n in wf["nodes"]}; C = wf["connections"]
    for nome in ("Não É Lead", EXEC, "Normaliza Dados", "Preparar Dados Loja", "Identificar Remetente"):
        if nome not in N: sys.exit(f"erro: no '{nome}' nao existe")
    if IA in N: sys.exit("erro: IA ja ligada")
    if [x["node"] for x in C["Não É Lead"]["main"][0]] != [EXEC]:
        sys.exit("erro: Nao E Lead (true) nao vai direto para Executar Comando")
    cred_or = {"httpHeaderAuth": {"id": estado()["cred_or_id"], "name": CRED_OR_NOME}} if "cred_or_id" in estado() \
        else {"httpHeaderAuth": {"id": "<a criar>", "name": CRED_OR_NOME}}
    x, y = N[EXEC]["position"]
    novos = [
        {"name": NOMES, "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.3, "id": str(uuid.uuid4()),
         "position": [x - 880, y], "credentials": CRED_SB, "onError": "continueRegularOutput",
         "parameters": {
             "url": "={{ $('Normaliza Dados').item.json.supabaseUrl }}/rest/v1/vendedores",
             "authentication": "genericCredentialType", "genericAuthType": "httpCustomAuth",
             "sendQuery": True, "queryParameters": {"parameters": [
                 {"name": "loja_id", "value": "=eq.{{ $('Preparar Dados Loja').item.json.lojaId }}"},
                 {"name": "status", "value": "neq.removido"},
                 {"name": "select", "value": "nome"},
                 {"name": "order", "value": "ordem_fila"}]},
             "options": {"response": {"response": {"fullResponse": True}}, "timeout": 5000}}},
        {"name": MONTAR, "type": "n8n-nodes-base.code", "typeVersion": 2, "id": str(uuid.uuid4()),
         "position": [x - 660, y], "onError": "continueRegularOutput",
         "parameters": {"mode": "runOnceForEachItem", "jsCode": montar_js()}},
        {"name": IA, "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.3, "id": str(uuid.uuid4()),
         "position": [x - 440, y], "credentials": cred_or, "onError": "continueRegularOutput",
         "parameters": {
             "method": "POST", "url": P.URL["openrouter"],
             "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
             "sendHeaders": True, "headerParameters": {"parameters": [{"name": "X-Title", "value": "lead-distributor comandos"}]},
             "sendBody": True, "specifyBody": "json", "jsonBody": "={{ JSON.stringify($json.corpo) }}",
             "options": {"timeout": 12000}}},
        {"name": LER, "type": "n8n-nodes-base.code", "typeVersion": 2, "id": str(uuid.uuid4()),
         "position": [x - 220, y], "onError": "continueRegularOutput",
         "parameters": {"mode": "runOnceForEachItem", "jsCode": LER_JS}},
    ]
    wf["nodes"] += novos
    ex = N[EXEC]["parameters"]
    ex["url"] = "={{ $('Normaliza Dados').item.json.supabaseUrl }}/rest/v1/rpc/executar_comando_ia"
    ex["jsonBody"] = ("={{ JSON.stringify({ p_loja_id: $('Preparar Dados Loja').item.json.lojaId, "
                      "p_remetente: $('Normaliza Dados').item.json.remetenteNumero, "
                      "p_texto: $('Normaliza Dados').item.json.mensagemTexto, "
                      "p_sugestao: ($('" + LER + "').isExecuted ? ($('" + LER + "').item.json.sugestao ?? null) : null) }) }}")
    C["Não É Lead"]["main"][0] = [{"node": NOMES, "type": "main", "index": 0}]
    C[NOMES] = {"main": [[{"node": MONTAR, "type": "main", "index": 0}]]}
    C[MONTAR] = {"main": [[{"node": IA, "type": "main", "index": 0}]]}
    C[IA] = {"main": [[{"node": LER, "type": "main", "index": 0}]]}
    C[LER] = {"main": [[{"node": EXEC, "type": "main", "index": 0}]]}
    return [f"  + {NOMES}  (GET nomes, credencial Supabase, falha nao para o fluxo)",
            f"  + {MONTAR}  (monta o corpo a partir de comandos_ia/prompt.py)",
            f"  + {IA}  (OpenRouter, {P.MODELO}, esforco {P.ESFORCO}, timeout 12 s, falha nao para o fluxo)",
            f"  + {LER}  (extrai a sugestao; null se algo deu errado)",
            f"  ~ {EXEC}: rpc/executar_comando -> rpc/executar_comando_ia (+ p_sugestao)",
            "  ~ Nao E Lead (true) -> Buscar Nomes Vendedores"]


def checar(wf, antes):
    N = {n["name"]: n for n in wf["nodes"]}; C = wf["connections"]; erros = []
    if len(wf["nodes"]) != len(antes["nodes"]) + 4: erros.append("numero de nos inesperado")
    if [x["node"] for x in C["Não É Lead"]["main"][0]] != [NOMES]: erros.append("entrada da IA errada")
    if C["Não É Lead"]["main"][1] != antes["connections"]["Não É Lead"]["main"][1]: erros.append("caminho de lead mudou")
    if [x["node"] for x in C[LER]["main"][0]] != [EXEC]: erros.append("Ler Sugestao nao vai para Executar Comando")
    for n in (NOMES, MONTAR, IA, LER):
        if N[n].get("onError") != "continueRegularOutput": erros.append(f"{n} sem continuar-em-falha")
    if ENV.get("OPENROUTER_API_KEY", "x") in json.dumps(wf["nodes"]): erros.append("chave do OpenRouter escrita no workflow")
    if "executar_comando_ia" not in N[EXEC]["parameters"]["url"]: erros.append("Executar Comando nao chama executar_comando_ia")
    mudou = [n["name"] for n in antes["nodes"] if n["name"] != EXEC and
             json.dumps(n, sort_keys=True) != json.dumps(N.get(n["name"]), sort_keys=True)]
    if mudou: erros.append(f"outros nos alterados: {mudou}")
    outras = {k: v for k, v in antes["connections"].items() if k != "Não É Lead"}
    if any(C.get(k) != v for k, v in outras.items()): erros.append("outras conexoes mudaram")
    return erros


def gravar(wf):
    req("PUT", f"workflows/{WID}", {"name": wf["name"], "nodes": wf["nodes"], "connections": wf["connections"],
                                    "settings": wf.get("settings", {})})
    d = req("GET", f"workflows/{WID}")
    if d.get("activeVersionId") != d.get("versionId"):
        req("POST", f"workflows/{WID}/activate", {}); d = req("GET", f"workflows/{WID}")
    return d


def main():
    a = sys.argv[1:]
    if "--criar-credencial" in a: return criar_credencial()
    if "--reverter" in a:
        snap = estado().get("snapshot")
        if not snap: sys.exit("erro: nao ha snapshot salvo")
        wf = json.loads(pathlib.Path(snap).read_text()); d = gravar(wf)
        print(f"REVERTIDO para {wf['versionId']}. nova {d['versionId']} | ativo={d['active']} | ativa=nova? {d['activeVersionId'] == d['versionId']}")
        return
    wf = req("GET", f"workflows/{WID}"); antes = json.loads(json.dumps(wf))
    print(f"antes: versionId {wf['versionId']} | {len(wf['nodes'])} nos | ativo={wf['active']}\n\nmudancas:")
    print("\n".join(transformar(wf)))
    erros = checar(wf, antes)
    print("\ntravas:", "todas ok" if not erros else ""); [print(f"  !! {e}") for e in erros]
    if erros: sys.exit("nada gravado")
    if "--aplicar" not in a:
        print("\n--- SIMULACAO, nada gravado ---"); return
    if "cred_or_id" not in estado(): sys.exit("erro: rode --criar-credencial antes")
    agora = datetime.datetime.now()
    snap = BK / f"workflow_{WID}_{antes['versionId']}_{agora:%Y%m%d-%H%M%S}.json"
    snap.write_text(json.dumps(antes)); snap.chmod(0o600)
    salvar_estado(snapshot=str(snap), versao_antes=antes["versionId"])
    print(f"\nsnapshot: {snap}")
    d = gravar(wf)
    print(f"GRAVADO. versionId {antes['versionId']} -> {d['versionId']} | ativo={d['active']} | ativa=nova? {d['activeVersionId'] == d['versionId']}")
    erros = checar(d, antes)
    print("travas no que ficou gravado:", "todas ok" if not erros else erros)
    salvar_estado(versao_depois=d["versionId"], aplicado_em=agora.isoformat())


if __name__ == "__main__":
    main()
