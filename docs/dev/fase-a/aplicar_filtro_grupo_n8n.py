#!/usr/bin/env python3
"""Descarta mensagem de grupo, canal e lista de transmissao (2026-10-17).

Achado no onboarding da Fitcar: o workflow nao filtrava `@g.us`. A Fitcar esta
em grupos de revenda; das 148 mensagens da primeira hora, 82 eram de grupo —
viraram lead ("cliente" = ID do grupo) ou reencaminharam "Novo Lead" ao
vendedor a cada foto. Grupo com ID antigo (`…-1450533080`) estoura
`varchar(20)` em `distribuir_lead` e gera alerta "Lead nao distribuido".

Correcao: `Filtro fromMe` (saida 0 = descartar no NoOp) passa a descartar
tambem `remoteJid` terminado em `@g.us`, `@newsletter` ou `@broadcast`.
Combinador vira OR; a condicao vazia que existia (""=="", sempre verdadeira)
sai — com OR ela descartaria tudo. Conversa individual (`@s.whatsapp.net`,
`@lid`) nao muda. Nome do no mantido (outros nos podem referencia-lo).

  python3 aplicar_filtro_grupo_n8n.py              simula
  python3 aplicar_filtro_grupo_n8n.py --aplicar
  python3 aplicar_filtro_grupo_n8n.py --reverter
"""
import datetime, importlib.util, json, pathlib, sys

AQUI = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ia", AQUI / "aplicar_comandos_ia_n8n.py")
IAMOD = importlib.util.module_from_spec(spec); spec.loader.exec_module(IAMOD)
req, gravar, BK, WID = IAMOD.req, IAMOD.gravar, IAMOD.BK, IAMOD.WID
ESTADO = BK / "filtro_grupo_estado.json"
NO = "Filtro fromMe"
JID = "={{ $json.body.data.key.remoteJid || '' }}"
SUFIXOS = ["@g.us", "@newsletter", "@broadcast"]


def estado():
    return json.loads(ESTADO.read_text()) if ESTADO.exists() else {}


def salvar_estado(**kw):
    e = estado(); e.update(kw); ESTADO.write_text(json.dumps(e, indent=1)); ESTADO.chmod(0o600)


def condicoes():
    c = [{"id": "cond-fromme", "operator": {"type": "boolean", "operation": "equals"},
          "leftValue": "={{ $json.body.data.key.fromMe }}", "rightValue": True}]
    for s in SUFIXOS:
        c.append({"id": f"cond-jid-{s.strip('@').replace('.', '-')}",
                  "operator": {"type": "string", "operation": "endsWith"},
                  "leftValue": JID, "rightValue": s})
    return c


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
    cond = N[NO]["parameters"]["conditions"]
    if any(c.get("id", "").startswith("cond-jid-") for c in cond["conditions"]): sys.exit("ja aplicado")
    erros = []
    if wf["connections"][NO]["main"][0][0]["node"] != "No Operation, do nothing":
        erros.append("saida 0 de Filtro fromMe nao vai mais para o NoOp")
    if wf["connections"][NO]["main"][1][0]["node"] != "Normaliza Dados":
        erros.append("saida 1 de Filtro fromMe nao vai mais para Normaliza Dados")
    cond["conditions"] = condicoes(); cond["combinator"] = "or"
    mudou = [n["name"] for n in antes["nodes"] if json.dumps(n, sort_keys=True) != json.dumps(N[n["name"]], sort_keys=True)]
    if mudou != [NO] or wf["connections"] != antes["connections"]: erros.append(f"mudancas inesperadas: {mudou}")
    print(f"antes: {antes['versionId']}\n  ~ {NO}: descarta fromMe OU remoteJid em {SUFIXOS}\ntravas:", "todas ok" if not erros else erros)
    if erros: sys.exit("nada gravado")
    if "--aplicar" not in a:
        print("--- SIMULACAO, nada gravado ---"); return
    agora = datetime.datetime.now()
    snap = BK / f"workflow_{WID}_{antes['versionId']}_{agora:%Y%m%d-%H%M%S}.json"
    snap.write_text(json.dumps(antes)); snap.chmod(0o600)
    salvar_estado(snapshot=str(snap), versao_antes=antes["versionId"])
    d = gravar(wf)
    g = {n["name"]: n for n in d["nodes"]}[NO]["parameters"]["conditions"]
    ok = g["combinator"] == "or" and len(g["conditions"]) == 1 + len(SUFIXOS)
    print(f"GRAVADO. {antes['versionId']} -> {d['versionId']} | ativo={d['active']} | ativa=nova? {d['activeVersionId'] == d['versionId']} | filtro gravado: {ok}")
    salvar_estado(versao_depois=d["versionId"], aplicado_em=agora.isoformat())


if __name__ == "__main__":
    main()
