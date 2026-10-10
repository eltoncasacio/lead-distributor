#!/usr/bin/env python3
"""Caminho legado (status/leads do gerente) passa a usar o comando interpretado.

Defeito (execucao 9181, 2026-10-10): gerente escreveu "Quais leads chegou nos
ultimos 3 dias"; a IA entendeu `leads`, o banco devolveu acao=legado, mas
`Identificar Comando` compara o TEXTO ORIGINAL com "status"/"leads" — nao bateu
e o gerente recebeu "Comando nao reconhecido".

Correcao: as duas condicoes de `Identificar Comando` passam a ler
$('Executar Comando').item.json.interpretado (o que o banco de fato executou),
com o texto original de reserva. Nenhum outro no muda.

  python3 aplicar_legado_interpretado_n8n.py              simula
  python3 aplicar_legado_interpretado_n8n.py --aplicar
  python3 aplicar_legado_interpretado_n8n.py --reverter
"""
import datetime, importlib.util, json, pathlib, sys

AQUI = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ia", AQUI / "aplicar_comandos_ia_n8n.py")
IAMOD = importlib.util.module_from_spec(spec); spec.loader.exec_module(IAMOD)
req, gravar, BK, WID = IAMOD.req, IAMOD.gravar, IAMOD.BK, IAMOD.WID
ESTADO = BK / "legado_estado.json"
NO = "Identificar Comando"
ANTIGO = "={{ $('Normaliza Dados').item.json.mensagemTexto.toLowerCase() }}"
NOVO = ("={{ String($('Executar Comando').item.json.interpretado || "
        "$('Normaliza Dados').item.json.mensagemTexto || '').trim().toLowerCase() }}")


def estado():
    return json.loads(ESTADO.read_text()) if ESTADO.exists() else {}


def salvar_estado(**kw):
    e = estado(); e.update(kw); ESTADO.write_text(json.dumps(e, indent=1)); ESTADO.chmod(0o600)


def transformar(wf):
    N = {n["name"]: n for n in wf["nodes"]}
    regras = N[NO]["parameters"]["rules"]["values"]
    trocadas = 0
    for r in regras:
        for c in r["conditions"]["conditions"]:
            if c.get("leftValue") == ANTIGO:
                c["leftValue"] = NOVO; trocadas += 1
    if trocadas != 2: sys.exit(f"erro: esperava 2 condicoes com o texto original, achei {trocadas} — ja aplicado?")
    return [f"  ~ {NO}: status/leads comparados com o comando interpretado ({trocadas} condicoes)"]


def checar(wf, antes):
    N = {n["name"]: n for n in wf["nodes"]}; erros = []
    s = json.dumps(N[NO]["parameters"])
    if s.count("interpretado") != 2: erros.append("condicoes nao usam interpretado")
    mudou = [n["name"] for n in antes["nodes"] if n["name"] != NO and
             json.dumps(n, sort_keys=True) != json.dumps(N.get(n["name"]), sort_keys=True)]
    if mudou: erros.append(f"outros nos alterados: {mudou}")
    if wf["connections"] != antes["connections"]: erros.append("conexoes mudaram")
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
    print(f"antes: versionId {wf['versionId']}\n\nmudancas:")
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
