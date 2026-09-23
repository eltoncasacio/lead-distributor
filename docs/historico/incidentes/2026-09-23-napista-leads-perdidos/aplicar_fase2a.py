#!/usr/bin/env python3
"""Fase 2A: reescreve o parser 'Separar Leads NaPista'.

Nao muda comportamento — so torna o dado honesto. Hoje o no le
templateMessage.hydratedTemplate.hydratedContentText, caminho undefined em
placeholderMessage (9 de 14 mensagens), e por ter onError
continueRegularOutput emite o OBJETO DE ERRO como dado. Passa a ler de
Normaliza Dados (que tem cadeia de fallback), com try/catch, devolvendo
sempre parse_ok true|false — nunca [] e nunca objeto de erro.

  python3 aplicar_fase2a.py                          simula
  python3 aplicar_fase2a.py --aplicar                 grava (03h-05h)
  python3 aplicar_fase2a.py --aplicar --fora-da-janela
  python3 aplicar_fase2a.py --reverter
Requer N8N_KEY."""
import json, os, sys, urllib.request, datetime

KEY = os.environ.get("N8N_KEY")
if not KEY: sys.exit("erro: exporte N8N_KEY")
B, WID, NO = "https://n8n.yavoh.cloud/api/v1", "Qj200sqS9544ao3d", "Separar Leads NaPista"

def req(m, p, body=None):
    r = urllib.request.Request(f"{B}/{p}", method=m,
        data=json.dumps(body).encode() if body else None)
    r.add_header("X-N8N-API-KEY", KEY)
    if body: r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=60) as x: return json.loads(x.read())

NOVO = r'''// Le de Normaliza Dados, que ja resolve template, conversation,
// extendedText e caption. O caminho antigo ia direto em
// templateMessage.hydratedTemplate.hydratedContentText, undefined em
// placeholderMessage. Sempre devolve parse_ok; nunca [] nem objeto de erro.
function extrair(texto) {
  const t = String(texto || '');
  const wa = t.match(/wa\.me\/\+?(\d{10,})/);
  const solto = t.match(/(?:^|[^\d])(\d{2}\s?9?\d{4}[-\s]?\d{4})(?!\d)/);
  const tel = wa ? wa[1] : (solto ? solto[1].replace(/\D/g, '') : null);

  const n = t.match(/\*\s*([^*]+?)\s*\*/);
  const nome = n ? n[1].trim() : null;

  let anuncio = null;
  const v = t.match(/Ve[ií]culo de interesse:\s*\*?([^*\n]+)\*?/i);
  if (v) anuncio = v[1].trim();
  else {
    const todos = t.match(/\*[^*]+\*/g) || [];
    if (todos.length > 1) anuncio = todos[1].replace(/\*/g, '').trim();
  }
  return { tel: tel, nome: nome, anuncio: anuncio };
}

const vazio = { titulo: 'Lead NaPista sem conteudo', cliente: null,
                mensagem: '', telefone: null, anuncio: null };
try {
  const texto = $('Normaliza Dados').item.json.mensagemTexto;
  if (!texto || !String(texto).trim()) {
    return [{ json: Object.assign({}, vazio, { parse_ok: false,
      parse_erro: 'mensagem sem texto (provavel placeholderMessage)' }) }];
  }
  const r = extrair(texto);
  return [{ json: { parse_ok: true, parse_erro: null,
    titulo: 'Novo lead recebido!', cliente: r.nome, mensagem: texto,
    telefone: r.tel, anuncio: r.anuncio } }];
} catch (e) {
  return [{ json: Object.assign({}, vazio, { parse_ok: false,
    parse_erro: String((e && e.message) || e) }) }];
}
'''

reverter = "--reverter" in sys.argv
aplicar = "--aplicar" in sys.argv or reverter
agora = datetime.datetime.now()
if aplicar and not (3 <= agora.hour < 5) and "--fora-da-janela" not in sys.argv:
    sys.exit(f"!! {agora:%H:%M} fora da janela 03h-05h BRT.\n"
             "   Repita com --fora-da-janela para aplicar assim mesmo.")

wf = req("GET", f"workflows/{WID}")
print(f"antes: versionId {wf.get('versionId')} | {len(wf['nodes'])} nos")
alvo = next(n for n in wf["nodes"] if n["name"] == NO)
atual = alvo["parameters"].get("jsCode", "")
ja = "parse_ok" in atual
print(f"estado: {'JA REESCRITO' if ja else 'codigo original'} | onError={alvo.get('onError','stopWorkflow')}")

if reverter: sys.exit("reverter: restaure o versionId anterior pela version history do n8n")
if ja: sys.exit("nada a fazer")

alvo["parameters"]["jsCode"] = NOVO
alvo.pop("onError", None)   # parser nunca usa continueRegularOutput

print("\nmudancas:")
print("  - jsCode reescrito (le de Normaliza Dados, try/catch, parse_ok)")
print("  - onError continueRegularOutput REMOVIDO")
print("  - campos novos na saida: parse_ok, parse_erro, anuncio")
print("  - campos preservados: titulo, cliente, mensagem, telefone")

if not aplicar:
    print("\n--- SIMULACAO, nada gravado ---"); sys.exit(0)

novo = req("PUT", f"workflows/{WID}", {"name": wf["name"], "nodes": wf["nodes"],
    "connections": wf["connections"], "settings": wf.get("settings", {})})
print(f"\nGRAVADO. versionId: {novo.get('versionId')}")
d = req("GET", f"workflows/{WID}")
a = next(n for n in d["nodes"] if n["name"] == NO)
print(f"conferindo: {len(d['nodes'])} nos | active={d.get('active')}")
print(f"  parse_ok no codigo: {'parse_ok' in a['parameters']['jsCode']}")
print(f"  onError: {a.get('onError','(removido)')}")
