#!/usr/bin/env python3
"""Fase 3 (n8n): registrar toda mensagem candidata a lead.

RAMO LATERAL, nao no caminho. Um no HTTP Request substitui o item pela
resposta da chamada — inserir no meio quebraria o `Distribuir Lead`, que le
$input.item.json.telefone. Entao o registro sai de uma segunda conexao da
mesma saida de `Normalizar Saida Lead`: os dois ramos recebem o mesmo item,
rodam em paralelo, e o de registro e terminal. Distribuicao intocada.

  python3 aplicar_fase3.py                            simula
  python3 aplicar_fase3.py --aplicar --fora-da-janela
  python3 aplicar_fase3.py --reverter
Requer N8N_KEY."""
import json, os, sys, urllib.request, datetime

KEY = os.environ.get("N8N_KEY")
if not KEY: sys.exit("erro: exporte N8N_KEY")
B, WID = "https://n8n.yavoh.cloud/api/v1", "Qj200sqS9544ao3d"
NO = "Registrar Mensagem"

def req(m, p, body=None):
    r = urllib.request.Request(f"{B}/{p}", method=m,
        data=json.dumps(body).encode() if body else None)
    r.add_header("X-N8N-API-KEY", KEY)
    if body: r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=60) as x: return json.loads(x.read())

# id externo: id da mensagem na Evolution + indice do item, porque uma
# mensagem pode trazer N leads (formato de lista do iCarros). Sem o indice,
# o indice unico colapsaria os N num so e o livro-razao perderia leads.
# Guardado por isExecuted: nos webhooks de portal o no Webhook nao roda.
EXT = ("={{ $('Webhook').isExecuted"
       " ? ($('Webhook').first().json.body?.data?.key?.id ?? null)"
       "   + '-' + $itemIndex"
       " : null }}")

CORPO = [
  ("p_loja_id",             "={{ $json.lojaId }}"),
  ("p_canal",               "={{ $('Webhook').isExecuted ? 'whatsapp' : 'webhook' }}"),
  ("p_origem_detectada",    "={{ $json.origem || 'WhatsApp Direto' }}"),
  ("p_mensagem_externa_id", EXT),
  ("p_remetente_numero",    "={{ $('Normaliza Dados').item.json.remetenteNumero || null }}"),
  ("p_remetente_nome",      "={{ $('Normaliza Dados').item.json.pushName || null }}"),
  ("p_texto",               "={{ $json.mensagemTexto || null }}"),
  ("p_telefone_extraido",   "={{ $json.telefone || null }}"),
  ("p_anuncio_extraido",    "={{ $json.anuncio || null }}"),
  ("p_classificado_por",    "regra"),
  ("p_n8n_execution_id",    "={{ $execution.id }}"),
]

reverter = "--reverter" in sys.argv
aplicar = "--aplicar" in sys.argv or reverter
agora = datetime.datetime.now()
if aplicar and not (3 <= agora.hour < 5) and "--fora-da-janela" not in sys.argv:
    sys.exit(f"!! {agora:%H:%M} fora da janela 03h-05h BRT.\n"
             "   Repita com --fora-da-janela para aplicar assim mesmo.")

wf = req("GET", f"workflows/{WID}")
nodes, conns = wf["nodes"], wf["connections"]
N = {n["name"]: n for n in nodes}
print(f"antes: versionId {wf.get('versionId')} | {len(nodes)} nos")

# URL e chave do Supabase saem do proprio workflow, nunca escritas aqui
nd = {f["name"]: f["value"] for f in
      N["Normaliza Dados"]["parameters"]["assignments"]["assignments"]}
SUPA_KEY = nd["supabaseKey"].lstrip("=")
SUPA_URL = "https://drtdctpwxkqqnhnikpwz.supabase.co"
print(f"supabase: {SUPA_URL} (chave lida do no Normaliza Dados)")

destino_atual = conns["Normalizar Saída Lead"]["main"][0]
print(f"Normalizar Saida Lead -> {[c['node'] for c in destino_atual]}")

if reverter:
    nodes = [n for n in nodes if n["name"] != NO]
    conns.pop(NO, None)
    conns["Normalizar Saída Lead"]["main"][0] = [
        c for c in destino_atual if c["node"] != NO]
else:
    if NO in N: sys.exit("ja aplicado")
    nodes = nodes + [{
      "parameters": {
        "method": "POST",
        "url": f"{SUPA_URL}/rest/v1/rpc/registrar_mensagem_recebida",
        "sendHeaders": True,
        "headerParameters": {"parameters": [
          {"name": "apikey", "value": SUPA_KEY},
          {"name": "Authorization", "value": f"Bearer {SUPA_KEY}"},
          {"name": "Content-Type", "value": "application/json"}]},
        "sendBody": True,
        "bodyParameters": {"parameters": [
          {"name": k, "value": v} for k, v in CORPO]},
        "options": {}},
      "id": "registrar-mensagem", "name": NO,
      "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
      "position": [1104, 1248],
      "onError": "continueRegularOutput",   # registro nunca derruba distribuicao
      "retryOnFail": True, "maxTries": 3, "waitBetweenTries": 2000}]
    conns["Normalizar Saída Lead"]["main"][0] = destino_atual + [
        {"node": NO, "type": "main", "index": 0}]
    conns[NO] = {"main": [[]]}              # terminal

print(f"\n{'REVERTER' if reverter else 'APLICAR'}: {len(nodes)} nos (era {len(wf['nodes'])})")
print(f"  Normalizar Saida Lead -> {[c['node'] for c in conns['Normalizar Saída Lead']['main'][0]]}")
if not reverter:
    print(f"  {NO} -> terminal | onError=continueRegularOutput")
    print(f"  id externo: id da Evolution + indice do item (mensagem com N leads)")

if not aplicar:
    print("\n--- SIMULACAO, nada gravado ---"); sys.exit(0)

novo = req("PUT", f"workflows/{WID}", {"name": wf["name"], "nodes": nodes,
    "connections": conns, "settings": wf.get("settings", {})})
print(f"\nGRAVADO. versionId: {novo.get('versionId')}")
d = req("GET", f"workflows/{WID}"); DN = {n["name"]: n for n in d["nodes"]}
print(f"conferindo: {len(d['nodes'])} nos | active={d.get('active')}")
alvos = [c["node"] for c in d["connections"]["Normalizar Saída Lead"]["main"][0]]
print(f"  Normalizar Saida Lead -> {alvos}")
print(f"  'Loop Over Items' ainda no caminho: {'Loop Over Items' in alvos}")
if not reverter:
    n = DN.get(NO)
    print(f"  {NO}: {'OK' if n else 'FALTA'} | onError={n.get('onError') if n else '-'}")
