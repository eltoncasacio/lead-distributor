#!/usr/bin/env python3
"""Fase A1: a chave service_role do Supabase sai do workflow e vai para uma
credencial do n8n.

Hoje a chave esta escrita em 6 nos e viaja como campo `supabaseKey` pelos
dados de cada execucao — fica gravada no historico de execucoes, nao so no
workflow. Depois desta mudanca:

  - existe UMA credencial n8n ("Supabase Leads service_role", tipo Custom
    Auth) que injeta os headers `apikey` e `Authorization`;
  - os 9 nos HTTP que falam com o Supabase usam essa credencial;
  - o campo `supabaseKey` deixa de existir em todos os nos (Set e Code);
  - `supabaseUrl` continua como esta — URL nao e segredo.

Esta mudanca NAO troca a chave. A rotacao e um passo separado, depois, e so
exige atualizar a credencial no n8n e o .env do Dashboard.

Passos, em ordem:
  python3 aplicar_a1_credencial_supabase.py                  simula (nada gravado)
  python3 aplicar_a1_credencial_supabase.py --criar-credencial
  python3 aplicar_a1_credencial_supabase.py --testar         workflow descartavel prova a credencial
  python3 aplicar_a1_credencial_supabase.py --aplicar       sem janela de horario, por decisao do dono (2026-10-10)
  python3 aplicar_a1_credencial_supabase.py --reverter       volta o snapshot salvo pelo --aplicar

Requer no .env: N8N_API_KEY, SUPABASE_SERVICE_KEY, SUPABASE_URL.
Estado (id da credencial, snapshots) em .n8n_backups/ — fora do git, contem segredo."""
import datetime, json, pathlib, sys, time, urllib.error, urllib.request, uuid

RAIZ = pathlib.Path(__file__).resolve().parents[3]
ENV = {}
for linha in (RAIZ / ".env").read_text().splitlines():
    if "=" in linha and not linha.lstrip().startswith("#"):
        k, v = linha.split("=", 1)
        ENV[k.strip()] = v.strip().strip('"').strip("'")
KEY, SK, SURL = ENV.get("N8N_API_KEY"), ENV.get("SUPABASE_SERVICE_KEY"), ENV.get("SUPABASE_URL", "").rstrip("/")
if not (KEY and SK and SURL): sys.exit("erro: .env precisa de N8N_API_KEY, SUPABASE_SERVICE_KEY e SUPABASE_URL")

B, WID = "https://n8n.yavoh.cloud/api/v1", "Qj200sqS9544ao3d"
LOJA_ID = "<LOJA_ID>"
CRED_NOME, CRED_TIPO = "Supabase Leads service_role", "httpCustomAuth"
BK = RAIZ / ".n8n_backups"; BK.mkdir(mode=0o700, exist_ok=True)
ESTADO = BK / "a1_estado.json"

HTTP_SUPABASE = ["Identificar Loja", "Distribuir Lead", "Buscar Status", "Buscar Leads",
                 "Buscar Mensagens Prontas", "Buscar Loja Mobiauto", "Buscar Loja Webmotors",
                 "Identificar Remetente", "Registrar Mensagem"]
CODE_SUPABASE = ["Normaliza Dados Mobiauto", "Normaliza Dados Webmotors"]


def req(m, p, body=None, base=B, headers=None):
    r = urllib.request.Request(f"{base}/{p}" if p else base, method=m,
                               data=json.dumps(body).encode() if body is not None else None)
    r.add_header("X-N8N-API-KEY", KEY)
    for k, v in (headers or {}).items(): r.add_header(k, v)
    if body is not None: r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=60) as x:
        t = x.read()
        return json.loads(t) if t else {}


def estado():
    return json.loads(ESTADO.read_text()) if ESTADO.exists() else {}


def salvar_estado(**kw):
    e = estado(); e.update(kw)
    ESTADO.write_text(json.dumps(e, indent=1)); ESTADO.chmod(0o600)


def credencial_ref():
    e = estado()
    if "cred_id" not in e: sys.exit("erro: credencial ainda nao criada — rode --criar-credencial")
    return {"id": e["cred_id"], "name": CRED_NOME}


def usar_credencial(params, node, ref):
    """Tira apikey/Authorization dos headers e liga a credencial."""
    hp = params.get("headerParameters", {}).get("parameters", [])
    resto = [h for h in hp if h.get("name", "").lower() not in ("apikey", "authorization")]
    if resto: params["headerParameters"]["parameters"] = resto
    else:
        params.pop("headerParameters", None); params["sendHeaders"] = False
    params["authentication"] = "genericCredentialType"
    params["genericAuthType"] = CRED_TIPO
    node["credentials"] = {CRED_TIPO: ref}


def transformar(wf, ref):
    N = {n["name"]: n for n in wf["nodes"]}
    log = []
    faltando = [x for x in HTTP_SUPABASE + CODE_SUPABASE if x not in N]
    if faltando: sys.exit(f"erro: nos esperados nao existem mais: {faltando} — workflow mudou, revisar o script")

    for nome in HTTP_SUPABASE:
        usar_credencial(N[nome]["parameters"], N[nome], ref)
        log.append(f"  HTTP  {nome:<26} headers apikey/Authorization -> credencial")

    for n in wf["nodes"]:
        a = n["parameters"].get("assignments", {}).get("assignments")
        if a and any(x.get("name") == "supabaseKey" for x in a):
            n["parameters"]["assignments"]["assignments"] = [x for x in a if x.get("name") != "supabaseKey"]
            log.append(f"  SET   {n['name']:<26} campo supabaseKey removido")

    for nome in CODE_SUPABASE:
        c = N[nome]["parameters"]["jsCode"]
        linhas = [l for l in c.splitlines()
                  if not l.strip().startswith("const supabaseKey") and l.strip() not in ("supabaseKey: supabaseKey,", "supabaseKey: supabaseKey")]
        c2 = "\n".join(linhas).replace("// Credenciais Supabase (hardcoded - apenas para uso interno do workflow)",
                                       "// URL do Supabase (a chave fica na credencial n8n \"" + CRED_NOME + "\")")
        N[nome]["parameters"]["jsCode"] = c2
        log.append(f"  CODE  {nome:<26} const supabaseKey e campo supabaseKey removidos")
    return log


def checar(wf):
    """Travas: se alguma falhar, nada e gravado."""
    s = json.dumps(wf["nodes"], ensure_ascii=False)
    erros = []
    if SK in s: erros.append("a chave service_role ainda aparece no workflow")
    if "supabaseKey" in s: erros.append("ainda ha referencia a supabaseKey")
    for n in wf["nodes"]:
        p = n["parameters"]
        url = str(p.get("url", ""))
        fala_supabase = "supabase" in url.lower() or "supabaseUrl" in url
        if n["type"].endswith("httpRequest") and fala_supabase:
            if p.get("authentication") != "genericCredentialType" or CRED_TIPO not in (n.get("credentials") or {}):
                erros.append(f"{n['name']}: fala com o Supabase sem a credencial")
            hs = [h.get("name", "").lower() for h in p.get("headerParameters", {}).get("parameters", [])]
            if "apikey" in hs or "authorization" in hs:
                erros.append(f"{n['name']}: ainda manda apikey/Authorization a mao")
    return erros


def criar_credencial():
    if "cred_id" in estado():
        print(f"credencial ja criada: {estado()['cred_id']} — nada a fazer"); return
    dados = {"json": json.dumps({"headers": {"apikey": SK, "Authorization": f"Bearer {SK}"}})}
    c = req("POST", "credentials", {"name": CRED_NOME, "type": CRED_TIPO, "data": dados})
    salvar_estado(cred_id=c["id"], cred_criada_em=datetime.datetime.now().isoformat())
    print(f"credencial criada: id {c['id']} | nome '{CRED_NOME}'")


def testar():
    """Workflow descartavel: webhook -> 2 chamadas ao Supabase pela credencial
    (uma leitura de tabela e uma RPC de leitura), igual aos nos de producao.
    Nao escreve nada no banco. Apagado ao final, passe ou falhe."""
    ref = credencial_ref()
    path = f"teste-a1-{uuid.uuid4().hex[:12]}"
    http = lambda nome, pos, extra: {
        "name": nome, "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.3, "position": pos,
        "id": str(uuid.uuid4()), "credentials": {CRED_TIPO: ref},
        "parameters": {"authentication": "genericCredentialType", "genericAuthType": CRED_TIPO,
                       "options": {}, **extra}}
    nodes = [
        {"name": "Webhook", "type": "n8n-nodes-base.webhook", "typeVersion": 2, "position": [0, 0],
         "id": str(uuid.uuid4()), "webhookId": str(uuid.uuid4()),
         "parameters": {"path": path, "httpMethod": "POST", "responseMode": "lastNode", "options": {}}},
        http("Ler Lojas", [220, 0], {"url": f"{SURL}/rest/v1/lojas", "sendQuery": True,
             "queryParameters": {"parameters": [{"name": "id", "value": f"eq.{LOJA_ID}"},
                                                {"name": "select", "value": "id,nome"}]}}),
        http("RPC Status", [440, 0], {"method": "POST", "url": f"{SURL}/rest/v1/rpc/comando_status",
             "sendBody": True, "bodyParameters": {"parameters": [{"name": "p_loja_id", "value": LOJA_ID}]}}),
    ]
    con = {"Webhook": {"main": [[{"node": "Ler Lojas", "type": "main", "index": 0}]]},
           "Ler Lojas": {"main": [[{"node": "RPC Status", "type": "main", "index": 0}]]}}
    w = req("POST", "workflows", {"name": "TESTE A1 credencial Supabase (apagar)", "nodes": nodes,
                                  "connections": con, "settings": {"executionOrder": "v1"}})
    print(f"workflow de teste criado: {w['id']}")
    ok = False
    try:
        req("POST", f"workflows/{w['id']}/activate", {})
        time.sleep(2)
        try:
            r = req("POST", "", {}, base=f"https://n8n.yavoh.cloud/webhook/{path}")
            ok = isinstance(r, dict) and "total_leads" in json.dumps(r)
            print(f"resposta do teste: {json.dumps(r, ensure_ascii=False)[:200]}")
        except urllib.error.HTTPError as e:
            print(f"webhook devolveu HTTP {e.code}: {e.read()[:300]}")
        ex = req("GET", f"executions?workflowId={w['id']}&limit=1&includeData=true").get("data", [])
        if ex:
            rd = ex[0].get("data", {}).get("resultData", {})
            print(f"execucao {ex[0]['id']}: {ex[0]['status']}")
            if rd.get("error"): print(f"  erro: {str(rd['error'].get('message'))[:300]}")
            for nome in ("Ler Lojas", "RPC Status"):
                run = rd.get("runData", {}).get(nome)
                if run:
                    saida = run[0].get("data", {}).get("main", [[{}]])[0]
                    print(f"  {nome}: {json.dumps(saida[0].get('json') if saida else None, ensure_ascii=False)[:150]}")
            vazou = SK in json.dumps(ex[0])
            print(f"  a chave aparece nos dados da execucao? {'SIM — PROBLEMA' if vazou else 'nao'}")
            ok = ok and ex[0]["status"] == "success" and not vazou
    finally:
        try: req("POST", f"workflows/{w['id']}/deactivate", {})
        except Exception: pass
        req("DELETE", f"workflows/{w['id']}")
        print(f"workflow de teste {w['id']} apagado")
    salvar_estado(teste_ok=ok, teste_em=datetime.datetime.now().isoformat())
    print("\nTESTE PASSOU — a credencial autentica no Supabase" if ok else "\nTESTE FALHOU — nao aplicar")
    if not ok: sys.exit(1)


def gravar(wf):
    corpo = {"name": wf["name"], "nodes": wf["nodes"], "connections": wf["connections"],
             "settings": wf.get("settings", {})}
    novo = req("PUT", f"workflows/{WID}", corpo)
    d = req("GET", f"workflows/{WID}")
    if d.get("activeVersionId") != d.get("versionId"):
        print("versao nova nao esta ativa — ativando")
        req("POST", f"workflows/{WID}/activate", {})
        d = req("GET", f"workflows/{WID}")
    return novo, d


def main():
    a = sys.argv[1:]
    if "--criar-credencial" in a: return criar_credencial()
    if "--testar" in a: return testar()

    reverter, aplicar = "--reverter" in a, "--aplicar" in a
    agora = datetime.datetime.now()

    if reverter:
        snap = estado().get("snapshot")
        if not snap: sys.exit("erro: nao ha snapshot salvo")
        wf = json.loads(pathlib.Path(snap).read_text())
        print(f"revertendo para o snapshot {snap} (versionId {wf['versionId']})")
        novo, d = gravar(wf)
        print(f"REVERTIDO. versionId {d['versionId']} | ativo={d['active']} | ativa=versao nova? {d['activeVersionId'] == d['versionId']}")
        return

    wf = req("GET", f"workflows/{WID}")
    print(f"antes: versionId {wf['versionId']} | {len(wf['nodes'])} nos | ativo={wf['active']}")
    ref = credencial_ref() if (aplicar or "cred_id" in estado()) else {"id": "<a criar>", "name": CRED_NOME}
    original = json.loads(json.dumps(wf))
    print("\nmudancas:"); print("\n".join(transformar(wf, ref)))
    erros = checar(wf)
    print("\ntravas:", "todas ok" if not erros else "")
    for e in erros: print(f"  !! {e}")
    if erros: sys.exit("nada gravado")

    if not aplicar:
        print("\n--- SIMULACAO, nada gravado ---"); return
    if not estado().get("teste_ok"): sys.exit("erro: rode --testar e veja passar antes de aplicar")

    snap = BK / f"workflow_{WID}_{original['versionId']}_{agora:%Y%m%d-%H%M%S}.json"
    snap.write_text(json.dumps(original)); snap.chmod(0o600)
    salvar_estado(snapshot=str(snap), versao_antes=original["versionId"])
    print(f"\nsnapshot salvo: {snap}")

    novo, d = gravar(wf)
    print(f"GRAVADO. versionId {original['versionId']} -> {d['versionId']}")
    print(f"conferindo no servidor: {len(d['nodes'])} nos | ativo={d['active']} | versao ativa = nova? {d['activeVersionId'] == d['versionId']}")
    erros = checar(d)
    print("travas no que ficou gravado:", "todas ok" if not erros else erros)
    salvar_estado(versao_depois=d["versionId"], aplicado_em=agora.isoformat())
    if erros or not d["active"] or d["activeVersionId"] != d["versionId"]:
        print("!! algo nao bateu — rode --reverter")


if __name__ == "__main__":
    main()
