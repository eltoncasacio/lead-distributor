#!/usr/bin/env python3
"""Aplica um arquivo SQL no Supabase de PRODUCAO (API de gestao), numa transacao.

  python3 sql/aplicar_sql_producao.py sql/portaria/FIX_portaria_sombra.sql

O arquivo deve ter testes no Docker passando antes (ver o README da pasta dele).
Requer SUPABASE_ACCESS_TOKEN_PROD no .env."""
import json, pathlib, sys, urllib.error, urllib.request
RAIZ = pathlib.Path(__file__).resolve().parents[1]
ENV = dict(l.split("=", 1) for l in (RAIZ / ".env").read_text().splitlines() if "=" in l and not l.startswith("#"))
TOKEN = ENV.get("SUPABASE_ACCESS_TOKEN_PROD", "").strip()
if not TOKEN or len(sys.argv) < 2: sys.exit("uso: aplicar_sql_producao.py <arquivo.sql>  (precisa de SUPABASE_ACCESS_TOKEN_PROD)")
sql = pathlib.Path(sys.argv[1]).read_text()
r = urllib.request.Request("https://api.supabase.com/v1/projects/drtdctpwxkqqnhnikpwz/database/query", method="POST",
                           data=json.dumps({"query": sql}).encode(),
                           headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json", "User-Agent": "lead-distributor"})
try:
    with urllib.request.urlopen(r, timeout=120) as x: print("APLICADO:", sys.argv[1], "|", x.read()[:200].decode())
except urllib.error.HTTPError as e:
    sys.exit(f"ERRO (nada aplicado — transacao): {e.read().decode()[:800]}")
