#!/usr/bin/env python3
"""Roda sql/fase_b/teste_isolamento.sql no banco de PRODUCAO, pela API de gestao
do Supabase. O teste se desfaz sozinho (sempre termina em RAISE EXCEPTION, que
desfaz a transacao). Depois confere que nao sobrou nada da loja de teste.

Requer no .env: SUPABASE_ACCESS_TOKEN_PROD e LOJA_ID."""
import json, pathlib, re, sys, urllib.error, urllib.request

AQUI = pathlib.Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
ENV = dict(l.split("=", 1) for l in (RAIZ / ".env").read_text().splitlines() if "=" in l and not l.startswith("#"))
TOKEN, LOJA = ENV.get("SUPABASE_ACCESS_TOKEN_PROD", "").strip(), ENV.get("LOJA_ID", "").strip()
if not (TOKEN and LOJA): sys.exit("erro: .env precisa de SUPABASE_ACCESS_TOKEN_PROD e LOJA_ID")


def sql(q):
    r = urllib.request.Request("https://api.supabase.com/v1/projects/drtdctpwxkqqnhnikpwz/database/query", method="POST",
                               data=json.dumps({"query": q}).encode(),
                               headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json", "User-Agent": "lead-distributor"})
    try:
        with urllib.request.urlopen(r, timeout=120) as x: return True, json.loads(x.read())
    except urllib.error.HTTPError as e:
        return False, e.read().decode()


ok, out = sql((AQUI / "teste_isolamento.sql").read_text().replace(":LOJA_REAL", LOJA))
msg = out if isinstance(out, str) else json.dumps(out)
try: msg = json.loads(msg).get("message", msg)
except (ValueError, AttributeError): pass
m = re.search(r"FASEB_(OK|FALHOU)\s*(.*)", msg, re.S)
if not m:
    print("resultado inesperado (o bloco deveria sempre terminar em FASEB_OK/FASEB_FALHOU):\n", msg[:1500]); sys.exit(2)
print(f"FASE B: {m.group(1)}")
detalhe = m.group(2).split("CONTEXT:")[0].strip()
try: print(json.dumps(json.loads(detalhe), ensure_ascii=False, indent=1))
except ValueError: print(detalhe)

_, sobra = sql("select (select count(*) from lojas where instancia_evolution = 'teste-isolamento-faseb') lojas, "
               "(select count(*) from vendedores where numero_whatsapp in ('5511911111111','5511922222222','5511933333334')) vendedores, "
               "(select count(*) from leads where numero_cliente like '551194444444%' or nome_cliente = 'Cliente da RM') leads")
print("sobrou algo da loja de teste?", sobra)
sys.exit(0 if m.group(1) == "OK" else 1)
