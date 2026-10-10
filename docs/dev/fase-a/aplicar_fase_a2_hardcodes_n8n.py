#!/usr/bin/env python3
"""Fase A2: tirar a Renato Motors fixa dos alertas do n8n (2026-10-10).

Ver docs/dev/fase-a-tirar-hardcodes-n8n.md. Decisao do dono: alertas de lead
continuam indo para o numero dele.

  Alerta Lead Nao Distribuido   URL/instancia/chave fixas -> lidas de Normaliza Dados
                                (sai pela instancia da loja da mensagem; destino: dono)
  Alerta NaPista Sem Telefone   idem (continua desativado, decisao do dono)
  Alerta Loja Nao Encontrada    WhatsApp fixo -> E-MAIL ao dono. Pela instancia da
                                mensagem nao daria: e exatamente a instancia que o
                                sistema nao conhece.
  Montar Alerta,                codigo morto (sem saida / sem entrada) com chave fixa,
  Enviar Alerta Conexao         substituido pelo alerta de desconexao por e-mail -> removidos

Fica para a loja 2: Extrai Dados NaPista (e-mail nao tem instancia; exige
lojas.email_leads). Ver o change-set.

  python3 aplicar_fase_a2_hardcodes_n8n.py              simula
  python3 aplicar_fase_a2_hardcodes_n8n.py --aplicar
  python3 aplicar_fase_a2_hardcodes_n8n.py --reverter
"""
import datetime, importlib.util, json, pathlib, re, sys, uuid

AQUI = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ia", AQUI / "aplicar_comandos_ia_n8n.py")
IAMOD = importlib.util.module_from_spec(spec); spec.loader.exec_module(IAMOD)
req, gravar, BK, WID = IAMOD.req, IAMOD.gravar, IAMOD.BK, IAMOD.WID
ESTADO = BK / "fase_a2_estado.json"
GMAIL = {"gmailOAuth2": {"id": "Wi24N8kw2GFRo3cr", "name": "Gmail account"}}
DESTINO_EMAIL = "eltoncasaccia@gmail.com"

ND = "$('Normaliza Dados').item.json"
URL = "={{ " + ND + ".evolutionServerUrl }}/message/sendText/{{ " + ND + ".instancia }}"
APIKEY = "={{ " + ND + ".evolutionApiKey }}"
DINAMICOS = ["Alerta Lead Nao Distribuido", "Alerta NaPista Sem Telefone"]
LOJA_NE = "Alerta Loja Nao Encontrada"
MORTOS = ["Montar Alerta", "Enviar Alerta Conexão"]
CORPO_LOJA_NE = (
    "=Chegou mensagem de uma instância da Evolution que não está cadastrada (ou está inativa) em `lojas`.\n"
    "A mensagem NÃO foi registrada nem distribuída.\n\n"
    "Instância: {{ " + ND + ".instancia || '?' }}\n"
    "De: {{ " + ND + ".remetenteNumero || '?' }}\n"
    "Mensagem: {{ String(" + ND + ".mensagemTexto || '(sem texto)').slice(0, 300) }}\n\n"
    "Causas comuns: loja nova com a instância ainda não cadastrada em lojas.instancia_evolution, "
    "loja desativada, ou instância renomeada na Evolution.\n\n"
    "Execução: https://n8n.yavoh.cloud/workflow/" + WID + "/executions/{{ $execution.id }}\n\n"
    "— alerta automático do lead-distributor (n8n)"
)


def estado():
    return json.loads(ESTADO.read_text()) if ESTADO.exists() else {}


def salvar_estado(**kw):
    e = estado(); e.update(kw); ESTADO.write_text(json.dumps(e, indent=1)); ESTADO.chmod(0o600)


def transformar(wf):
    N = {n["name"]: n for n in wf["nodes"]}; C = wf["connections"]
    for n in DINAMICOS + [LOJA_NE] + MORTOS:
        if n not in N: sys.exit(f"erro: no '{n}' nao existe — ja aplicado?")
    log = []
    for nome in DINAMICOS:
        p = N[nome]["parameters"]
        p["url"] = URL
        for h in p["headerParameters"]["parameters"]:
            if h["name"].lower() == "apikey": h["value"] = APIKEY
        log.append(f"  ~ {nome}: URL/instancia/chave de Normaliza Dados (destino continua o dono)")

    velho = N[LOJA_NE]
    novo = {"name": LOJA_NE, "type": "n8n-nodes-base.gmail", "typeVersion": 2.1, "id": velho["id"],
            "position": velho["position"], "credentials": GMAIL, "onError": "continueRegularOutput",
            "parameters": {"resource": "message", "operation": "send", "sendTo": DESTINO_EMAIL,
                           "subject": "=⚠️ Mensagem de instância não cadastrada — {{ " + ND + ".instancia || '?' }}",
                           "emailType": "text", "message": CORPO_LOJA_NE, "options": {"appendAttribution": False}}}
    wf["nodes"][wf["nodes"].index(velho)] = novo
    log.append(f"  ~ {LOJA_NE}: WhatsApp fixo -> e-mail para {DESTINO_EMAIL}")

    wf["nodes"] = [n for n in wf["nodes"] if n["name"] not in MORTOS]
    for m in MORTOS:
        C.pop(m, None)
    for src, v in C.items():
        for i, saida in enumerate(v.get("main", [])):
            v["main"][i] = [x for x in (saida or []) if x["node"] not in MORTOS]
    log.append(f"  - {', '.join(MORTOS)} (codigo morto, substituido pelo alerta de desconexao por e-mail)")
    return log


SEGREDO = re.compile(r"CC1D4[A-Za-z0-9-]{10,}")


def checar(wf, antes):
    N = {n["name"]: n for n in wf["nodes"]}; C = wf["connections"]; erros = []
    if len(wf["nodes"]) != len(antes["nodes"]) - 2: erros.append("numero de nos inesperado")
    for n in wf["nodes"]:
        s = json.dumps(n["parameters"])
        if SEGREDO.search(s) and n["name"] != "Extrai Dados NaPista": erros.append(f"chave da Evolution ainda fixa em {n['name']}")
        if "sendText/renato-motors" in s: erros.append(f"instancia fixa em {n['name']}")
    if any(m in N for m in MORTOS): erros.append("nos mortos ainda existem")
    if any(x["node"] in MORTOS for v in C.values() for o in v.get("main", []) for x in (o or [])): erros.append("conexao para no removido")
    if N[LOJA_NE]["type"] != "n8n-nodes-base.gmail": erros.append("Loja Nao Encontrada nao virou e-mail")
    # nada fora destes nos mudou; conexoes so perderam as dos nos removidos
    tocados = set(DINAMICOS + [LOJA_NE] + MORTOS)
    mudou = [n["name"] for n in antes["nodes"] if n["name"] not in tocados and
             json.dumps(n, sort_keys=True) != json.dumps(N.get(n["name"]), sort_keys=True)]
    if mudou: erros.append(f"outros nos alterados: {mudou}")
    for k, v in antes["connections"].items():
        if k in MORTOS: continue
        esperado = {"main": [[x for x in (o or []) if x["node"] not in MORTOS] for o in v.get("main", [])]}
        if C.get(k) != esperado: erros.append(f"conexao de {k} mudou alem do esperado")
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
    resto = [n["name"] for n in wf["nodes"] if SEGREDO.search(json.dumps(n["parameters"]))]
    print(f"chave da Evolution ainda fixa em: {resto or 'nenhum'} (Extrai Dados NaPista fica para a loja 2)")
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
