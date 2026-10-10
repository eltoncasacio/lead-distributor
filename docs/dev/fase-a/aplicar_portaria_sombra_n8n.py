#!/usr/bin/env python3
"""Portaria v3 em MODO SOMBRA no n8n (2026-10-10).

Acrescenta um ramo PARALELO na saida "cliente" de `Nao E Lead`. O ramo de
hoje (Verificar Origem -> ... -> Distribuir Lead) nao muda. A sombra so grava
em `portaria_sombra` o que a IA faria; nada e ignorado.

  Nao E Lead (cliente) -> Verificar Origem ...                (inalterado)
                       -> Sombra: Preparar (rpc/portaria_sombra_preparar)
                          -> Sombra: Usar IA? -> Sombra: Montar Pedido (prompt de portaria/prompt.py)
                          -> Sombra: IA (OpenRouter) -> Sombra: Ler -> Sombra: Registrar (rpc/registrar_portaria_sombra)

Garantias: todos os nos da sombra com onError=continueRegularOutput; nos
posicionados ABAIXO do ramo principal (o n8n executa os ramos de cima para
baixo, entao a distribuicao acontece antes); credenciais do n8n (nenhuma chave
no workflow); limite de 200 classificacoes/loja/dia no banco.

  python3 aplicar_portaria_sombra_n8n.py              simula
  python3 aplicar_portaria_sombra_n8n.py --aplicar
  python3 aplicar_portaria_sombra_n8n.py --reverter
"""
import datetime, importlib.util, json, pathlib, sys, uuid

AQUI = pathlib.Path(__file__).resolve().parent
RAIZ = AQUI.parents[2]
spec = importlib.util.spec_from_file_location("ia", AQUI / "aplicar_comandos_ia_n8n.py")
IAMOD = importlib.util.module_from_spec(spec); spec.loader.exec_module(IAMOD)
req, gravar, BK, WID, CRED_SB = IAMOD.req, IAMOD.gravar, IAMOD.BK, IAMOD.WID, IAMOD.CRED_SB
sys.path.insert(0, str(RAIZ))
from portaria import prompt as PP

ESTADO = BK / "portaria_sombra_estado.json"
CRED_OR = {"httpHeaderAuth": {"id": json.loads((BK / "comandos_ia_estado.json").read_text())["cred_or_id"],
                              "name": "OpenRouter comandos"}}
NEL = "Não É Lead"
PREP, USAR, MONT, IA, LER, REG = ("Sombra: Preparar", "Sombra: Usar IA?", "Sombra: Montar Pedido",
                                 "Sombra: IA", "Sombra: Ler", "Sombra: Registrar")
ND = "$('Normaliza Dados').item.json"
LOJA = "$('Preparar Dados Loja').item.json.lojaId"


def montar_js():
    base = PP.corpo_requisicao("<<TEXTO>>", PP.MODELO)
    usuario = base["messages"][1]["content"]
    return (
        "// Gerado por docs/dev/fase-a/aplicar_portaria_sombra_n8n.py a partir de portaria/prompt.py.\n"
        "// NAO editar aqui: mude o prompt.py, rode portaria/avaliar.py e reaplique.\n"
        f"const corpo = {json.dumps(base, ensure_ascii=False, indent=1)};\n"
        f"const modelo = {json.dumps(usuario, ensure_ascii=False)};\n"
        f"const texto = String({ND}.mensagemTexto || '').slice(0, {PP.LIMITE_TEXTO});\n"
        "corpo.messages[1].content = modelo.split('<<TEXTO>>').join(texto);\n"
        "return { json: { corpo } };\n"
    )


LER_JS = """// Extrai {classificacao, motivo, trecho_evidencia}; qualquer falha -> null
// (o banco transforma em 'duvida' = distribuir). Espelha portaria/prompt.py:extrair.
let c = null, motivo = null, trecho = null;
try {
  const ch = $('""" + IA + """').item.json.choices[0];
  if (ch.finish_reason === 'stop') {
    let t = ch.message.content;
    if (typeof t === 'string') {
      t = t.trim();
      if (t.startsWith('```')) t = t.replace(/^```[a-z]*\\n?/, '').replace(/```$/, '');
      t = JSON.parse(t);
    }
    c = t.classificacao ?? null; motivo = t.motivo ?? null; trecho = t.trecho_evidencia ?? null;
  }
} catch (e) { c = null; }
return { json: { classificacao: c, motivo, trecho } };"""


def http(nome, pos, url, cred, tipo, body_expr, timeout):
    return {"name": nome, "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.3, "id": str(uuid.uuid4()),
            "position": pos, "credentials": cred, "onError": "continueRegularOutput",
            "parameters": {"method": "POST", "url": url, "authentication": "genericCredentialType",
                           "genericAuthType": tipo, "sendBody": True, "specifyBody": "json",
                           "jsonBody": body_expr, "options": {"timeout": timeout}}}


def transformar(wf):
    N = {n["name"]: n for n in wf["nodes"]}; C = wf["connections"]
    if PREP in N: sys.exit("erro: sombra ja aplicada")
    saida_cliente = C[NEL]["main"][1]
    if [x["node"] for x in saida_cliente] != ["Verificar Origem"]:
        sys.exit(f"erro: saida 'cliente' de {NEL} mudou: {saida_cliente}")
    # abaixo de tudo: o n8n roda os ramos de cima para baixo
    y = max(n["position"][1] for n in wf["nodes"]) + 400
    x = N["Verificar Origem"]["position"][0]
    sup = "={{ " + ND + ".supabaseUrl }}/rest/v1/rpc/"
    novos = [
        http(PREP, [x, y], sup + "portaria_sombra_preparar", CRED_SB, "httpCustomAuth",
             "={{ JSON.stringify({ p_loja_id: " + LOJA + ", p_remetente: " + ND + ".remetenteNumero, p_texto: " + ND + ".mensagemTexto || '' }) }}",
             5000),
        {"name": USAR, "type": "n8n-nodes-base.if", "typeVersion": 2.2, "id": str(uuid.uuid4()), "position": [x + 220, y],
         "parameters": {"conditions": {"options": {"version": 2, "leftValue": "", "caseSensitive": True, "typeValidation": "loose"},
                                       "conditions": [{"id": str(uuid.uuid4()), "leftValue": "={{ $json.usar === true }}", "rightValue": "",
                                                       "operator": {"type": "boolean", "operation": "true", "singleValue": True}}],
                                       "combinator": "and"}, "looseTypeValidation": True, "options": {}}},
        {"name": MONT, "type": "n8n-nodes-base.code", "typeVersion": 2, "id": str(uuid.uuid4()), "position": [x + 440, y],
         "onError": "continueRegularOutput", "parameters": {"mode": "runOnceForEachItem", "jsCode": montar_js()}},
        http(IA, [x + 660, y], PP.URL, CRED_OR, "httpHeaderAuth", "={{ JSON.stringify($json.corpo) }}", 15000),
        {"name": LER, "type": "n8n-nodes-base.code", "typeVersion": 2, "id": str(uuid.uuid4()), "position": [x + 880, y],
         "onError": "continueRegularOutput", "parameters": {"mode": "runOnceForEachItem", "jsCode": LER_JS}},
        http(REG, [x + 1100, y], sup + "registrar_portaria_sombra", CRED_SB, "httpCustomAuth",
             "={{ JSON.stringify({ p_loja_id: " + LOJA + ", p_remetente: " + ND + ".remetenteNumero, "
             "p_mensagem_externa_id: ($('Webhook').isExecuted ? ($('Webhook').first().json.body?.data?.key?.id ?? null) : null), "
             "p_texto: " + ND + ".mensagemTexto || '', p_classificacao: $json.classificacao, p_motivo: $json.motivo, "
             "p_trecho: $json.trecho, p_modelo: '" + PP.MODELO + "' }) }}", 5000),
    ]
    wf["nodes"] += novos
    C[NEL]["main"][1] = saida_cliente + [{"node": PREP, "type": "main", "index": 0}]
    C[PREP] = {"main": [[{"node": USAR, "type": "main", "index": 0}]]}
    C[USAR] = {"main": [[{"node": MONT, "type": "main", "index": 0}], []]}
    C[MONT] = {"main": [[{"node": IA, "type": "main", "index": 0}]]}
    C[IA] = {"main": [[{"node": LER, "type": "main", "index": 0}]]}
    C[LER] = {"main": [[{"node": REG, "type": "main", "index": 0}]]}
    return [f"  + 6 nos 'Sombra: ...' (ramo paralelo, abaixo de tudo, y={y})",
            f"  ~ {NEL} (cliente) -> Verificar Origem (inalterado) + {PREP}"]


def checar(wf, antes):
    N = {n["name"]: n for n in wf["nodes"]}; C = wf["connections"]; erros = []
    novos = [PREP, USAR, MONT, IA, LER, REG]
    if len(wf["nodes"]) != len(antes["nodes"]) + 6: erros.append("numero de nos inesperado")
    if [x["node"] for x in C[NEL]["main"][1]] != ["Verificar Origem", PREP]: erros.append("saida cliente errada")
    if C[NEL]["main"][0] != antes["connections"][NEL]["main"][0]: erros.append("saida de comandos mudou")
    for n in [PREP, MONT, IA, LER, REG]:
        if N[n].get("onError") != "continueRegularOutput": erros.append(f"{n} sem continuar-em-falha")
    ymax_antigo = max(n["position"][1] for n in antes["nodes"])
    if any(N[n]["position"][1] <= ymax_antigo for n in novos): erros.append("sombra nao esta abaixo do ramo principal")
    s = json.dumps([N[n] for n in novos])
    if IAMOD.ENV.get("OPENROUTER_API_KEY", "x") in s or IAMOD.ENV.get("SUPABASE_SERVICE_KEY", "x") in s: erros.append("chave escrita no workflow")
    mudou = [n["name"] for n in antes["nodes"] if json.dumps(n, sort_keys=True) != json.dumps(N.get(n["name"]), sort_keys=True)]
    if mudou: erros.append(f"nos existentes alterados: {mudou}")
    outras = {k: v for k, v in antes["connections"].items() if k != NEL}
    if any(C.get(k) != v for k, v in outras.items()): erros.append("outras conexoes mudaram")
    return erros


def main():
    a = sys.argv[1:]
    if "--reverter" in a:
        snap = json.loads(ESTADO.read_text())["snapshot"] if ESTADO.exists() else None
        if not snap: sys.exit("erro: nao ha snapshot salvo")
        wf = json.loads(pathlib.Path(snap).read_text()); d = gravar(wf)
        print(f"REVERTIDO para {wf['versionId']}. nova {d['versionId']} | ativo={d['active']}"); return
    wf = req("GET", f"workflows/{WID}"); antes = json.loads(json.dumps(wf))
    print(f"antes: {wf['versionId']} | {len(wf['nodes'])} nos | ultima edicao {wf['updatedAt']}\n\nmudancas:")
    print("\n".join(transformar(wf)))
    erros = checar(wf, antes)
    print("\ntravas:", "todas ok" if not erros else erros)
    if erros: sys.exit("nada gravado")
    if "--aplicar" not in a:
        print("--- SIMULACAO, nada gravado ---"); return
    agora = datetime.datetime.now()
    snap = BK / f"workflow_{WID}_{antes['versionId']}_{agora:%Y%m%d-%H%M%S}.json"
    snap.write_text(json.dumps(antes)); snap.chmod(0o600)
    ESTADO.write_text(json.dumps({"snapshot": str(snap), "versao_antes": antes["versionId"]})); ESTADO.chmod(0o600)
    d = gravar(wf)
    print(f"GRAVADO. {antes['versionId']} -> {d['versionId']} | ativo={d['active']} | ativa=nova? {d['activeVersionId'] == d['versionId']}")
    print("travas no que ficou gravado:", "todas ok" if not checar(d, antes) else checar(d, antes))


if __name__ == "__main__":
    main()
