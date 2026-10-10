"""Auditoria SOMENTE LEITURA do estado de producao.

Responde "o sistema esta funcionando?" sem abrir o Dashboard: ritmo de leads,
coerencia da fila, leads orfaos, silencio por origem, e a tabela de mensagens.

    source venv/bin/activate
    python3 auditoria_producao.py

NAO escreve nada. NAO imprime credencial. Le direto do Supabase com a
service_role do .env — nao passa por utils/queries.py de proposito, para
auditar o banco e nao a camada que le o banco.

Criado em 2026-09-23, quando descobriu que iCarros estava mudo ha 122 dias
e ninguem tinha notado.
"""
import os
from collections import Counter
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from supabase import create_client

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_KEY")
if not url or not key:
    raise SystemExit("credenciais nao encontradas no .env")

sb = create_client(url, key)
LOJA = os.environ.get("LOJA_ID")
if not LOJA:
    raise SystemExit("LOJA_ID nao encontrado no .env")
HOJE = datetime.now(timezone.utc)


def cont(tabela, **filtros):
    q = sb.table(tabela).select("id", count="exact").limit(1)
    for k, v in filtros.items():
        if k.endswith("__gte"):
            q = q.gte(k[:-5], v)
        elif k.endswith("__is"):
            q = q.is_(k[:-4], v)
        else:
            q = q.eq(k, v)
    return q.execute().count


def paginado(tabela, select, **filtros):
    """PostgREST corta em 1000 linhas — pagina para nao contar errado."""
    out, passo, ini = [], 1000, 0
    while True:
        q = sb.table(tabela).select(select)
        for k, v in filtros.items():
            q = q.gte(k[:-5], v) if k.endswith("__gte") else q.eq(k, v)
        r = q.range(ini, ini + passo - 1).execute()
        out.extend(r.data or [])
        if len(r.data or []) < passo:
            return out
        ini += passo


print("=" * 72)
print("AUDITORIA RENATO MOTORS — %s UTC" % HOJE.strftime("%Y-%m-%d %H:%M"))
print("=" * 72)

# ---------- 1. a loja existe e esta ativa ----------
loja = sb.table("lojas").select("*").eq("id", LOJA).execute().data
if not loja:
    raise SystemExit("!! LOJA NAO ENCONTRADA")
loja = loja[0]
print("\n[1] LOJA")
print("    nome...............: %s" % loja.get("nome"))
print("    ativa..............: %s" % loja.get("ativa"))
print("    instancia_evolution: %s" % loja.get("instancia_evolution"))
print("    proximo_vendedor_id: %s" % loja.get("proximo_vendedor_id"))
print("    ultima_distribuicao: %s" % loja.get("ultima_distribuicao_em"))

# ---------- 2. vendedores e coerencia do ponteiro ----------
vends = sb.table("vendedores").select("*").eq("loja_id", LOJA).execute().data or []
ativos = [v for v in vends if v.get("status") == "ativo"]
print("\n[2] VENDEDORES")
print("    total: %d | ativos: %d | inativos: %d | removidos: %d" % (
    len(vends), len(ativos),
    sum(1 for v in vends if v.get("status") == "inativo"),
    sum(1 for v in vends if v.get("status") == "removido")))
prox = loja.get("proximo_vendedor_id")
if not ativos:
    print("    !! NENHUM VENDEDOR ATIVO — nada seria distribuido")
elif prox and prox in [v["id"] for v in ativos]:
    nome = next(v["nome"] for v in ativos if v["id"] == prox)
    print("    ok ponteiro da fila aponta para ativo: %s" % nome)
elif prox:
    alvo = next((v for v in vends if v["id"] == prox), None)
    print("    !! ponteiro aponta para NAO-ATIVO: %s (%s)" % (
        alvo and alvo.get("nome"), alvo and alvo.get("status")))
else:
    print("    ~ ponteiro nulo (cai no primeiro ativo)")

# distribuir_lead() so filtra por status='ativo' — nao checa numero_whatsapp.
# Um ativo sem numero vai entrar no rodizio, o lead e' criado normalmente,
# e o encaminhamento no n8n falha calado (mesmo padrao do incidente NaPista).
sem_whatsapp = [v for v in ativos if not v.get("numero_whatsapp")]
if sem_whatsapp:
    print("    !! %d vendedor(es) ATIVO(S) sem numero_whatsapp — recebe lead e o cliente fica sem retorno:" % len(sem_whatsapp))
    for v in sem_whatsapp:
        print("       - %s (id=%s)" % (v.get("nome"), v["id"]))

# ---------- 3. leads: volume e ritmo ----------
total = cont("leads", loja_id=LOJA)
d30 = paginado("leads", "id,criado_em,origem,vendedor_id,status_lead",
               loja_id=LOJA, criado_em__gte=(HOJE - timedelta(days=30)).isoformat())
print("\n[3] LEADS")
print("    total historico....: %d" % total)
print("    ultimos 30 dias....: %d" % len(d30))

por_dia = Counter((l["criado_em"] or "")[:10] for l in d30)
print("\n    ultimos 14 dias:")
for i in range(13, -1, -1):
    dia = (HOJE - timedelta(days=i)).strftime("%Y-%m-%d")
    n = por_dia.get(dia, 0)
    barra = "#" * min(n, 50)
    marca = "   <= HOJE" if i == 0 else ("   !! zero" if n == 0 else "")
    print("      %s  %3d %s%s" % (dia, n, barra, marca))

ult = sb.table("leads").select("criado_em,nome_cliente,origem").eq(
    "loja_id", LOJA).order("criado_em", desc=True).limit(1).execute().data
if ult:
    q = ult[0]["criado_em"]
    try:
        delta = HOJE - datetime.fromisoformat(q.replace("Z", "+00:00"))
        idade = "%.1f h atras" % (delta.total_seconds() / 3600)
    except Exception:
        idade = "?"
    print("\n    ultimo lead........: %s (%s) origem=%s  -> %s" % (
        q, ult[0].get("nome_cliente"), ult[0].get("origem"), idade))

# ---------- 4. origens ----------
print("\n[4] ORIGENS (30 dias)")
for o, n in Counter(l.get("origem") or "(vazio)" for l in d30).most_common():
    print("      %-20s %4d" % (o, n))

nap = [l for l in d30 if (l.get("origem") or "").lower().startswith("napista")]
print("    NaPista nos ultimos 30 dias: %d %s" % (
    len(nap), "(esperado ~0 — canal na caixa errada)" if len(nap) < 3 else ""))

# ---------- 5. leads orfaos ----------
orfaos = [l for l in d30 if not l.get("vendedor_id")]
print("\n[5] LEADS SEM VENDEDOR (30 dias): %d %s" % (
    len(orfaos), "!! distribuicao falhando" if orfaos else "ok"))

# ---------- 6. mensagens_recebidas (tabela nova de ontem) ----------
print("\n[6] MENSAGENS_RECEBIDAS")
try:
    tm = cont("mensagens_recebidas", loja_id=LOJA)
    pend = cont("mensagens_recebidas", loja_id=LOJA, revisado_em__is="null")
    print("    total: %d | pendentes de revisao: %d" % (tm, pend))
    u = sb.table("mensagens_recebidas").select(
        "recebido_em,origem_detectada,telefone_extraido,decisao").eq(
        "loja_id", LOJA).order("recebido_em", desc=True).limit(5).execute().data or []
    if not u:
        print("    !! nenhuma mensagem registrada — o no 'Registrar Mensagem' pode nao estar gravando")
    for m in u:
        print("      %s | %-14s | tel=%-14s | %s" % (
            (m.get("recebido_em") or "")[:16], m.get("origem_detectada"),
            m.get("telefone_extraido") or "-", m.get("decisao") or "-"))
except Exception as e:
    print("    !! erro ao ler: %s" % e)

# ---------- 7. atividades ----------
print("\n[7] ATIVIDADES RECENTES")
for a in (sb.table("atividades").select("criado_em,tipo,descricao").eq(
        "loja_id", LOJA).order("criado_em", desc=True).limit(8).execute().data or []):
    print("      %s | %-28s | %s" % (
        (a.get("criado_em") or "")[:16], a.get("tipo"), (a.get("descricao") or "")[:52]))

# ---------- 8. gerentes ----------
g = sb.table("gerentes").select("id,nome,ativo").eq("loja_id", LOJA).execute().data or []
print("\n[8] GERENTES: %d (ativos: %d)" % (len(g), sum(1 for x in g if x.get("ativo"))))

# ---------- 9. isolamento: existe outra loja? ----------
todas = sb.table("lojas").select("id,nome,ativa").execute().data or []
print("\n[9] LOJAS NA BASE: %d" % len(todas))
for l in todas:
    print("      %s | ativa=%s | %s" % (
        l["id"][:8], l.get("ativa"), l.get("nome")))

# ---------- 10. silencio por origem — o check que mais importa ----------
# Foi assim que a NaPista morreu por 6 semanas sem ninguem ver.
print("\n[10] SILENCIO POR ORIGEM (historico completo)")
todos, ini = [], 0
while True:
    r = (sb.table("leads").select("criado_em,origem").eq("loja_id", LOJA)
         .order("criado_em", desc=True).range(ini, ini + 999).execute())
    todos += r.data or []
    if len(r.data or []) < 1000:
        break
    ini += 1000

ultimo, tot = {}, Counter()
for l in todos:
    o = l.get("origem") or "(vazio)"
    tot[o] += 1
    ultimo.setdefault(o, l["criado_em"])

print("    %-20s %6s  %-18s %s" % ("ORIGEM", "TOTAL", "ULTIMO LEAD", "SILENCIO"))
print("    " + "-" * 64)
alerta = []
for o in sorted(ultimo, key=lambda k: ultimo[k], reverse=True):
    try:
        dias = (HOJE - datetime.fromisoformat(ultimo[o].replace("Z", "+00:00"))).days
    except Exception:
        dias = None
    flag = ""
    if isinstance(dias, int) and dias >= 30:
        flag = "  <<< MORTA"
        alerta.append((o, dias))
    elif isinstance(dias, int) and dias >= 14:
        flag = "  <<  quieta"
    print("    %-20s %6d  %-18s %s dias%s" % (o, tot[o], ultimo[o][:16], dias, flag))

if alerta:
    print("\n    !! %d origem(ns) sem um unico lead ha 30+ dias:" % len(alerta))
    for o, dias in alerta:
        print("       - %s (%d dias)" % (o, dias))
    print("       Degrau, nao queda gradual, costuma ser parser quebrado")
    print("       ou plano cancelado. So o dono sabe dizer qual.")

print("\n" + "=" * 72)
