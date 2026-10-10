#!/usr/bin/env python3
"""Faz o alerta "Loja nao encontrada" disparar de verdade (2026-10-10).

Defeito antigo, achado no teste da Fase A2 (execucao 9217): quando a
instancia nao esta em `lojas`, `Identificar Loja` recebe [] e o n8n PARA ali —
`Loja Encontrada?` nunca roda, e o alerta nunca disparou, nem na versao antiga.

Correcao: `alwaysOutputData: true` em `Identificar Loja`. Com resultado vazio
ele entrega um item vazio; `Loja Encontrada?` ($json.id exists) da falso e o
alerta (agora por e-mail) roda. Loja encontrada: nada muda.

  python3 aplicar_loja_nao_encontrada_n8n.py              simula
  python3 aplicar_loja_nao_encontrada_n8n.py --aplicar
  python3 aplicar_loja_nao_encontrada_n8n.py --reverter
"""
import datetime, importlib.util, json, pathlib, sys

AQUI = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ia", AQUI / "aplicar_comandos_ia_n8n.py")
IAMOD = importlib.util.module_from_spec(spec); spec.loader.exec_module(IAMOD)
req, gravar, BK, WID = IAMOD.req, IAMOD.gravar, IAMOD.BK, IAMOD.WID
ESTADO = BK / "loja_nao_encontrada_estado.json"
NO = "Identificar Loja"


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
        print(f"REVERTIDO para {wf['versionId']}. nova {d['versionId']} | ativo={d['active']}")
        return
    wf = req("GET", f"workflows/{WID}"); antes = json.loads(json.dumps(wf))
    N = {n["name"]: n for n in wf["nodes"]}
    if N[NO].get("alwaysOutputData"): sys.exit("ja aplicado")
    N[NO]["alwaysOutputData"] = True
    mudou = [n["name"] for n in antes["nodes"] if json.dumps(n, sort_keys=True) != json.dumps(N[n["name"]], sort_keys=True)]
    erros = [] if mudou == [NO] and wf["connections"] == antes["connections"] else [f"mudancas inesperadas: {mudou}"]
    print(f"antes: {antes['versionId']}\n  ~ {NO}: alwaysOutputData = true\ntravas:", "todas ok" if not erros else erros)
    if erros: sys.exit("nada gravado")
    if "--aplicar" not in a:
        print("--- SIMULACAO, nada gravado ---"); return
    agora = datetime.datetime.now()
    snap = BK / f"workflow_{WID}_{antes['versionId']}_{agora:%Y%m%d-%H%M%S}.json"
    snap.write_text(json.dumps(antes)); snap.chmod(0o600)
    salvar_estado(snapshot=str(snap), versao_antes=antes["versionId"])
    d = gravar(wf)
    ok = {n["name"]: n for n in d["nodes"]}[NO].get("alwaysOutputData") is True
    print(f"GRAVADO. {antes['versionId']} -> {d['versionId']} | ativo={d['active']} | ativa=nova? {d['activeVersionId'] == d['versionId']} | flag gravada: {ok}")
    salvar_estado(versao_depois=d["versionId"], aplicado_em=agora.isoformat())


if __name__ == "__main__":
    main()
