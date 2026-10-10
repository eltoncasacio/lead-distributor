#!/usr/bin/env python3
"""Troca o numero que recebe os alertas de lead por WhatsApp (decisao do dono, 2026-10-10).

Uso geral: --de <numero> --para <numero>. (10/10 noite: 6219 -> 7453 de volta,
porque o 6219 nao tem WhatsApp e a loja fake que usava o 7453 foi apagada.)

O 5519996977453 passou a ser o WhatsApp da loja fake (onboarding da segunda
loja). Alerta mandado para ele chegaria na loja fake e viraria lead la. Os
alertas passam para o 5519999746219.

  python3 aplicar_destino_alerta_n8n.py              simula
  python3 aplicar_destino_alerta_n8n.py --aplicar
  python3 aplicar_destino_alerta_n8n.py --reverter
"""
import datetime, importlib.util, json, pathlib, sys

AQUI = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ia", AQUI / "aplicar_comandos_ia_n8n.py")
IAMOD = importlib.util.module_from_spec(spec); spec.loader.exec_module(IAMOD)
req, gravar, BK, WID = IAMOD.req, IAMOD.gravar, IAMOD.BK, IAMOD.WID
ESTADO = BK / "destino_alerta_estado.json"
DE, PARA = "5519996977453", "5519999746219"
if "--de" in sys.argv: DE = sys.argv[sys.argv.index("--de") + 1]
if "--para" in sys.argv: PARA = sys.argv[sys.argv.index("--para") + 1]
NOS = ["Alerta Lead Nao Distribuido", "Alerta NaPista Sem Telefone"]


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
    for nome in NOS:
        jb = N[nome]["parameters"]["jsonBody"]
        if jb.count(DE) != 1: sys.exit(f"erro: {nome} nao tem exatamente 1 ocorrencia de {DE} — ja aplicado?")
        N[nome]["parameters"]["jsonBody"] = jb.replace(DE, PARA)
    resto = [n["name"] for n in wf["nodes"] if DE in json.dumps(n["parameters"])]
    mudou = [n["name"] for n in antes["nodes"] if json.dumps(n, sort_keys=True) != json.dumps(N[n["name"]], sort_keys=True)]
    erros = ([f"{DE} ainda em {resto}"] if resto else []) + ([f"mudou alem do esperado: {mudou}"] if sorted(mudou) != sorted(NOS) else [])
    print(f"antes: {antes['versionId']}\n  ~ {', '.join(NOS)}: destino {DE} -> {PARA}\ntravas:", "todas ok" if not erros else erros)
    if erros: sys.exit("nada gravado")
    if "--aplicar" not in a:
        print("--- SIMULACAO, nada gravado ---"); return
    agora = datetime.datetime.now()
    snap = BK / f"workflow_{WID}_{antes['versionId']}_{agora:%Y%m%d-%H%M%S}.json"
    snap.write_text(json.dumps(antes)); snap.chmod(0o600)
    salvar_estado(snapshot=str(snap), versao_antes=antes["versionId"])
    d = gravar(wf)
    print(f"GRAVADO. {antes['versionId']} -> {d['versionId']} | ativo={d['active']} | ativa=nova? {d['activeVersionId'] == d['versionId']}")
    salvar_estado(versao_depois=d["versionId"], aplicado_em=agora.isoformat())


if __name__ == "__main__":
    main()
