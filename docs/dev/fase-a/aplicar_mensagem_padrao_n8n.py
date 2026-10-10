#!/usr/bin/env python3
"""Mensagem padrao do sistema para loja sem mensagem pronta (2026-10-10).

Defeito: loja sem nenhuma linha em `mensagens_prontas` -> `Buscar Mensagens
Prontas` volta vazio -> o n8n para ali e o vendedor NUNCA recebe o aviso do
lead (o lead e criado e distribuido, em silencio). A Renato Motors nao sofre
porque tem mensagens cadastradas; toda loja nova cairia nisso.

Correcao (pedido do dono: "era para ter mensagem padrao"):
  - `Buscar Mensagens Prontas` com alwaysOutputData (nao para mais o fluxo);
  - `Montar Notificacao` ignora item vazio e, se a loja nao tiver nenhuma
    mensagem, usa a MENSAGEM_PADRAO abaixo (o texto da Renato Motors, com o
    nome da loja no lugar);
  - novo placeholder {loja_nome}, que tambem pode ser usado nas mensagens
    cadastradas.
Loja com mensagens cadastradas: aviso identico ao de antes.

  python3 aplicar_mensagem_padrao_n8n.py              simula
  python3 aplicar_mensagem_padrao_n8n.py --aplicar
  python3 aplicar_mensagem_padrao_n8n.py --reverter
"""
import datetime, importlib.util, json, pathlib, sys

AQUI = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ia", AQUI / "aplicar_comandos_ia_n8n.py")
IAMOD = importlib.util.module_from_spec(spec); spec.loader.exec_module(IAMOD)
req, gravar, BK, WID = IAMOD.req, IAMOD.gravar, IAMOD.BK, IAMOD.WID
ESTADO = BK / "mensagem_padrao_estado.json"
BUSCAR, MONTAR = "Buscar Mensagens Prontas", "Montar Notificação"

MENSAGEM_PADRAO = ("Olá,\nMeu nome é {vendedor_nome} e sou consultor de vendas da {loja_nome}, tudo bem?\n"
                   "Referente seu interesse no veículo {anuncio}. em que posso te ajudar?\n"
                   "Teria disponibilidade de vir a loja?")

TROCAS = [
    ("const rawTemplates = $input.all().map(i => i.json);",
     "// Itens vazios aparecem quando a loja nao tem mensagem pronta (Buscar Mensagens\n"
     "// Prontas com alwaysOutputData). Ficam de fora.\n"
     "const rawTemplates = $input.all().map(i => i.json).filter(t => t && t.texto);\n\n"
     "// Mensagem padrao do sistema: usada quando a loja nao tem nenhuma cadastrada.\n"
     "// Mesmo texto da Renato Motors, com o nome da loja no lugar (2026-10-10).\n"
     f"const MENSAGEM_PADRAO = {json.dumps(MENSAGEM_PADRAO, ensure_ascii=False)};\n"
     "let lojaNome = 'nossa loja';\n"
     "try { lojaNome = $('Preparar Dados Loja').first().json.lojaNome || lojaNome; } catch (e) {}"),
    ("const templates = templatesVendedor.length ? templatesVendedor : templatesLoja;",
     "let templates = templatesVendedor.length ? templatesVendedor : templatesLoja;\n"
     "if (!templates.length) templates = [{ titulo: 'Mensagem Padrão', texto: MENSAGEM_PADRAO }];"),
    (".replace(/{origem}/g, origem);",
     ".replace(/{origem}/g, origem)\n    .replace(/{loja_nome}/g, lojaNome);"),
]


def estado():
    return json.loads(ESTADO.read_text()) if ESTADO.exists() else {}


def salvar_estado(**kw):
    e = estado(); e.update(kw); ESTADO.write_text(json.dumps(e, indent=1)); ESTADO.chmod(0o600)


def novo_codigo(codigo):
    for a, b in TROCAS:
        if codigo.count(a) != 1: sys.exit(f"erro: trecho nao encontrado (ou repetido) em {MONTAR}: {a[:50]} — ja aplicado?")
        codigo = codigo.replace(a, b)
    return codigo


def transformar(wf):
    N = {n["name"]: n for n in wf["nodes"]}
    if N[BUSCAR].get("alwaysOutputData"): sys.exit("ja aplicado")
    N[BUSCAR]["alwaysOutputData"] = True
    N[MONTAR]["parameters"]["jsCode"] = novo_codigo(N[MONTAR]["parameters"]["jsCode"])
    return [f"  ~ {BUSCAR}: alwaysOutputData = true", f"  ~ {MONTAR}: mensagem padrao + {{loja_nome}} + ignora item vazio"]


def checar(wf, antes):
    N = {n["name"]: n for n in wf["nodes"]}; erros = []
    if "MENSAGEM_PADRAO" not in N[MONTAR]["parameters"]["jsCode"]: erros.append("codigo sem mensagem padrao")
    if not N[BUSCAR].get("alwaysOutputData"): erros.append("busca sem alwaysOutputData")
    mudou = [n["name"] for n in antes["nodes"] if n["name"] not in (BUSCAR, MONTAR) and
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
    print(f"antes: {wf['versionId']}\n\nmudancas:"); print("\n".join(transformar(wf)))
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
    print(f"\nsnapshot: {snap}\nGRAVADO. {antes['versionId']} -> {d['versionId']} | ativo={d['active']} | ativa=nova? {d['activeVersionId'] == d['versionId']}")
    erros = checar(d, antes)
    print("travas no que ficou gravado:", "todas ok" if not erros else erros)
    salvar_estado(versao_depois=d["versionId"], aplicado_em=agora.isoformat())


if __name__ == "__main__":
    main()
