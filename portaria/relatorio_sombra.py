#!/usr/bin/env python3
"""Relatorio do modo sombra da Portaria (somente leitura).

  python3 portaria/relatorio_sombra.py            ultimos 7 dias
  python3 portaria/relatorio_sombra.py 14         ultimos 14 dias

Mostra o que a Portaria TERIA ignorado (decisao = ignorar), com o texto e o
motivo, para o dono decidir se liga de verdade. Le via service_role do .env."""
import collections, os, sys
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from supabase import create_client

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(RAIZ, ".env"))
c = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
dias = int(sys.argv[1]) if len(sys.argv) > 1 else 7
desde = (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat()
lojas = {l["id"]: l["nome"] for l in c.table("lojas").select("id,nome").execute().data}
rows = c.table("portaria_sombra").select("*").gte("criado_em", desde).order("criado_em").execute().data

print(f"PORTARIA (sombra) — ultimos {dias} dias — {len(rows)} mensagens de numero novo classificadas\n")
por = collections.Counter((lojas.get(r["loja_id"], "?"), r["classificacao"]) for r in rows)
for (loja, cl), n in sorted(por.items()): print(f"  {loja:20} {cl:9} {n}")
travas = collections.Counter(r["trava"] for r in rows if r["trava"])
if travas: print("  travas acionadas:", dict(travas))

ign = [r for r in rows if r["decisao"] == "ignorar"]
print(f"\nTERIA IGNORADO: {len(ign)}  (confira se algum era cliente)\n")
for r in ign:
    print(f"- {r['criado_em'][:16]} {lojas.get(r['loja_id'], '?')} | de ...{r['remetente_numero'][-4:]}")
    print(f"    texto : {' '.join((r['texto'] or '').split())[:200]}")
    print(f"    motivo: {r['motivo']}  | trecho: {r['trecho_evidencia']!r}")
usos = c.table("ia_uso").select("dia,chamadas").eq("remetente_chave", "portaria").gte("dia", desde[:10]).execute().data
print(f"\nchamadas de IA da Portaria no periodo: {sum(u['chamadas'] for u in usos)} (~US$ {sum(u['chamadas'] for u in usos)*0.0002:.3f})")
