"""Monitor SOMENTE LEITURA de todas as lojas ativas.

Responde, loja por loja, "esta recebendo e distribuindo?" — o que a
auditoria_producao.py (so Renato Motors) nao cobre.

    python3 monitor_lojas.py          # relatorio completo
    python3 monitor_lojas.py --curto  # so os alertas
    python3 monitor_lojas.py --curto --avisar  # agendado: avisa o dono

Sai com codigo 1 quando ha alerta. NAO escreve no banco. NAO imprime credencial.

--avisar avisa o DONO, nunca a loja: notificacao no Mac e, se o .env tiver
ALERTA_INSTANCIA/ALERTA_INSTANCIA_KEY (numero exclusivo do sistema), WhatsApp
para DONO_WHATSAPP. Instancia de loja e recusada: o que sai por ela fica no
celular da loja — em 2026-10-17 um alerta saiu pela Renato Motors e o Renato
viu o nome de outro cliente.
So avisa quando o conjunto de alertas muda — o ultimo enviado fica em
.monitor_estado (fora do git) — e avisa de novo quando tudo normaliza.
Roda de hora em hora pelo launchd: ver docs/dev/monitor-lojas.md.

Criado em 2026-10-17, com Fitcar e TbMotors entrando no mesmo dia.
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_KEY")
if not url or not key:
    raise SystemExit("credenciais nao encontradas no .env")

EVOLUTION = "https://evolution.yavoh.cloud"
BRT = timezone(timedelta(hours=-3))
AGORA = datetime.now(timezone.utc)
# Silencio so conta em horario comercial — de madrugada ninguem escreve.
HORARIO_COMERCIAL = 8 <= AGORA.astimezone(BRT).hour < 20
SILENCIO_HORAS = 4

sb = create_client(url, key)
CURTO = "--curto" in sys.argv
AVISAR = "--avisar" in sys.argv
DONO_WHATSAPP = os.environ.get("DONO_WHATSAPP", "5519996977453")
ALERTA_INSTANCIA = os.environ.get("ALERTA_INSTANCIA")
ALERTA_INSTANCIA_KEY = os.environ.get("ALERTA_INSTANCIA_KEY")
ESTADO = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".monitor_estado")


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def idade(s):
    d = ts(s)
    if not d:
        return "nunca"
    h = (AGORA - d).total_seconds() / 3600
    return "%.0f min" % (h * 60) if h < 1 else "%.1f h" % h


def conexao(loja):
    try:
        r = requests.get("%s/instance/connectionState/%s" % (EVOLUTION, loja["instancia_evolution"]),
                         headers={"apikey": loja.get("evolution_api_key") or ""}, timeout=15)
        return (r.json().get("instance") or {}).get("state") or "?(%s)" % r.status_code
    except Exception as e:
        return "erro: %s" % type(e).__name__


def cont(tabela, loja_id, desde, coluna="criado_em", **extra):
    q = sb.table(tabela).select("id", count="exact").eq("loja_id", loja_id).gte(coluna, desde).limit(1)
    for k, v in extra.items():
        q = q.is_(k[:-4], v) if k.endswith("__is") else q.not_.is_(k[:-8], v)
    return q.execute().count


alertas = []
d24 = (AGORA - timedelta(hours=24)).isoformat()
d1 = (AGORA - timedelta(hours=1)).isoformat()

if not CURTO:
    print("=" * 72)
    print("MONITOR DE LOJAS — %s (BRT)" % AGORA.astimezone(BRT).strftime("%Y-%m-%d %H:%M"))
    print("=" * 72)

lojas = sb.table("lojas").select("*").eq("ativa", True).order("criado_em").execute().data or []
for loja in lojas:
    lid, nome = loja["id"], loja["nome"]

    def alerta(msg):
        alertas.append("%s: %s" % (nome, msg))

    estado = conexao(loja)
    if estado != "open":
        alerta("WhatsApp DESCONECTADO (estado=%s) — reconectar por QR/codigo" % estado)

    vends = sb.table("vendedores").select("id,nome,status,numero_whatsapp").eq("loja_id", lid).execute().data or []
    ativos = [v for v in vends if v.get("status") == "ativo"]
    if not ativos:
        alerta("nenhum vendedor ativo — todo lead fica sem dono")
    prox = loja.get("proximo_vendedor_id")
    if prox and prox not in {v["id"] for v in ativos}:
        alerta("proximo_vendedor_id aponta para vendedor inativo ou de outra loja")

    msg_ult = (sb.table("mensagens_recebidas").select("recebido_em").eq("loja_id", lid)
               .order("recebido_em", desc=True).limit(1).execute().data or [{}])[0].get("recebido_em")
    lead_ult = (sb.table("leads").select("criado_em").eq("loja_id", lid)
                .order("criado_em", desc=True).limit(1).execute().data or [{}])[0].get("criado_em")
    m24, m1 = cont("mensagens_recebidas", lid, d24, "recebido_em"), cont("mensagens_recebidas", lid, d1, "recebido_em")
    l24, l1 = cont("leads", lid, d24), cont("leads", lid, d1)
    orfaos = cont("leads", lid, d24, vendedor_id__is="null")
    erros = cont("mensagens_recebidas", lid, d24, "recebido_em", erro__not_is="null")

    # Mensagem nao chegar e o sinal mais cedo: vem antes do lead e nao depende de parser.
    if HORARIO_COMERCIAL and estado == "open":
        d = ts(msg_ult)
        if not d or AGORA - d > timedelta(hours=SILENCIO_HORAS):
            alerta("nenhuma mensagem %s em horario comercial — webhook/n8n parado?" % (
                "desde que conectou" if not d else "ha " + idade(msg_ult)))
    if orfaos:
        alerta("%d lead(s) sem vendedor nas ultimas 24h" % orfaos)
    if erros:
        alerta("%d mensagem(ns) com erro registrado nas ultimas 24h" % erros)

    # Regressao do filtro de grupo (2026-10-17): ID de grupo virando "cliente".
    suspeitos = [l for l in (sb.table("leads").select("numero_cliente").eq("loja_id", lid)
                             .gte("criado_em", d24).execute().data or [])
                 if "-" in (l.get("numero_cliente") or "") or len(l.get("numero_cliente") or "") > 13]
    if suspeitos:
        alerta("%d lead(s) com numero de grupo — filtro @g.us falhou?" % len(suspeitos))

    if not CURTO:
        print("\n%s (%s)" % (nome, loja["instancia_evolution"]))
        print("    whatsapp...........: %s" % estado)
        print("    vendedores ativos..: %d de %d (%s)" % (len(ativos), len(vends), ", ".join(v["nome"] for v in ativos)))
        print("    mensagens 1h / 24h.: %d / %d   ultima ha %s" % (m1, m24, idade(msg_ult)))
        print("    leads     1h / 24h.: %d / %d   ultimo ha %s" % (l1, l24, idade(lead_ult)))
        print("    sem vendedor 24h...: %d    com erro 24h: %d" % (orfaos, erros))

if not CURTO:
    print("\n" + "=" * 72)
    if not HORARIO_COMERCIAL:
        print("(fora do horario comercial: silencio de mensagens nao gera alerta)")


def avisar_mac(titulo, texto):
    import subprocess
    try:
        aspas = lambda t: '"%s"' % t.replace("\\", "\\\\").replace('"', '\\"')
        r = subprocess.run(["osascript", "-e", 'display notification %s with title %s sound name "Glass"'
                            % (aspas(texto), aspas(titulo))], timeout=10, capture_output=True)
        return r.returncode == 0
    except Exception:
        return False


def avisar_whatsapp(texto):
    if not (ALERTA_INSTANCIA and ALERTA_INSTANCIA_KEY):
        return False
    if ALERTA_INSTANCIA in {l["instancia_evolution"] for l in lojas}:
        print("!! ALERTA_INSTANCIA e instancia de loja — alerta NAO enviado por WhatsApp")
        return False
    try:
        r = requests.post("%s/message/sendText/%s" % (EVOLUTION, ALERTA_INSTANCIA),
                          headers={"apikey": ALERTA_INSTANCIA_KEY},
                          json={"number": DONO_WHATSAPP, "text": texto}, timeout=20)
        return r.status_code < 300
    except Exception:
        return False


if AVISAR:
    try:
        anterior = json.load(open(ESTADO))
    except Exception:
        anterior = []
    if sorted(alertas) != sorted(anterior):
        hora = AGORA.astimezone(BRT).strftime("%d/%m %H:%M")
        if alertas:
            titulo, corpo = "⚠️ Monitor de lojas", "\n".join(alertas)
        else:
            titulo, corpo = "✅ Monitor de lojas", "Tudo normalizado: %d loja(s) sem alerta." % len(lojas)
        mac = avisar_mac(titulo, corpo)
        wpp = avisar_whatsapp("*%s* (%s)\n\n%s" % (titulo, hora, corpo))
        if mac or wpp:
            json.dump(alertas, open(ESTADO, "w"))

if alertas:
    print("ALERTAS (%d):" % len(alertas))
    for a in alertas:
        print("  !! " + a)
    sys.exit(1)
print("OK — %d loja(s) ativa(s), nenhum alerta" % len(lojas))
