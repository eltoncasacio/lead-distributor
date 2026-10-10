#!/usr/bin/env python3
"""Liga os comandos por WhatsApp (executar_comando, ja aplicado no banco em
2026-10-10) ao workflow n8n de producao.

Hoje:   Nao E Lead -(gerente/vendedor)-> Identificar Comando -> status | leads | nao reconhecido
Depois: Nao E Lead -(gerente/vendedor)-> Executar Comando (RPC)
                                          -> Comando Legado? -sim-> Identificar Comando (inalterado)
                                                             -nao-> Enviar Resposta Comando

`acao = legado` e o que a funcao devolve quando um GERENTE manda exatamente
`status` ou `leads`: esses continuam no caminho antigo. Todo o resto
(menu, listar/inserir/pausar/reativar/excluir, e o status/leads pessoal do
vendedor) volta pronto da funcao e e so enviado.

O caminho de lead (Nao E Lead -> Verificar Origem) nao e tocado.

  python3 aplicar_comandos_n8n.py              simula (nada gravado)
  python3 aplicar_comandos_n8n.py --aplicar
  python3 aplicar_comandos_n8n.py --reverter   volta o snapshot salvo pelo --aplicar

Requer no .env: N8N_API_KEY. A credencial Supabase do n8n vem da Fase A1
(.n8n_backups/a1_estado.json)."""
import datetime, json, pathlib, sys, urllib.request, uuid

RAIZ = pathlib.Path(__file__).resolve().parents[3]
ENV = {}
for linha in (RAIZ / ".env").read_text().splitlines():
    if "=" in linha and not linha.lstrip().startswith("#"):
        k, v = linha.split("=", 1)
        ENV[k.strip()] = v.strip().strip('"').strip("'")
KEY = ENV.get("N8N_API_KEY")
if not KEY: sys.exit("erro: .env precisa de N8N_API_KEY")
B, WID = "https://n8n.yavoh.cloud/api/v1", "Qj200sqS9544ao3d"
BK = RAIZ / ".n8n_backups"; BK.mkdir(mode=0o700, exist_ok=True)
ESTADO = BK / "comandos_estado.json"
A1 = json.loads((BK / "a1_estado.json").read_text())
CRED = {"httpCustomAuth": {"id": A1["cred_id"], "name": "Supabase Leads service_role"}}

EXEC, LEGADO, ENVIAR = "Executar Comando", "Comando Legado?", "Enviar Resposta Comando"


def req(m, p, body=None):
    r = urllib.request.Request(f"{B}/{p}", method=m, data=json.dumps(body).encode() if body is not None else None)
    r.add_header("X-N8N-API-KEY", KEY)
    if body is not None: r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=60) as x: return json.loads(x.read())


def estado():
    return json.loads(ESTADO.read_text()) if ESTADO.exists() else {}


def salvar_estado(**kw):
    e = estado(); e.update(kw); ESTADO.write_text(json.dumps(e, indent=1)); ESTADO.chmod(0o600)


def transformar(wf):
    N = {n["name"]: n for n in wf["nodes"]}
    C = wf["connections"]
    for nome in ("Não É Lead", "Identificar Comando", "Normaliza Dados", "Preparar Dados Loja", "Enviar Resp Comando"):
        if nome not in N: sys.exit(f"erro: no '{nome}' nao existe — workflow mudou, revisar o script")
    if EXEC in N: sys.exit(f"erro: '{EXEC}' ja existe — ja aplicado?")
    saida_true = C["Não É Lead"]["main"][0]
    if [x["node"] for x in saida_true] != ["Identificar Comando"]:
        sys.exit(f"erro: saida 'true' de Nao E Lead nao e so Identificar Comando: {saida_true}")

    x, y = N["Identificar Comando"]["position"]
    envio = N["Enviar Resp Comando"]["parameters"]
    novos = [
        {"name": EXEC, "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.3, "id": str(uuid.uuid4()),
         "position": [x, y - 220], "credentials": CRED,
         "parameters": {
             "method": "POST",
             "url": "={{ $('Normaliza Dados').item.json.supabaseUrl }}/rest/v1/rpc/executar_comando",
             "authentication": "genericCredentialType", "genericAuthType": "httpCustomAuth",
             "sendBody": True, "specifyBody": "json",
             "jsonBody": "={{ JSON.stringify({ p_loja_id: $('Preparar Dados Loja').item.json.lojaId, "
                         "p_remetente: $('Normaliza Dados').item.json.remetenteNumero, "
                         "p_texto: $('Normaliza Dados').item.json.mensagemTexto }) }}",
             "options": {}}},
        {"name": LEGADO, "type": "n8n-nodes-base.if", "typeVersion": 2.2, "id": str(uuid.uuid4()),
         "position": [x + 220, y - 220],
         "parameters": {"conditions": {
             "options": {"version": 2, "leftValue": "", "caseSensitive": True, "typeValidation": "loose"},
             "conditions": [{"id": str(uuid.uuid4()), "leftValue": "={{ $json.acao }}", "rightValue": "legado",
                             "operator": {"type": "string", "operation": "equals"}}],
             "combinator": "and"}, "looseTypeValidation": True, "options": {}}},
        {"name": ENVIAR, "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.3, "id": str(uuid.uuid4()),
         "position": [x + 440, y - 320],
         "parameters": {
             "method": "POST", "url": envio["url"],
             "sendHeaders": True, "headerParameters": envio["headerParameters"],
             "sendBody": True, "bodyParameters": {"parameters": [
                 {"name": "number", "value": "={{ $('Normaliza Dados').item.json.remetenteNumero }}"},
                 {"name": "text", "value": "={{ $('" + EXEC + "').item.json.resposta }}"}]},
             "options": {}}},
    ]
    wf["nodes"] += novos
    C["Não É Lead"]["main"][0] = [{"node": EXEC, "type": "main", "index": 0}]
    C[EXEC] = {"main": [[{"node": LEGADO, "type": "main", "index": 0}]]}
    C[LEGADO] = {"main": [[{"node": "Identificar Comando", "type": "main", "index": 0}],
                          [{"node": ENVIAR, "type": "main", "index": 0}]]}
    return ["  + no HTTP  'Executar Comando'  -> RPC executar_comando, pela credencial Supabase",
            "  + no IF    'Comando Legado?'   -> acao == legado ? Identificar Comando : Enviar Resposta",
            "  + no HTTP  'Enviar Resposta Comando' -> sendText com o campo resposta, mesma URL/instancia/chave do Enviar Resp Comando",
            "  ~ Nao E Lead (true): Identificar Comando -> Executar Comando"]


def checar(wf, antes):
    N = {n["name"]: n for n in wf["nodes"]}; C = wf["connections"]; erros = []
    if len(wf["nodes"]) != len(antes["nodes"]) + 3: erros.append("numero de nos inesperado")
    if [x["node"] for x in C["Não É Lead"]["main"][0]] != [EXEC]: erros.append("Nao E Lead true nao vai para Executar Comando")
    if C["Não É Lead"]["main"][1] != antes["connections"]["Não É Lead"]["main"][1]: erros.append("caminho de lead (false) mudou")
    if [x["node"] for x in C[LEGADO]["main"][0]] != ["Identificar Comando"]: erros.append("legado nao vai para Identificar Comando")
    if [x["node"] for x in C[LEGADO]["main"][1]] != [ENVIAR]: erros.append("nao-legado nao vai para Enviar Resposta")
    if "httpCustomAuth" not in (N[EXEC].get("credentials") or {}): erros.append("Executar Comando sem credencial")
    # nada fora do ramo de comando mudou
    mudou = [n["name"] for n in antes["nodes"] if json.dumps(n, sort_keys=True) != json.dumps(N.get(n["name"]), sort_keys=True)]
    if mudou: erros.append(f"nos existentes alterados: {mudou}")
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
    if "--reverter" in a:
        snap = estado().get("snapshot")
        if not snap: sys.exit("erro: nao ha snapshot salvo")
        wf = json.loads(pathlib.Path(snap).read_text())
        d = gravar(wf)
        print(f"REVERTIDO para {wf['versionId']}. versao nova {d['versionId']} | ativo={d['active']} | ativa=nova? {d['activeVersionId'] == d['versionId']}")
        print(f"Executar Comando existe? {any(n['name'] == EXEC for n in d['nodes'])}")
        return

    wf = req("GET", f"workflows/{WID}")
    antes = json.loads(json.dumps(wf))
    print(f"antes: versionId {wf['versionId']} | {len(wf['nodes'])} nos | ativo={wf['active']}\n\nmudancas:")
    print("\n".join(transformar(wf)))
    erros = checar(wf, antes)
    print("\ntravas:", "todas ok" if not erros else ""); [print(f"  !! {e}") for e in erros]
    if erros: sys.exit("nada gravado")
    if "--aplicar" not in a:
        print("\n--- SIMULACAO, nada gravado ---"); return

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
