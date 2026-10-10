#!/usr/bin/env python3
"""Limite de uso da IA de comandos (custo).

Antes:  Nao E Lead -> Buscar Nomes Vendedores -> ... -> Executar Comando
Depois: Nao E Lead -> Reservar IA (rpc/reservar_ia) -> Usar IA?
                         sim -> Buscar Nomes Vendedores -> ... (IA, como antes)
                         nao -> Executar Comando (sem IA: texto digitado)

reservar_ia (Postgres) diz "nao" para comando exato (menu, sim, status...) e
para quem passou de 30 chamadas no dia. Se Reservar IA falhar, Usar IA? cai
no "nao": sem IA, os comandos digitados continuam funcionando.

Tambem regrava o codigo de Montar Pedido IA a partir de comandos_ia/prompt.py
(agora so os primeiros prompt.LIMITE_TEXTO caracteres vao para a IA).

  python3 aplicar_limite_ia_n8n.py              simula
  python3 aplicar_limite_ia_n8n.py --aplicar
  python3 aplicar_limite_ia_n8n.py --reverter

Requer no .env: N8N_API_KEY. Precisa de reservar_ia ja aplicada no banco."""
import datetime, importlib.util, json, pathlib, sys, uuid

AQUI = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ia", AQUI / "aplicar_comandos_ia_n8n.py")
IAMOD = importlib.util.module_from_spec(spec); spec.loader.exec_module(IAMOD)
req, gravar, BK, WID, CRED_SB = IAMOD.req, IAMOD.gravar, IAMOD.BK, IAMOD.WID, IAMOD.CRED_SB
NOMES, MONTAR, EXEC = IAMOD.NOMES, IAMOD.MONTAR, IAMOD.EXEC
ESTADO = BK / "limite_ia_estado.json"
RESERVAR, USAR = "Reservar IA", "Usar IA?"


def estado():
    return json.loads(ESTADO.read_text()) if ESTADO.exists() else {}


def salvar_estado(**kw):
    e = estado(); e.update(kw); ESTADO.write_text(json.dumps(e, indent=1)); ESTADO.chmod(0o600)


def transformar(wf):
    N = {n["name"]: n for n in wf["nodes"]}; C = wf["connections"]
    if RESERVAR in N: sys.exit("erro: limite ja aplicado")
    if [x["node"] for x in C["Não É Lead"]["main"][0]] != [NOMES]:
        sys.exit("erro: Nao E Lead (true) nao vai para Buscar Nomes Vendedores — a IA esta ligada?")
    x, y = N[NOMES]["position"]
    wf["nodes"] += [
        {"name": RESERVAR, "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.3, "id": str(uuid.uuid4()),
         "position": [x - 440, y], "credentials": CRED_SB, "onError": "continueRegularOutput",
         "parameters": {
             "method": "POST",
             "url": "={{ $('Normaliza Dados').item.json.supabaseUrl }}/rest/v1/rpc/reservar_ia",
             "authentication": "genericCredentialType", "genericAuthType": "httpCustomAuth",
             "sendBody": True, "specifyBody": "json",
             "jsonBody": "={{ JSON.stringify({ p_loja_id: $('Preparar Dados Loja').item.json.lojaId, "
                         "p_remetente: $('Normaliza Dados').item.json.remetenteNumero, "
                         "p_texto: $('Normaliza Dados').item.json.mensagemTexto }) }}",
             "options": {"timeout": 5000}}},
        {"name": USAR, "type": "n8n-nodes-base.if", "typeVersion": 2.2, "id": str(uuid.uuid4()),
         "position": [x - 220, y],
         "parameters": {"conditions": {
             "options": {"version": 2, "leftValue": "", "caseSensitive": True, "typeValidation": "loose"},
             "conditions": [{"id": str(uuid.uuid4()), "leftValue": "={{ $json.usar === true }}", "rightValue": "",
                             "operator": {"type": "boolean", "operation": "true", "singleValue": True}}],
             "combinator": "and"}, "looseTypeValidation": True, "options": {}}},
    ]
    N[MONTAR]["parameters"]["jsCode"] = IAMOD.montar_js()
    C["Não É Lead"]["main"][0] = [{"node": RESERVAR, "type": "main", "index": 0}]
    C[RESERVAR] = {"main": [[{"node": USAR, "type": "main", "index": 0}]]}
    C[USAR] = {"main": [[{"node": NOMES, "type": "main", "index": 0}],
                        [{"node": EXEC, "type": "main", "index": 0}]]}
    return [f"  + {RESERVAR}  (rpc/reservar_ia; falha -> sem IA)",
            f"  + {USAR}  (sim -> {NOMES}; nao -> {EXEC})",
            f"  ~ {MONTAR}: codigo regerado (texto cortado em {IAMOD.P.LIMITE_TEXTO} caracteres)",
            f"  ~ Nao E Lead (true) -> {RESERVAR}"]


def checar(wf, antes):
    N = {n["name"]: n for n in wf["nodes"]}; C = wf["connections"]; erros = []
    if len(wf["nodes"]) != len(antes["nodes"]) + 2: erros.append("numero de nos inesperado")
    if [x["node"] for x in C["Não É Lead"]["main"][0]] != [RESERVAR]: erros.append("Nao E Lead nao vai para Reservar IA")
    if C["Não É Lead"]["main"][1] != antes["connections"]["Não É Lead"]["main"][1]: erros.append("caminho de lead mudou")
    if [x["node"] for x in C[USAR]["main"][0]] != [NOMES]: erros.append("sim nao vai para a IA")
    if [x["node"] for x in C[USAR]["main"][1]] != [EXEC]: erros.append("nao nao vai para Executar Comando")
    if N[RESERVAR].get("onError") != "continueRegularOutput": erros.append("Reservar IA sem continuar-em-falha")
    if f"slice(0, {IAMOD.P.LIMITE_TEXTO})" not in N[MONTAR]["parameters"]["jsCode"]: erros.append("Montar Pedido sem corte de texto")
    mudou = [n["name"] for n in antes["nodes"] if n["name"] != MONTAR and
             json.dumps(n, sort_keys=True) != json.dumps(N.get(n["name"]), sort_keys=True)]
    if mudou: erros.append(f"outros nos alterados: {mudou}")
    outras = {k: v for k, v in antes["connections"].items() if k != "Não É Lead"}
    if any(C.get(k) != v for k, v in outras.items()): erros.append("outras conexoes mudaram")
    return erros


def main():
    a = sys.argv[1:]
    if "--reverter" in a:
        snap = estado().get("snapshot")
        if not snap: sys.exit("erro: nao ha snapshot salvo")
        wf = json.loads(pathlib.Path(snap).read_text()); d = gravar(wf)
        print(f"REVERTIDO para {wf['versionId']}. nova {d['versionId']} | ativo={d['active']} | ativa=nova? {d['activeVersionId'] == d['versionId']}")
        return
    wf = req("GET", f"workflows/{WID}"); antes = json.loads(json.dumps(wf))
    print(f"antes: versionId {wf['versionId']} | {len(wf['nodes'])} nos | ativo={wf['active']}\n\nmudancas:")
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
    print(f"\nsnapshot: {snap}")
    d = gravar(wf)
    print(f"GRAVADO. versionId {antes['versionId']} -> {d['versionId']} | ativo={d['active']} | ativa=nova? {d['activeVersionId'] == d['versionId']}")
    erros = checar(d, antes)
    print("travas no que ficou gravado:", "todas ok" if not erros else erros)
    salvar_estado(versao_depois=d["versionId"], aplicado_em=agora.isoformat())


if __name__ == "__main__":
    main()
