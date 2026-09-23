#!/usr/bin/env python3
"""Fase 2C: alertas de lead vao para o GERENTE, e levam o link do portal.

Duas correcoes:

1. Destino. Os alertas iam para 5519996977453 (o dono do sistema). Os que
   pedem acao comercial passam a ir para o gerente cadastrado. Os tecnicos
   (queda de conexao, loja nao encontrada) continuam com o dono — nao e
   assunto do gerente.

2. O link. O alerta do NaPista mandava nome e veiculo mas nao o link da
   oportunidade, que fica em hydratedButtons[0].urlButton.url e nao no texto
   da mensagem. Sem ele o gerente teria que cacar a oportunidade no portal.

  python3 aplicar_fase2c.py                            simula
  python3 aplicar_fase2c.py --aplicar --fora-da-janela
  python3 aplicar_fase2c.py --reverter
Requer N8N_KEY."""
import json, os, re, sys, urllib.request, datetime

KEY = os.environ.get("N8N_KEY")
if not KEY: sys.exit("erro: exporte N8N_KEY")
B, WID = "https://n8n.yavoh.cloud/api/v1", "Qj200sqS9544ao3d"
DONO = "5519996977453"
GERENTE = "5519XXXXXXXXX"     # Renato, unico gerente ativo da loja
COMERCIAIS = ["Alerta Lead Nao Distribuido", "Alerta NaPista Sem Telefone"]

def req(m, p, body=None):
    r = urllib.request.Request(f"{B}/{p}", method=m,
        data=json.dumps(body).encode() if body else None)
    r.add_header("X-N8N-API-KEY", KEY)
    if body: r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=60) as x: return json.loads(x.read())

LINK = ("($('Webhook').isExecuted"
        " ? ($('Webhook').first().json.body?.data?.message?.templateMessage"
        "?.hydratedTemplate?.hydratedButtons?.[0]?.urlButton?.url ?? '')"
        " : '')")

reverter = "--reverter" in sys.argv
aplicar = "--aplicar" in sys.argv or reverter
agora = datetime.datetime.now()
if aplicar and not (3 <= agora.hour < 5) and "--fora-da-janela" not in sys.argv:
    sys.exit(f"!! {agora:%H:%M} fora da janela 03h-05h BRT.\n"
             "   Repita com --fora-da-janela para aplicar assim mesmo.")

wf = req("GET", f"workflows/{WID}")
N = {n["name"]: n for n in wf["nodes"]}
print(f"antes: versionId {wf.get('versionId')} | {len(wf['nodes'])} nos")

de, para = (GERENTE, DONO) if reverter else (DONO, GERENTE)
print(f"\ndestino dos alertas comerciais: {de} -> {para}")

for nome in COMERCIAIS:
    n = N[nome]
    jb = n["parameters"]["jsonBody"]
    antes = re.search(r"number:\s*'(\d+)'", jb)
    jb2 = re.sub(r"(number:\s*')\d+(')", r"\g<1>" + para + r"\g<2>", jb)

    # acrescenta o link da oportunidade so no alerta do NaPista
    if nome == "Alerta NaPista Sem Telefone" and not reverter and "urlButton" not in jb2:
        jb2 = jb2.replace(
            "+ 'Nao distribuido de proposito:",
            "+ ((" + LINK + ") ? 'Abrir a oportunidade:\\n' + " + LINK + " + '\\n\\n' : '')"
            "+ 'Nao distribuido de proposito:")
    elif nome == "Alerta NaPista Sem Telefone" and reverter:
        jb2 = re.sub(r"\+ \(\(\$\('Webhook'\).*?\) : ''\)\n?", "", jb2, flags=re.S)

    n["parameters"]["jsonBody"] = jb2
    tem_link = "urlButton" in jb2
    print(f"  {nome:<30} {antes.group(1) if antes else '?'} -> {para} | link: {tem_link}")

print("\ntecnicos (seguem com o dono):")
for nome in ["Enviar Alerta Conexão", "Alerta Loja Nao Encontrada"]:
    n = N.get(nome)
    if not n: continue
    src = n["parameters"].get("jsonBody", "")
    m = re.search(r"number:\s*'(\d+)'", src) or re.search(r"number:\s*\$json\.number", src)
    print(f"  {nome:<30} {m.group(1) if m and m.groups() else '(do Montar Alerta)'}")

if not aplicar:
    print("\n--- SIMULACAO, nada gravado ---"); sys.exit(0)

novo = req("PUT", f"workflows/{WID}", {"name": wf["name"], "nodes": wf["nodes"],
    "connections": wf["connections"], "settings": wf.get("settings", {})})
print(f"\nGRAVADO. versionId: {novo.get('versionId')}")
d = req("GET", f"workflows/{WID}"); DN = {n["name"]: n for n in d["nodes"]}
print(f"conferindo: {len(d['nodes'])} nos | active={d.get('active')}")
for nome in COMERCIAIS:
    jb = DN[nome]["parameters"]["jsonBody"]
    m = re.search(r"number:\s*'(\d+)'", jb)
    print(f"  {nome:<30} destino={m.group(1) if m else '?'} | link={'urlButton' in jb}")
