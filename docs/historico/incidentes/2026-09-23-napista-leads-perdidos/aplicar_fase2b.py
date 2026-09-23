#!/usr/bin/env python3
"""Fase 2B: usar o telefone parseado, preencher o anuncio, e nunca
distribuir com numero de plataforma como se fosse o cliente.

  python3 aplicar_fase2b.py                           simula
  python3 aplicar_fase2b.py --aplicar                  grava (03h-05h)
  python3 aplicar_fase2b.py --aplicar --fora-da-janela
  python3 aplicar_fase2b.py --reverter
Requer N8N_KEY."""
import json, os, sys, urllib.request, datetime

KEY = os.environ.get("N8N_KEY")
if not KEY: sys.exit("erro: exporte N8N_KEY")
B, WID = "https://n8n.yavoh.cloud/api/v1", "Qj200sqS9544ao3d"
GUARDA, ALERTA = "Telefone do Cliente?", "Alerta NaPista Sem Telefone"
PLATAFORMAS = ["551131361712", "551130044558"]   # NaPista, iCarros

def req(m, p, body=None):
    r = urllib.request.Request(f"{B}/{p}", method=m,
        data=json.dumps(body).encode() if body else None)
    r.add_header("X-N8N-API-KEY", KEY)
    if body: r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=60) as x: return json.loads(x.read())

CAMPOS = {   # no -> {campo: (valor_antigo, valor_novo)}
 "Prepara Dados NaPista": {
   # Fallback obrigatorio: quando o CLIENTE manda o link do anuncio, o
   # parser nao acha telefone no texto, mas o remetente E o cliente (23
   # leads assim no banco). Sem o fallback, a guarda bloquearia leads bons.
   # Quando a PLATAFORMA repassa, o remetente e o numero dela — e ai a
   # guarda barra. O par fallback+guarda cobre os dois casos.
   "telefone": ("={{ $('Normaliza Dados').item.json.remetenteNumero }}",
                "={{ $json.telefone || $('Normaliza Dados').item.json.remetenteNumero }}"),
   "anuncio":  ("={{ $('Normaliza Dados').item.json.anuncio }}",
                "={{ $json.anuncio || '' }}"),
 },
 "Distribuir Lead": {
   "p_mensagem_original": (
     "={{ $input.item.json.anuncio || $input.item.json.mensagemTexto }}",
     "={{ $input.item.json.mensagemTexto }}"),
 },
}

_dig = "String($json.telefone || '').replace(/\\D/g,'')"
COND = ("={{ " + _dig + ".length >= 10 && !"
        + json.dumps(PLATAFORMAS) + ".includes(" + _dig + ") }}")

ND = "$('Normaliza Dados').item.json"
TXT = ("'🚨 *Lead NaPista sem telefone do cliente*\\n\\n'"
  "+ 'Cliente: ' + ($json.nome || '(nao identificado)') + '\\n'"
  "+ 'Veiculo: ' + ($json.anuncio || '(nao identificado)') + '\\n'"
  "+ 'Telefone extraido: ' + ($json.telefone || '(nenhum)') + '\\n\\n'"
  f"+ 'Mensagem: ' + String({ND}.mensagemTexto || '(sem texto)').slice(0,200) + '\\n\\n'"
  "+ 'Nao distribuido de proposito: sem telefone do cliente nao ha para quem\\n'"
  "+ 'enviar. Abra a oportunidade no portal da NaPista para pegar o contato.\\n\\n'"
  "+ 'Execucao: https://n8n.yavoh.cloud/workflow/Qj200sqS9544ao3d/executions/' + $execution.id")

def set_campo(node, nome, valor):
    for f in node["parameters"]["assignments"]["assignments"]:
        if f.get("name") == nome: f["value"] = valor; return True
    return False

def get_campo(node, nome):
    for f in node["parameters"]["assignments"]["assignments"]:
        if f.get("name") == nome: return f.get("value")

def get_param(node, nome):
    for p in node["parameters"]["bodyParameters"]["parameters"]:
        if p.get("name") == nome: return p.get("value")

def set_param(node, nome, valor):
    for p in node["parameters"]["bodyParameters"]["parameters"]:
        if p.get("name") == nome: p["value"] = valor; return True
    return False

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

alerta_evo = N["Enviar Alerta Conexão"]["parameters"]
EVO_URL = alerta_evo["url"]
EVO_KEY = next(h["value"] for h in alerta_evo["headerParameters"]["parameters"]
               if h["name"] == "apikey")
import re
OPERADOR = re.search(r"number:\s*'(\d+)'", N["Montar Alerta"]["parameters"]["jsCode"]).group(1)

idx = 1 if reverter else 0     # reverter usa o valor antigo
print(f"\n{'REVERTER' if reverter else 'APLICAR'} campos:")
for no, campos in CAMPOS.items():
    for campo, (antigo, novo) in campos.items():
        atual = get_campo(N[no], campo) if no != "Distribuir Lead" else get_param(N[no], campo)
        alvo = antigo if reverter else novo
        estado = "ja esta" if atual == alvo else "muda"
        print(f"  {no}.{campo}: {estado}")
        print(f"      de : {atual}")
        print(f"      para: {alvo}")
        if no == "Distribuir Lead": set_param(N[no], campo, alvo)
        else: set_campo(N[no], campo, alvo)

if reverter:
    nodes = [n for n in nodes if n["name"] not in (GUARDA, ALERTA)]
    conns.pop(GUARDA, None); conns.pop(ALERTA, None)
    conns["Prepara Dados NaPista"]["main"] = [[{"node": "Normalizar Saída Lead", "type": "main", "index": 0}]]
else:
    if GUARDA in N: sys.exit("\nja aplicado: no de guarda existe")
    nodes = nodes + [
      {"parameters": {"conditions": {"options": {"version": 2, "leftValue": "",
          "caseSensitive": True, "typeValidation": "loose"}, "combinator": "and",
          "conditions": [{"id": "cond-telefone-cliente",
            "operator": {"type": "boolean", "operation": "true", "singleValue": True},
            "leftValue": COND}]}, "options": {}},
       "id": "telefone-do-cliente", "name": GUARDA, "type": "n8n-nodes-base.if",
       "typeVersion": 2.2, "position": [-560, 1024]},
      {"parameters": {"method": "POST", "url": EVO_URL, "sendHeaders": True,
         "headerParameters": {"parameters": [{"name": "apikey", "value": EVO_KEY}]},
         "sendBody": True, "specifyBody": "json",
         "jsonBody": "={{ JSON.stringify({ number: '" + OPERADOR + "', text: " + TXT + " }) }}",
         "options": {}},
       "id": "alerta-napista-sem-telefone", "name": ALERTA,
       "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
       "position": [-560, 1248], "onError": "continueRegularOutput",
       "retryOnFail": True, "maxTries": 3, "waitBetweenTries": 2000},
    ]
    conns["Prepara Dados NaPista"]["main"] = [[{"node": GUARDA, "type": "main", "index": 0}]]
    conns[GUARDA] = {"main": [
        [{"node": "Normalizar Saída Lead", "type": "main", "index": 0}],   # true
        [{"node": ALERTA, "type": "main", "index": 0}]]}                   # false
    conns[ALERTA] = {"main": [[]]}                                          # terminal

print(f"\nnos: {len(nodes)} (era {len(wf['nodes'])})")
print(f"  Prepara Dados NaPista -> {json.dumps(conns['Prepara Dados NaPista']['main'],ensure_ascii=False)}")
if not reverter:
    print(f"  {GUARDA} [true]  -> Normalizar Saída Lead")
    print(f"  {GUARDA} [false] -> {ALERTA} (terminal)")
    print(f"  condicao: {COND}")

if not aplicar:
    print("\n--- SIMULACAO, nada gravado ---"); sys.exit(0)

novo = req("PUT", f"workflows/{WID}", {"name": wf["name"], "nodes": nodes,
    "connections": conns, "settings": wf.get("settings", {})})
print(f"\nGRAVADO. versionId: {novo.get('versionId')}")
d = req("GET", f"workflows/{WID}"); DN = {n["name"]: n for n in d["nodes"]}
print(f"conferindo: {len(d['nodes'])} nos | active={d.get('active')}")
print(f"  telefone: {get_campo(DN['Prepara Dados NaPista'],'telefone')}")
print(f"  anuncio : {get_campo(DN['Prepara Dados NaPista'],'anuncio')}")
print(f"  p_mensagem_original: {get_param(DN['Distribuir Lead'],'p_mensagem_original')}")
if not reverter:
    g = DN.get(GUARDA); a = DN.get(ALERTA)
    print(f"  {GUARDA}: {'OK' if g else 'FALTA'}")
    print(f"  {ALERTA}: {'OK' if a else 'FALTA'} | onError={a.get('onError') if a else '-'}")
