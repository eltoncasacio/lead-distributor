#!/usr/bin/env python3
"""Aplica FIX_comandos_whatsapp.sql no Supabase de producao, numa transacao,
e confere o resultado. Ou desfaz, com --reverter (ROLLBACK_comandos_whatsapp.sql).

  python3 sql/comandos_whatsapp/aplicar_producao.py              aplica e confere
  python3 sql/comandos_whatsapp/aplicar_producao.py --conferir   so confere
  python3 sql/comandos_whatsapp/aplicar_producao.py --reverter   desfaz

Requer no .env: SUPABASE_ACCESS_TOKEN_PROD (token de conta com acesso ao
projeto de producao) e LOJA_ID. Usa a API de gestao do Supabase
(/v1/projects/{ref}/database/query), que roda SQL arbitrario.

O FIX so cria funcoes e indices novos — nada no fluxo atual chama
executar_comando ate o n8n ser alterado. Se houver nome ou telefone repetido,
o proprio FIX aborta e a transacao inteira volta."""
import json, pathlib, sys, urllib.error, urllib.request

AQUI = pathlib.Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
ENV = {}
for linha in (RAIZ / ".env").read_text().splitlines():
    if "=" in linha and not linha.lstrip().startswith("#"):
        k, v = linha.split("=", 1)
        ENV[k.strip()] = v.strip().strip('"').strip("'")
TOKEN, LOJA = ENV.get("SUPABASE_ACCESS_TOKEN_PROD"), ENV.get("LOJA_ID")
if not (TOKEN and LOJA): sys.exit("erro: .env precisa de SUPABASE_ACCESS_TOKEN_PROD e LOJA_ID")
PROJETO = "drtdctpwxkqqnhnikpwz"
GERENTE_TESTE = "5519999746219"   # Elton, gerente cadastrado em 09/10


def sql(q):
    r = urllib.request.Request(f"https://api.supabase.com/v1/projects/{PROJETO}/database/query", method="POST",
                               data=json.dumps({"query": q}).encode(),
                               headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json",
                                        "User-Agent": "lead-distributor"})
    try:
        with urllib.request.urlopen(r, timeout=120) as x: return json.loads(x.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"ERRO do banco (HTTP {e.code}) — nada foi aplicado:\n{e.read().decode()[:800]}")


def conferir():
    c = sql("""select
      (select count(*) from pg_proc where pronamespace='public'::regnamespace and proname in
        ('normalizar_nome','somente_digitos','normalizar_telefone_br','chave_telefone','formatar_telefone','_cmd_resp','executar_comando')) as funcoes,
      (select count(*) from pg_indexes where schemaname='public' and indexname in ('uq_vendedores_loja_nome','uq_vendedores_loja_telefone')) as indices""")[0]
    print(f"funcoes: {c['funcoes']}/7 | indices: {c['indices']}/2")
    if c["funcoes"] != 7: return False
    g = sql("""select has_function_privilege('anon','public.executar_comando(uuid,text,text)','EXECUTE') as anon,
                      has_function_privilege('authenticated','public.executar_comando(uuid,text,text)','EXECUTE') as authenticated,
                      has_function_privilege('service_role','public.executar_comando(uuid,text,text)','EXECUTE') as service_role""")[0]
    print(f"quem executa executar_comando: anon={g['anon']} authenticated={g['authenticated']} service_role={g['service_role']}")
    m = sql(f"select public.executar_comando('{LOJA}'::uuid, '{GERENTE_TESTE}', 'menu') as r")[0]["r"]
    print(f"\n'menu' pelo gerente {GERENTE_TESTE}: papel={m.get('papel')} acao={m.get('acao')}\n{m.get('resposta')}")
    ok = c["indices"] == 2 and not g["anon"] and not g["authenticated"] and g["service_role"] and m.get("papel") == "gerente"
    print("\nCONFERENCIA:", "OK" if ok else "!! algo nao bateu")
    return ok


if "--conferir" in sys.argv:
    conferir()
elif "--reverter" in sys.argv:
    sql("BEGIN;\n" + (AQUI / "ROLLBACK_comandos_whatsapp.sql").read_text() + "\nCOMMIT;")
    print("REVERTIDO.")
    c = sql("select count(*) as n from pg_proc where pronamespace='public'::regnamespace and proname='executar_comando'")[0]
    print(f"executar_comando existe? {c['n'] > 0}")
else:
    sql("BEGIN;\n" + (AQUI / "FIX_comandos_whatsapp.sql").read_text() + "\nCOMMIT;")
    print("APLICADO.\n")
    conferir()
