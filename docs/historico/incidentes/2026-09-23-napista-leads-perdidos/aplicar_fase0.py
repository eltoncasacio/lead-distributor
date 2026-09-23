#!/usr/bin/env python3
"""Fase 0: conecta 'Montar Alerta' -> 'Enviar Alerta Conexao'.
Uso:  python3 fase0.py            (simula)
      python3 fase0.py --aplicar  (grava)
      python3 fase0.py --reverter (desfaz)
Requer N8N_KEY no ambiente."""
import json, os, sys, urllib.request, datetime

KEY = os.environ.get("N8N_KEY")
if not KEY: sys.exit("erro: exporte N8N_KEY com a chave da Public API")
B, WID = "https://n8n.yavoh.cloud/api/v1", "Qj200sqS9544ao3d"
ORIG, DEST = "Montar Alerta", "Enviar Alerta Conexão"

def req(method, path, body=None):
    r = urllib.request.Request(f"{B}/{path}", method=method,
        data=json.dumps(body).encode() if body else None)
    r.add_header("X-N8N-API-KEY", KEY)
    if body: r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=60) as x: return json.loads(x.read())

reverter = "--reverter" in sys.argv
aplicar  = "--aplicar" in sys.argv or reverter

agora = datetime.datetime.now()
if aplicar and not (3 <= agora.hour < 5):
    print(f"!! {agora:%H:%M} esta fora da janela 03h-05h BRT.")
    if input("   continuar mesmo assim? (digite SIM) ") != "SIM": sys.exit("abortado")

wf = req("GET", f"workflows/{WID}")
print(f"workflow: {wf['name']} | versionId: {wf.get('versionId')} | nos: {len(wf['nodes'])}")

conns = wf["connections"]
atual = conns.get(ORIG, {}).get("main", [[]])
ligado = any(c.get("node") == DEST for br in atual for c in (br or []))
print(f"estado atual: {ORIG} -> {'LIGADO' if ligado else 'desligado (saida vazia)'}")

alvo = [] if reverter else [{"node": DEST, "type": "main", "index": 0}]
if ligado == (not reverter):
    sys.exit("nada a fazer: ja esta no estado desejado")

conns.setdefault(ORIG, {})["main"] = [alvo]
payload = {"name": wf["name"], "nodes": wf["nodes"],
           "connections": conns, "settings": wf.get("settings", {})}

if not aplicar:
    print("\n--- SIMULACAO, nada gravado ---")
    print(f"mudaria connections['{ORIG}']['main'] para:")
    print(" ", json.dumps([alvo], ensure_ascii=False))
    print("\nrode com --aplicar para gravar")
    sys.exit(0)

novo = req("PUT", f"workflows/{WID}", payload)
print(f"\nGRAVADO. novo versionId: {novo.get('versionId')}")
dep = req("GET", f"workflows/{WID}")
ok = any(c.get("node") == DEST for br in dep["connections"].get(ORIG, {}).get("main", [[]]) for c in (br or []))
print(f"confirmacao: {ORIG} -> {DEST} = {'LIGADO' if ok else 'desligado'}")
print(f"ativo: {dep.get('active')} | nos: {len(dep['nodes'])} (esperado 62)")
