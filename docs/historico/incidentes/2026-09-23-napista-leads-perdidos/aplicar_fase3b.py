#!/usr/bin/env python3
"""Fase 3B: registrar TAMBEM a mensagem que a guarda barra.

Furo encontrado em 2026-09-23 ao tracar o caminho de uma mensagem NaPista:
`Registrar Mensagem` pende de `Normalizar Saida Lead`, mas a guarda
`Telefone do Cliente?` barra ANTES disso. Resultado: a mensagem sem telefone
do cliente — exatamente a que precisa de triagem — gerava alerta e nao
ficava registrada. A tela de triagem ficaria vazia para sempre.

Correcao: a saida falsa da guarda passa a alimentar tambem o `Registrar
Mensagem`, alem do alerta.

  python3 aplicar_fase3b.py                            simula
  python3 aplicar_fase3b.py --aplicar --fora-da-janela
  python3 aplicar_fase3b.py --reverter
Requer N8N_KEY."""
import json, os, sys, urllib.request, datetime

KEY = os.environ.get("N8N_KEY")
if not KEY: sys.exit("erro: exporte N8N_KEY")
B, WID = "https://n8n.yavoh.cloud/api/v1", "Qj200sqS9544ao3d"
GUARDA, REG = "Telefone do Cliente?", "Registrar Mensagem"

def req(m, p, body=None):
    r = urllib.request.Request(f"{B}/{p}", method=m,
        data=json.dumps(body).encode() if body else None)
    r.add_header("X-N8N-API-KEY", KEY)
    if body: r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=60) as x: return json.loads(x.read())

reverter = "--reverter" in sys.argv
aplicar = "--aplicar" in sys.argv or reverter
agora = datetime.datetime.now()
if aplicar and not (3 <= agora.hour < 5) and "--fora-da-janela" not in sys.argv:
    sys.exit(f"!! {agora:%H:%M} fora da janela 03h-05h BRT.\n"
             "   Repita com --fora-da-janela para aplicar assim mesmo.")

wf = req("GET", f"workflows/{WID}")
conns = wf["connections"]
print(f"antes: versionId {wf.get('versionId')} | {len(wf['nodes'])} nos")

falsa = conns[GUARDA]["main"][1]
tem = any(c["node"] == REG for c in falsa)
print(f"{GUARDA} [false] -> {[c['node'] for c in falsa]}")
print(f"ja registra? {tem}")

if reverter:
    conns[GUARDA]["main"][1] = [c for c in falsa if c["node"] != REG]
else:
    if tem: sys.exit("nada a fazer")
    conns[GUARDA]["main"][1] = falsa + [{"node": REG, "type": "main", "index": 0}]

print(f"\n{'REVERTER' if reverter else 'APLICAR'}:")
print(f"  {GUARDA} [false] -> {[c['node'] for c in conns[GUARDA]['main'][1]]}")

if not aplicar:
    print("\n--- SIMULACAO, nada gravado ---"); sys.exit(0)

novo = req("PUT", f"workflows/{WID}", {"name": wf["name"], "nodes": wf["nodes"],
    "connections": conns, "settings": wf.get("settings", {})})
print(f"\nGRAVADO. versionId: {novo.get('versionId')}")
d = req("GET", f"workflows/{WID}")
alvos = [c["node"] for c in d["connections"][GUARDA]["main"][1]]
print(f"conferindo: {len(d['nodes'])} nos | active={d.get('active')}")
print(f"  {GUARDA} [false] -> {alvos}")
print(f"  registra o barrado: {REG in alvos}")
print(f"  ainda alerta: {'Alerta NaPista Sem Telefone' in alvos}")
