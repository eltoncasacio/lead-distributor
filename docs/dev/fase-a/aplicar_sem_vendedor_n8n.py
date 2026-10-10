#!/usr/bin/env python3
"""Lead sem vendedor disponivel deixa de se perder em silencio (2026-10-10).

Defeito (execucao 9222, Loja Teste sem vendedores): distribuir_lead RECUSA com
erro ("Nenhum vendedor ativo disponivel na loja", HTTP 400) em vez de devolver
vendedor nulo. O no `Distribuir Lead` falhava e a execucao parava: nao chegava
a `Vendedor Encontrado?` -> `Alerta Lead Nao Distribuido`, e `Registrar
Mensagem` (ramo paralelo) tambem nao rodava. Lead perdido sem aviso. Vale para
qualquer loja — na Renato Motors, se todos os vendedores estiverem pausados.

Correcao (sem mexer em distribuir_lead):
  - `Distribuir Lead`: onError = continueRegularOutput (o erro vira item);
  - `Vendedor Encontrado?`: vendedor_id NAO VAZIO (a condicao antiga,
    "!= 'null'", deixaria o item de erro passar como se tivesse vendedor);
  - `Alerta Lead Nao Distribuido`: texto ganha a loja e o motivo.

  python3 aplicar_sem_vendedor_n8n.py              simula
  python3 aplicar_sem_vendedor_n8n.py --aplicar
  python3 aplicar_sem_vendedor_n8n.py --reverter
"""
import datetime, importlib.util, json, pathlib, sys, uuid

AQUI = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ia", AQUI / "aplicar_comandos_ia_n8n.py")
IAMOD = importlib.util.module_from_spec(spec); spec.loader.exec_module(IAMOD)
req, gravar, BK, WID = IAMOD.req, IAMOD.gravar, IAMOD.BK, IAMOD.WID
ESTADO = BK / "sem_vendedor_estado.json"
DIST, ENC, ALERTA = "Distribuir Lead", "Vendedor Encontrado?", "Alerta Lead Nao Distribuido"

ANTES_TXT = "'🚨 *Lead NAO distribuido*\\n\\n'+ 'De: '"
DEPOIS_TXT = ("'🚨 *Lead NAO distribuido*\\n\\n'"
              "+ 'Loja: ' + String($('Preparar Dados Loja').item.json.lojaNome || '?') + '\\n'"
              "+ 'Motivo: ' + String(($json.error && ($json.error.description || $json.error.message)) || $json.error || 'sem vendedor no retorno') + '\\n\\n'"
              "+ 'De: '")


def estado():
    return json.loads(ESTADO.read_text()) if ESTADO.exists() else {}


def salvar_estado(**kw):
    e = estado(); e.update(kw); ESTADO.write_text(json.dumps(e, indent=1)); ESTADO.chmod(0o600)


def transformar(wf):
    N = {n["name"]: n for n in wf["nodes"]}
    if N[DIST].get("onError") == "continueRegularOutput": sys.exit("ja aplicado")
    N[DIST]["onError"] = "continueRegularOutput"
    N[ENC]["parameters"]["conditions"]["conditions"] = [
        {"id": "cond-vendedor-lead", "leftValue": "={{ $json.vendedor_id }}", "rightValue": "",
         "operator": {"type": "string", "operation": "notEmpty", "singleValue": True}}]
    jb = N[ALERTA]["parameters"]["jsonBody"]
    if jb.count(ANTES_TXT) != 1: sys.exit("erro: texto do alerta mudou — revisar")
    N[ALERTA]["parameters"]["jsonBody"] = jb.replace(ANTES_TXT, DEPOIS_TXT)
    return [f"  ~ {DIST}: erro vira item (continueRegularOutput)",
            f"  ~ {ENC}: vendedor_id nao vazio",
            f"  ~ {ALERTA}: texto com loja e motivo"]


def checar(wf, antes):
    N = {n["name"]: n for n in wf["nodes"]}; erros = []
    mudou = sorted(n["name"] for n in antes["nodes"] if json.dumps(n, sort_keys=True) != json.dumps(N[n["name"]], sort_keys=True))
    if mudou != sorted([DIST, ENC, ALERTA]): erros.append(f"mudou alem do esperado: {mudou}")
    if wf["connections"] != antes["connections"]: erros.append("conexoes mudaram")
    if "Motivo: " not in N[ALERTA]["parameters"]["jsonBody"]: erros.append("alerta sem motivo")
    return erros


def main():
    a = sys.argv[1:]
    if "--reverter" in a:
        snap = estado().get("snapshot")
        if not snap: sys.exit("erro: nao ha snapshot salvo")
        wf = json.loads(pathlib.Path(snap).read_text()); d = gravar(wf)
        print(f"REVERTIDO para {wf['versionId']}. nova {d['versionId']} | ativo={d['active']}"); return
    wf = req("GET", f"workflows/{WID}"); antes = json.loads(json.dumps(wf))
    print(f"antes: {wf['versionId']}\n\nmudancas:"); print("\n".join(transformar(wf)))
    erros = checar(wf, antes)
    print("\ntravas:", "todas ok" if not erros else erros)
    if erros: sys.exit("nada gravado")
    if "--aplicar" not in a:
        print("--- SIMULACAO, nada gravado ---"); return
    agora = datetime.datetime.now()
    snap = BK / f"workflow_{WID}_{antes['versionId']}_{agora:%Y%m%d-%H%M%S}.json"
    snap.write_text(json.dumps(antes)); snap.chmod(0o600)
    salvar_estado(snapshot=str(snap), versao_antes=antes["versionId"])
    d = gravar(wf)
    print(f"GRAVADO. {antes['versionId']} -> {d['versionId']} | ativo={d['active']} | ativa=nova? {d['activeVersionId'] == d['versionId']}")
    print("travas no que ficou gravado:", "todas ok" if not checar(d, antes) else checar(d, antes))
    salvar_estado(versao_depois=d["versionId"], aplicado_em=agora.isoformat())


if __name__ == "__main__":
    main()
