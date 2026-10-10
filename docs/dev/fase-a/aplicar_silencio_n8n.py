#!/usr/bin/env python3
"""So gerente ativo ou vendedor ativo fala com o sistema (regra do dono, 2026-10-10).

O banco ja devolve acao=ignorado e resposta NULL para quem nao tem permissao
(vendedor pausado/removido, gerente desativado). Este script garante que o n8n
nao envie nada nesse caso — sem isto, ele tentaria mandar uma mensagem vazia.

Antes:  Comando Legado? -nao-> Enviar Resposta Comando
Depois: Comando Legado? -nao-> Tem Resposta? -sim-> Enviar Resposta Comando
                                             -nao-> (fim, nada enviado)

  python3 aplicar_silencio_n8n.py              simula
  python3 aplicar_silencio_n8n.py --aplicar
  python3 aplicar_silencio_n8n.py --reverter
"""
import datetime, importlib.util, json, pathlib, sys, uuid

AQUI = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ia", AQUI / "aplicar_comandos_ia_n8n.py")
IAMOD = importlib.util.module_from_spec(spec); spec.loader.exec_module(IAMOD)
req, gravar, BK, WID = IAMOD.req, IAMOD.gravar, IAMOD.BK, IAMOD.WID
ESTADO = BK / "silencio_estado.json"
LEGADO, ENVIAR, TEM = "Comando Legado?", "Enviar Resposta Comando", "Tem Resposta?"


def estado():
    return json.loads(ESTADO.read_text()) if ESTADO.exists() else {}


def salvar_estado(**kw):
    e = estado(); e.update(kw); ESTADO.write_text(json.dumps(e, indent=1)); ESTADO.chmod(0o600)


def transformar(wf):
    N = {n["name"]: n for n in wf["nodes"]}; C = wf["connections"]
    if TEM in N: sys.exit("erro: ja aplicado")
    if [x["node"] for x in C[LEGADO]["main"][1]] != [ENVIAR]:
        sys.exit("erro: saida 'nao' de Comando Legado? nao vai so para Enviar Resposta Comando")
    x, y = N[ENVIAR]["position"]
    N[ENVIAR]["position"] = [x + 220, y]
    wf["nodes"].append(
        {"name": TEM, "type": "n8n-nodes-base.if", "typeVersion": 2.2, "id": str(uuid.uuid4()),
         "position": [x, y],
         "parameters": {"conditions": {
             "options": {"version": 2, "leftValue": "", "caseSensitive": True, "typeValidation": "loose"},
             "conditions": [{"id": str(uuid.uuid4()), "leftValue": "={{ $('Executar Comando').item.json.resposta }}",
                             "rightValue": "", "operator": {"type": "string", "operation": "notEmpty", "singleValue": True}}],
             "combinator": "and"}, "looseTypeValidation": True, "options": {}}})
    C[LEGADO]["main"][1] = [{"node": TEM, "type": "main", "index": 0}]
    C[TEM] = {"main": [[{"node": ENVIAR, "type": "main", "index": 0}], []]}
    return [f"  + {TEM}  (resposta vazia -> nada enviado)", f"  ~ {LEGADO} (nao) -> {TEM} -> {ENVIAR}"]


def checar(wf, antes):
    N = {n["name"]: n for n in wf["nodes"]}; C = wf["connections"]; erros = []
    if len(wf["nodes"]) != len(antes["nodes"]) + 1: erros.append("numero de nos inesperado")
    if [x["node"] for x in C[LEGADO]["main"][1]] != [TEM]: erros.append("Comando Legado? nao vai para Tem Resposta?")
    if [x["node"] for x in C[TEM]["main"][0]] != [ENVIAR]: erros.append("Tem Resposta? nao vai para Enviar")
    if C[LEGADO]["main"][0] != antes["connections"][LEGADO]["main"][0]: erros.append("caminho legado mudou")
    def sem_pos(n): return {k: v for k, v in n.items() if k != "position"} if n else None
    mudou = [n["name"] for n in antes["nodes"] if json.dumps(sem_pos(n), sort_keys=True) != json.dumps(sem_pos(N.get(n["name"])), sort_keys=True)]
    if mudou: erros.append(f"nos existentes alterados: {mudou}")
    outras = {k: v for k, v in antes["connections"].items() if k != LEGADO}
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
