#!/usr/bin/env python3
"""Aviso curto para cliente que ja tem vendedor + repasse de audio/foto (2026-10-17).

Queixa dos vendedores da Fitcar: cada mensagem de um cliente que ja e lead
chegava como um "🚗 Novo Lead" completo (cabecalho + links de mensagem pronta).
Em um dia, 9 avisos para o mesmo cliente. E audio/foto sem legenda chegavam
como "Novo Lead" vazio — o vendedor nao sabia que havia um audio.

Decisao do dono (2026-10-17):
- primeira mensagem do cliente: "Novo Lead" completo, como antes;
- seguintes (`duplicado = true` em `distribuir_lead`): so o texto, curto, com
  link para responder;
- audio, foto, video e documento: o proprio arquivo e repassado ao vendedor
  (a Evolution manda o base64 no webhook — `webhookBase64: true`).

Nao muda contagem de lead nem regra de distribuicao: so o formato do aviso.
Cliente que volta por OUTRO anuncio continua `duplicado = false` (Passo 2 de
05-deduplicacao.md) e recebe o aviso completo.

Mudancas:
  ~ Montar Notificação: formato curto quando duplicado; rotulo de midia;
    devolve midiaEndpoint/midiaBody quando ha arquivo para repassar.
  + Tem Mídia?  (IF)  entre Encaminhar ao Vendedor e Loop Over Items
  + Encaminhar Mídia (HTTP, continua em falha) -> Loop Over Items

  python3 aplicar_aviso_curto_midia_n8n.py              simula
  python3 aplicar_aviso_curto_midia_n8n.py --aplicar
  python3 aplicar_aviso_curto_midia_n8n.py --reverter
"""
import datetime, importlib.util, json, pathlib, sys, uuid

AQUI = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ia", AQUI / "aplicar_comandos_ia_n8n.py")
IAMOD = importlib.util.module_from_spec(spec); spec.loader.exec_module(IAMOD)
req, gravar, BK, WID = IAMOD.req, IAMOD.gravar, IAMOD.BK, IAMOD.WID
ESTADO = BK / "aviso_curto_midia_estado.json"
MONTAR, ENC, LOOP = "Montar Notificação", "Encaminhar ao Vendedor", "Loop Over Items"
TEM, ENC_MIDIA = "Tem Mídia?", "Encaminhar Mídia"

# Inserido logo antes do bloco "9. MONTAR MENSAGEM FINAL" do no original.
MIDIA_JS = r"""
// =============================
// 8b. MIDIA E CLIENTE QUE JA TEM VENDEDOR (2026-10-17)
// =============================
// duplicado = cliente ja e lead deste vendedor: aviso curto, sem template.
// Midia: so existe quando a mensagem veio pelo webhook da Evolution (WhatsApp).
const duplicado = vendedor.duplicado === true;
let midiaRotulo = '';
let midiaEndpoint = '';
let midiaBody = null;
try {
  if ($('Webhook').isExecuted) {
    const d = $('Webhook').first().json.body.data || {};
    const msg = d.message || {};
    const tipo = d.messageType || '';
    const info = msg[tipo] || {};
    const b64 = msg.base64 || '';
    const numero = vendedor.vendedor_numero_whatsapp;
    if (tipo === 'audioMessage') {
      midiaRotulo = `🎤 Áudio${info.seconds ? ' (' + info.seconds + 's)' : ''}`;
      if (b64) { midiaEndpoint = 'sendWhatsAppAudio'; midiaBody = { number: numero, audio: b64 }; }
    } else if (tipo === 'imageMessage' || tipo === 'videoMessage' || tipo === 'documentMessage') {
      const tipoMidia = tipo === 'imageMessage' ? 'image' : (tipo === 'videoMessage' ? 'video' : 'document');
      midiaRotulo = tipo === 'imageMessage' ? '📷 Foto' : (tipo === 'videoMessage' ? '🎥 Vídeo' : `📄 Documento${info.fileName ? ': ' + info.fileName : ''}`);
      if (b64) {
        midiaEndpoint = 'sendMedia';
        midiaBody = { number: numero, mediatype: tipoMidia, mimetype: info.mimetype || '', media: b64,
                      fileName: info.fileName || (tipoMidia + (tipoMidia === 'image' ? '.jpg' : tipoMidia === 'video' ? '.mp4' : '')) };
      }
    } else if (tipo === 'stickerMessage') {
      midiaRotulo = '🙂 Figurinha';
    } else if (tipo === 'reactionMessage') {
      midiaRotulo = `Reagiu com ${info.text || 'uma reação'}`;
    } else if (tipo === 'locationMessage') {
      midiaRotulo = '📍 Localização';
    } else if (tipo === 'contactMessage' || tipo === 'contactsArrayMessage') {
      midiaRotulo = '👤 Contato';
    }
  }
} catch (e) {}
if (midiaRotulo && midiaBody) midiaRotulo += ' — segue abaixo';
const conteudo = [mensagemTexto, midiaRotulo].filter(Boolean).join('\n') || '(mensagem sem texto)';
"""

ANTIGO_DETALHE = """const detalheTexto = anuncio
  ? `Anúncio: ${anuncio}`
  : (mensagemTexto ? `Mensagem: ${mensagemTexto}` : '');

const mensagemFormatada = origem === 'Mobiauto' ?\x20
  `${mensagemTexto} ${linksSection}` :"""  # \x20: o no original tem espaco no fim da linha

NOVO_DETALHE = """const detalheTexto = anuncio
  ? `Anúncio: ${anuncio}${midiaRotulo ? '\\n' + midiaRotulo : ''}`
  : ((mensagemTexto || midiaRotulo) ? `Mensagem: ${conteudo}` : '');

const mensagemFormatada = (duplicado && origem !== 'Mobiauto') ?
  `💬 *${nomeCliente}* · ${telefoneClienteFormatado}
${conteudo}

Responder: https://wa.me/${telefoneClienteFormatado}` :
  origem === 'Mobiauto' ?
  `${mensagemTexto} ${linksSection}` :"""

ANTIGO_RET = """    vendedor_numero_whatsapp: vendedor.vendedor_numero_whatsapp
  },"""
NOVO_RET = """    vendedor_numero_whatsapp: vendedor.vendedor_numero_whatsapp,
    midiaEndpoint,
    midiaBody
  },"""
MARCA = "// =============================\n// 9. MONTAR MENSAGEM FINAL"


def estado():
    return json.loads(ESTADO.read_text()) if ESTADO.exists() else {}


def salvar_estado(**kw):
    e = estado(); e.update(kw); ESTADO.write_text(json.dumps(e, indent=1)); ESTADO.chmod(0o600)


def novo_js(js):
    for a in (MARCA, ANTIGO_DETALHE, ANTIGO_RET):
        if js.count(a) != 1: sys.exit(f"erro: trecho esperado nao encontrado 1x em {MONTAR}: {a[:50]!r}")
    return (js.replace(MARCA, MIDIA_JS.strip("\n") + "\n\n" + MARCA)
              .replace(ANTIGO_DETALHE, NOVO_DETALHE).replace(ANTIGO_RET, NOVO_RET))


def nos_novos(enc):
    x, y = enc["position"]
    tem = {"id": str(uuid.uuid4()), "name": TEM, "type": "n8n-nodes-base.if", "typeVersion": 2.2,
           "position": [x + 224, y],
           "parameters": {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                                         "combinator": "and",
                                         "conditions": [{"id": "cond-tem-midia", "leftValue": f"={{{{ $('{MONTAR}').item.json.midiaEndpoint }}}}",
                                                         "rightValue": "", "operator": {"type": "string", "operation": "notEmpty", "singleValue": True}}]},
                          "looseTypeValidation": True, "options": {}}}
    midia = {"id": str(uuid.uuid4()), "name": ENC_MIDIA, "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.3,
             "position": [x + 448, y - 160], "onError": "continueRegularOutput",
             "parameters": {"method": "POST",
                            "url": f"={{{{ $('{MONTAR}').item.json.evolutionServerUrl }}}}/message/{{{{ $('{MONTAR}').item.json.midiaEndpoint }}}}/{{{{ $('{MONTAR}').item.json.instancia }}}}",
                            "sendHeaders": True,
                            "headerParameters": {"parameters": [{"name": "apikey", "value": f"={{{{ $('{MONTAR}').item.json.evolutionApiKey }}}}"}]},
                            "sendBody": True, "specifyBody": "json",
                            "jsonBody": f"={{{{ JSON.stringify($('{MONTAR}').item.json.midiaBody) }}}}",
                            "options": {"timeout": 60000}}}
    return tem, midia


def main():
    a = sys.argv[1:]
    if "--reverter" in a:
        snap = estado().get("snapshot")
        if not snap: sys.exit("erro: nao ha snapshot salvo")
        wf = json.loads(pathlib.Path(snap).read_text()); d = gravar(wf)
        print(f"REVERTIDO para {wf['versionId']}. nova {d['versionId']} | ativo={d['active']}")
        return
    if "--js" in a:  # imprime o codigo novo do no, para teste local
        wf = req("GET", f"workflows/{WID}")
        print(novo_js({n["name"]: n for n in wf["nodes"]}[MONTAR]["parameters"]["jsCode"])); return
    wf = req("GET", f"workflows/{WID}"); antes = json.loads(json.dumps(wf))
    N = {n["name"]: n for n in wf["nodes"]}
    if TEM in N or ENC_MIDIA in N: sys.exit("ja aplicado")
    erros = []
    if wf["connections"][ENC]["main"] != [[{"node": LOOP, "type": "main", "index": 0}]]:
        erros.append(f"{ENC} nao vai mais so para {LOOP}")
    if wf["connections"][MONTAR]["main"] != [[{"node": ENC, "type": "main", "index": 0}]]:
        erros.append(f"{MONTAR} nao vai mais so para {ENC}")
    N[MONTAR]["parameters"]["jsCode"] = novo_js(N[MONTAR]["parameters"]["jsCode"])
    tem, midia = nos_novos(N[ENC])
    wf["nodes"] += [tem, midia]
    c = wf["connections"]
    c[ENC] = {"main": [[{"node": TEM, "type": "main", "index": 0}]]}
    c[TEM] = {"main": [[{"node": ENC_MIDIA, "type": "main", "index": 0}], [{"node": LOOP, "type": "main", "index": 0}]]}
    c[ENC_MIDIA] = {"main": [[{"node": LOOP, "type": "main", "index": 0}]]}
    mudou = [n["name"] for n in antes["nodes"] if json.dumps(n, sort_keys=True) != json.dumps(N[n["name"]], sort_keys=True)]
    if mudou != [MONTAR]: erros.append(f"mudancas inesperadas: {mudou}")
    print(f"antes: {antes['versionId']}\n  ~ {MONTAR}: aviso curto se duplicado; rotulo/repasse de midia"
          f"\n  + {TEM} -> {ENC_MIDIA} (continua em falha) -> {LOOP}\ntravas:", "todas ok" if not erros else erros)
    if erros: sys.exit("nada gravado")
    if "--aplicar" not in a:
        print("--- SIMULACAO, nada gravado ---"); return
    agora = datetime.datetime.now()
    snap = BK / f"workflow_{WID}_{antes['versionId']}_{agora:%Y%m%d-%H%M%S}.json"
    snap.write_text(json.dumps(antes)); snap.chmod(0o600)
    salvar_estado(snapshot=str(snap), versao_antes=antes["versionId"])
    d = gravar(wf)
    g = {n["name"]: n for n in d["nodes"]}
    ok = TEM in g and ENC_MIDIA in g and "midiaEndpoint" in g[MONTAR]["parameters"]["jsCode"]
    print(f"GRAVADO. {antes['versionId']} -> {d['versionId']} | ativo={d['active']} | ativa=nova? {d['activeVersionId'] == d['versionId']} | nos gravados: {ok}")
    salvar_estado(versao_depois=d["versionId"], aplicado_em=agora.isoformat())


if __name__ == "__main__":
    main()
