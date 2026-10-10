#!/usr/bin/env python3
"""Alerta de desconexao da Evolution por e-mail (decisao do dono, 2026-10-10).

Problema: quando o WhatsApp da loja cai, ninguem fica sabendo — o no
`Montar Alerta` monta o texto mas nao tem saida, e mesmo que tivesse, enviaria
pela propria instancia que caiu. Foi o que deixou a loja ~48 h parada (07-09/10).

A conexao oscila muito (62 quedas em 14 dias, quase todas de segundos), entao
alertar a cada "close" seria spam. Desenho:

  E Mensagem? (nao e mensagem) -> E Queda? (connection.update + state=close)
     -> Esperar 5 min -> Checar Conexao (GET /instance/connectionState)
     -> Ainda Caida? (state != open, ou a Evolution nem respondeu)
     -> Email Alerta Conexao (Gmail, credencial existente "Gmail account")

`Montar Alerta` continua onde esta (sem saida); nada no caminho de mensagens
muda. Funciona para qualquer loja: instancia, servidor e chave vem do proprio
webhook da Evolution.

  python3 aplicar_alerta_email_n8n.py              simula
  python3 aplicar_alerta_email_n8n.py --aplicar
  python3 aplicar_alerta_email_n8n.py --reverter
"""
import datetime, importlib.util, json, pathlib, sys, uuid

AQUI = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ia", AQUI / "aplicar_comandos_ia_n8n.py")
IAMOD = importlib.util.module_from_spec(spec); spec.loader.exec_module(IAMOD)
req, gravar, BK, WID = IAMOD.req, IAMOD.gravar, IAMOD.BK, IAMOD.WID
ESTADO = BK / "alerta_email_estado.json"

DESTINO = "eltoncasaccia@gmail.com"
ESPERA_MIN = 5
GMAIL = {"gmailOAuth2": {"id": "Wi24N8kw2GFRo3cr", "name": "Gmail account"}}
EMSG, QUEDA, ESPERAR, CHECAR, CAIDA, EMAIL = ("É Mensagem?", "É Queda?", "Esperar 5 min", "Checar Conexão",
                                             "Ainda Caída?", "Email Alerta Conexão")
WB = "$('Webhook').item.json.body"


def estado():
    return json.loads(ESTADO.read_text()) if ESTADO.exists() else {}


def salvar_estado(**kw):
    e = estado(); e.update(kw); ESTADO.write_text(json.dumps(e, indent=1)); ESTADO.chmod(0o600)


def cond(left, op, right="", tipo="string", single=False):
    o = {"type": tipo, "operation": op}
    if single: o["singleValue"] = True
    return {"id": str(uuid.uuid4()), "leftValue": left, "rightValue": right, "operator": o}


def no_if(nome, pos, conds):
    return {"name": nome, "type": "n8n-nodes-base.if", "typeVersion": 2.2, "id": str(uuid.uuid4()), "position": pos,
            "parameters": {"conditions": {"options": {"version": 2, "leftValue": "", "caseSensitive": True,
                                                      "typeValidation": "loose"},
                                          "conditions": conds, "combinator": "and"},
                           "looseTypeValidation": True, "options": {}}}


CORPO = (
    "=O WhatsApp da loja está DESCONECTADO há pelo menos " + str(ESPERA_MIN) + " minutos.\n\n"
    "Instância: {{ " + WB + ".instance }}\n"
    "Caiu em: {{ " + WB + ".date_time || '(sem horário no aviso)' }}\n"
    "Motivo informado pela Evolution: {{ " + WB + ".data?.statusReason ?? '(nenhum)' }}\n"
    "Estado agora: {{ $json.instance?.state || 'sem resposta da Evolution' }}\n\n"
    "Enquanto estiver assim, NENHUMA mensagem chega ao sistema: leads não são distribuídos.\n\n"
    "Causa mais comum: o aparelho foi desvinculado (troca de celular, WhatsApp reinstalado, "
    "'desconectar dispositivos'). Para reconectar, gere um código de pareamento na Evolution e digite "
    "no celular da loja em WhatsApp > Dispositivos conectados > Conectar com número de telefone "
    "(passo a passo no RUNBOOK do incidente NaPista, complemento de 09/10).\n\n"
    "— alerta automático do lead-distributor (n8n)"
)


def transformar(wf):
    N = {n["name"]: n for n in wf["nodes"]}; C = wf["connections"]
    if QUEDA in N: sys.exit("erro: alerta ja aplicado")
    if [x["node"] for x in C[EMSG]["main"][0]] != ["Montar Alerta"]:
        sys.exit(f"erro: saida 'nao e mensagem' de {EMSG} mudou: {C[EMSG]['main'][0]}")
    x, y = N["Montar Alerta"]["position"]; y += 200
    wf["nodes"] += [
        no_if(QUEDA, [x, y], [cond("={{ " + WB + ".event }}", "equals", "connection.update"),
                              cond("={{ " + WB + ".data?.state }}", "equals", "close")]),
        {"name": ESPERAR, "type": "n8n-nodes-base.wait", "typeVersion": 1.1, "id": str(uuid.uuid4()),
         "webhookId": str(uuid.uuid4()), "position": [x + 220, y],
         "parameters": {"resume": "timeInterval", "amount": ESPERA_MIN, "unit": "minutes"}},
        {"name": CHECAR, "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.3, "id": str(uuid.uuid4()),
         "position": [x + 440, y], "onError": "continueRegularOutput",
         "parameters": {"url": "={{ " + WB + ".server_url }}/instance/connectionState/{{ " + WB + ".instance }}",
                        "sendHeaders": True,
                        "headerParameters": {"parameters": [{"name": "apikey", "value": "={{ " + WB + ".apikey }}"}]},
                        "options": {"timeout": 10000}}},
        no_if(CAIDA, [x + 660, y], [cond("={{ $json.instance?.state || '' }}", "notEquals", "open")]),
        {"name": EMAIL, "type": "n8n-nodes-base.gmail", "typeVersion": 2.1, "id": str(uuid.uuid4()),
         "position": [x + 880, y], "credentials": GMAIL, "onError": "continueRegularOutput",
         "parameters": {"resource": "message", "operation": "send", "sendTo": DESTINO,
                        "subject": "=⚠️ WhatsApp da loja DESCONECTADO — {{ " + WB + ".instance }}",
                        "emailType": "text", "message": CORPO, "options": {"appendAttribution": False}}},
    ]
    C[EMSG]["main"][0] = [{"node": "Montar Alerta", "type": "main", "index": 0},
                          {"node": QUEDA, "type": "main", "index": 0}]
    C[QUEDA] = {"main": [[{"node": ESPERAR, "type": "main", "index": 0}], []]}
    C[ESPERAR] = {"main": [[{"node": CHECAR, "type": "main", "index": 0}]]}
    C[CHECAR] = {"main": [[{"node": CAIDA, "type": "main", "index": 0}]]}
    C[CAIDA] = {"main": [[{"node": EMAIL, "type": "main", "index": 0}], []]}
    return [f"  + {QUEDA}  (connection.update com state=close)",
            f"  + {ESPERAR}  ({ESPERA_MIN} minutos)",
            f"  + {CHECAR}  (GET connectionState; falha conta como caida)",
            f"  + {CAIDA}  (state != open)",
            f"  + {EMAIL}  (Gmail -> {DESTINO})",
            f"  ~ {EMSG} (nao e mensagem) -> Montar Alerta + {QUEDA}"]


def checar(wf, antes):
    N = {n["name"]: n for n in wf["nodes"]}; C = wf["connections"]; erros = []
    if len(wf["nodes"]) != len(antes["nodes"]) + 5: erros.append("numero de nos inesperado")
    if C[EMSG]["main"][1] != antes["connections"][EMSG]["main"][1]: erros.append("caminho de mensagens mudou")
    if [x["node"] for x in C[CAIDA]["main"][0]] != [EMAIL]: erros.append("alerta nao chega ao e-mail")
    if N[EMAIL]["parameters"]["sendTo"] != DESTINO: erros.append("destino errado")
    mudou = [n["name"] for n in antes["nodes"] if json.dumps(n, sort_keys=True) != json.dumps(N.get(n["name"]), sort_keys=True)]
    if mudou: erros.append(f"nos existentes alterados: {mudou}")
    outras = {k: v for k, v in antes["connections"].items() if k != EMSG}
    if any(C.get(k) != v for k, v in outras.items()): erros.append("outras conexoes mudaram")
    return erros


def main():
    a = sys.argv[1:]
    if "--reverter" in a:
        snap = estado().get("snapshot")
        if not snap: sys.exit("erro: nao ha snapshot salvo")
        wf = json.loads(pathlib.Path(snap).read_text()); d = gravar(wf)
        print(f"REVERTIDO para {wf['versionId']}. nova {d['versionId']} | ativo={d['active']}")
        return
    wf = req("GET", f"workflows/{WID}"); antes = json.loads(json.dumps(wf))
    print(f"antes: versionId {wf['versionId']} | {len(wf['nodes'])} nos\n\nmudancas:")
    print("\n".join(transformar(wf)))
    erros = checar(wf, antes)
    print("\ntravas:", "todas ok" if not erros else ""); [print(f"  !! {e}") for e in erros]
    if erros: sys.exit("nada gravado")
    if "--aplicar" not in a:
        print("\n--- SIMULACAO, nada gravado ---"); return
    agora = datetime.datetime.now()
    snap = BK / f"workflow_{WID}_{antes['versionId']}_{agora:%Y%m%d-%H%M%S}.json"
    snap.write_text(json.dumps(antes)); snap.chmod(0o600)
    salvar_estado(snapshot=str(snap), versao_antes=antes["versionId"])
    d = gravar(wf)
    print(f"\nsnapshot: {snap}\nGRAVADO. versionId {antes['versionId']} -> {d['versionId']} | ativo={d['active']} | ativa=nova? {d['activeVersionId'] == d['versionId']}")
    erros = checar(d, antes)
    print("travas no que ficou gravado:", "todas ok" if not erros else erros)
    salvar_estado(versao_depois=d["versionId"], aplicado_em=agora.isoformat())


if __name__ == "__main__":
    main()
