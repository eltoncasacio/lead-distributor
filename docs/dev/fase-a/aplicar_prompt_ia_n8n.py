#!/usr/bin/env python3
"""Leva o prompt atual de comandos_ia/prompt.py para o no `Montar Pedido IA` do n8n.

Usar depois de mudar o prompt E rodar comandos_ia/avaliar.py. So esse no muda.

  python3 aplicar_prompt_ia_n8n.py              simula (mostra se ha diferenca)
  python3 aplicar_prompt_ia_n8n.py --aplicar
  python3 aplicar_prompt_ia_n8n.py --reverter
"""
import datetime, importlib.util, json, pathlib, sys

AQUI = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ia", AQUI / "aplicar_comandos_ia_n8n.py")
IAMOD = importlib.util.module_from_spec(spec); spec.loader.exec_module(IAMOD)
req, gravar, BK, WID, MONTAR = IAMOD.req, IAMOD.gravar, IAMOD.BK, IAMOD.WID, IAMOD.MONTAR
ESTADO = BK / "prompt_ia_estado.json"


def estado():
    return json.loads(ESTADO.read_text()) if ESTADO.exists() else {}


def salvar_estado(**kw):
    e = estado(); e.update(kw); ESTADO.write_text(json.dumps(e, indent=1)); ESTADO.chmod(0o600)


def main():
    a = sys.argv[1:]
    if "--reverter" in a:
        snap = estado().get("snapshot")
        if not snap: sys.exit("erro: nao ha snapshot salvo")
        wf = json.loads(pathlib.Path(snap).read_text()); d = gravar(wf)
        print(f"REVERTIDO para {wf['versionId']}. nova {d['versionId']} | ativo={d['active']}"); return
    wf = req("GET", f"workflows/{WID}"); antes = json.loads(json.dumps(wf))
    N = {n["name"]: n for n in wf["nodes"]}
    novo = IAMOD.montar_js()
    if N[MONTAR]["parameters"]["jsCode"] == novo:
        print("prompt no n8n ja e o atual — nada a fazer"); return
    N[MONTAR]["parameters"]["jsCode"] = novo
    mudou = [n["name"] for n in antes["nodes"] if json.dumps(n, sort_keys=True) != json.dumps(N[n["name"]], sort_keys=True)]
    if mudou != [MONTAR] or wf["connections"] != antes["connections"]: sys.exit(f"mudancas inesperadas: {mudou}")
    print(f"antes: {antes['versionId']}\n  ~ {MONTAR}: prompt regerado de comandos_ia/prompt.py\ntravas: todas ok")
    if "--aplicar" not in a:
        print("--- SIMULACAO, nada gravado ---"); return
    agora = datetime.datetime.now()
    snap = BK / f"workflow_{WID}_{antes['versionId']}_{agora:%Y%m%d-%H%M%S}.json"
    snap.write_text(json.dumps(antes)); snap.chmod(0o600)
    salvar_estado(snapshot=str(snap), versao_antes=antes["versionId"])
    d = gravar(wf)
    ok = {n["name"]: n for n in d["nodes"]}[MONTAR]["parameters"]["jsCode"] == novo
    print(f"GRAVADO. {antes['versionId']} -> {d['versionId']} | ativo={d['active']} | ativa=nova? {d['activeVersionId'] == d['versionId']} | prompt gravado: {ok}")
    salvar_estado(versao_depois=d["versionId"], aplicado_em=agora.isoformat())


if __name__ == "__main__":
    main()
