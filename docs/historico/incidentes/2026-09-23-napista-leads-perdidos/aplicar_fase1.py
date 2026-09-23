#!/usr/bin/env python3
"""Fase 1: alerta quando um lead nao e distribuido.
  python3 fase1.py            simula
  python3 fase1.py --aplicar  grava
  python3 fase1.py --reverter desfaz
Requer N8N_KEY."""
import json, os, sys, urllib.request, datetime

KEY = os.environ.get("N8N_KEY")
if not KEY: sys.exit("erro: exporte N8N_KEY")
B, WID = "https://n8n.yavoh.cloud/api/v1", "Qj200sqS9544ao3d"
# URL, chave e numero do operador sao LIDOS do proprio workflow (nos
# "Enviar Alerta Conexao" e "Montar Alerta"), nunca escritos aqui: nenhum
# segredo mora neste arquivo e nada sai de sincronia se mudarem la.
EVO_URL = EVO_KEY = OPERADOR = None
A, LOJA = "Alerta Lead Nao Distribuido", "Alerta Loja Nao Encontrada"

def req(m, p, body=None):
    r = urllib.request.Request(f"{B}/{p}", method=m,
        data=json.dumps(body).encode() if body else None)
    r.add_header("X-N8N-API-KEY", KEY)
    if body: r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=60) as x: return json.loads(x.read())

def http_node(nome, nid, pos, texto_expr):
    return {
        "parameters": {
            "method": "POST", "url": EVO_URL, "sendHeaders": True,
            "headerParameters": {"parameters": [{"name": "apikey", "value": EVO_KEY}]},
            "sendBody": True, "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify({ number: '" + OPERADOR + "', text: " + texto_expr + " }) }}",
            "options": {},
        },
        "id": nid, "name": nome, "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2, "position": pos,
        "onError": "continueRegularOutput",       # NUNCA derruba a distribuicao
        "retryOnFail": True, "maxTries": 3, "waitBetweenTries": 2000,
    }

ND = "$('Normaliza Dados').item.json"
TXT_LEAD = ("'🚨 *Lead NAO distribuido*\\n\\n'"
    f"+ 'De: ' + ({ND}.remetenteNumero || '?') + '\\n'"
    f"+ 'Nome: ' + ({ND}.pushName || '-') + '\\n'"
    f"+ 'Mensagem: ' + String({ND}.mensagemTexto || '(sem texto)').slice(0,200) + '\\n\\n'"
    "+ 'duplicado: ' + String($json.duplicado ?? '-') + '\\n'"
    "+ 'lead_id: ' + String($json.lead_id ?? '-') + '\\n'"
    "+ 'vendedor: ' + String($json.vendedor_nome ?? '-') + '\\n\\n'"
    "+ 'Execucao: https://n8n.yavoh.cloud/workflow/Qj200sqS9544ao3d/executions/' + $execution.id")
TXT_LOJA = ("'🚨 *Loja nao encontrada*\\n\\n'"
    f"+ 'Instancia: ' + ({ND}.instancia || '?') + '\\n'"
    f"+ 'De: ' + ({ND}.remetenteNumero || '?') + '\\n'"
    f"+ 'Mensagem: ' + String({ND}.mensagemTexto || '(sem texto)').slice(0,200) + '\\n\\n'"
    "+ 'Execucao: https://n8n.yavoh.cloud/workflow/Qj200sqS9544ao3d/executions/' + $execution.id")

reverter = "--reverter" in sys.argv
aplicar  = "--aplicar" in sys.argv or reverter
agora = datetime.datetime.now()
if aplicar and not (3 <= agora.hour < 5):
    print(f"!! {agora:%H:%M} fora da janela 03h-05h BRT.")
    if input("   continuar? (digite SIM) ") != "SIM": sys.exit("abortado")

wf = req("GET", f"workflows/{WID}")
nodes, conns = wf["nodes"], wf["connections"]
print(f"antes: versionId {wf.get('versionId')} | {len(nodes)} nos")

_n = {n["name"]: n for n in nodes}
try:
    _alerta = _n["Enviar Alerta Conexão"]["parameters"]
    EVO_URL = _alerta["url"]
    EVO_KEY = next(h["value"] for h in _alerta["headerParameters"]["parameters"]
                   if h["name"] == "apikey")
    import re as _re
    OPERADOR = _re.search(r"number:\s*'(\d+)'",
                          _n["Montar Alerta"]["parameters"]["jsCode"]).group(1)
except Exception as e:
    sys.exit(f"erro: nao consegui ler URL/chave/operador do workflow: {e}")
print(f"destino do alerta: {OPERADOR} via {EVO_URL.rsplit('/',1)[0]}/...")

existe = {n["name"] for n in nodes}
LOOP = [{"node": "Loop Over Items", "type": "main", "index": 0}]

if reverter:
    nodes = [n for n in nodes if n["name"] not in (A, LOJA)]
    conns.pop(A, None); conns.pop(LOJA, None)
    conns["Duplicado de Plataforma?"]["main"][0] = LOOP
    conns["Vendedor Encontrado?"]["main"][1] = LOOP
    conns["Loja Encontrada?"]["main"] = [conns["Loja Encontrada?"]["main"][0]]
else:
    if A in existe: sys.exit("ja aplicado: no de alerta existe")
    nodes = nodes + [
        http_node(A, "alerta-lead-nao-distribuido", [1728, 1248], TXT_LEAD),
        http_node(LOJA, "alerta-loja-nao-encontrada", [-176, 800], TXT_LOJA)]
    alvoA = [{"node": A, "type": "main", "index": 0}]
    conns["Duplicado de Plataforma?"]["main"][0] = alvoA          # true -> alerta
    conns["Vendedor Encontrado?"]["main"][1] = alvoA              # false -> alerta
    conns[A] = {"main": [LOOP]}                                   # alerta -> volta ao loop
    lj = conns["Loja Encontrada?"]["main"]
    conns["Loja Encontrada?"]["main"] = [lj[0], [{"node": LOJA, "type": "main", "index": 0}]]
    conns[LOJA] = {"main": [[]]}                                  # terminal, nao entra no loop

payload = {"name": wf["name"], "nodes": nodes, "connections": conns,
           "settings": wf.get("settings", {})}

print(f"\n{'REVERTER' if reverter else 'APLICAR'}: {len(nodes)} nos (era {len(wf['nodes'])})")
for k in ["Duplicado de Plataforma?", "Vendedor Encontrado?", "Loja Encontrada?"]:
    print(f"  {k}: {json.dumps(conns[k]['main'], ensure_ascii=False)}")
if not reverter:
    print(f"  {A} -> {json.dumps(conns[A]['main'], ensure_ascii=False)}")
    print(f"  {LOJA} -> {json.dumps(conns[LOJA]['main'], ensure_ascii=False)}  (terminal)")

if not aplicar:
    print("\n--- SIMULACAO, nada gravado. Use --aplicar ---"); sys.exit(0)

novo = req("PUT", f"workflows/{WID}", payload)
print(f"\nGRAVADO. versionId: {novo.get('versionId')}")
d = req("GET", f"workflows/{WID}")
nn = {n["name"]: n for n in d["nodes"]}
print(f"conferindo: {len(d['nodes'])} nos | active={d.get('active')}")
for nm in ([A, LOJA] if not reverter else []):
    n = nn.get(nm)
    print(f"  {nm}: {'OK' if n else 'FALTA'} | onError={n.get('onError') if n else '-'} | retry={n.get('retryOnFail') if n else '-'}")
