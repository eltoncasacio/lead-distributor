"""Comandos por WhatsApp com IA — prompt, schema e corpo da requisicao. FONTE UNICA.

A IA so TRADUZ a frase livre do gerente/vendedor para um comando do
vocabulario que ja existe. Ela nao executa nada: a sugestao vai para
`executar_comando_ia` no Postgres, que aplica as travas (verbo conhecido, sem
"confirmar", sem telefone inventado) e cai no texto original se a sugestao nao
passar. Qualquer escrita continua exigindo eco + "sim" do humano.

O corpo montado por `corpo_requisicao()` e o mesmo que o no do n8n envia
(docs/dev/fase-a/aplicar_comandos_ia_n8n.py importa daqui). Mudou aqui, rode
`comandos_ia/avaliar.py` de novo antes de subir.
"""
import json

# Provedor: "openrouter" (chave OPENROUTER_API_KEY, formato de chat da OpenAI,
# decisao do dono em 2026-10-10) ou "anthropic" (ANTHROPIC_API_KEY, API direta).
# O modelo e escolhido pela avaliacao (avaliar.py) — decisao do dono.
PROVEDOR = "openrouter"
MODELO = {"openrouter": "anthropic/claude-haiku-5.5", "anthropic": "claude-haiku-5-5"}[PROVEDOR]  # escolha do dono, 2026-10-10
ESFORCO = "low"          # tarefa curta e fechada: traducao para vocabulario fixo
MAX_TOKENS = 2048        # cabe o raciocinio em esforco baixo + um JSON pequeno
LIMITE_TEXTO = 300      # so o comeco da mensagem vai para a IA: limita o custo por chamada

URL = {"openrouter": "https://openrouter.ai/api/v1/chat/completions",
       "anthropic": "https://api.anthropic.com/v1/messages"}
API_VERSION = "2023-06-01"
# Fallback no servidor da Anthropic quando o modelo recusa por politica
# (so API direta; Haiku nao tem).
BETA_FALLBACK = "server-side-fallback-2026-07-01"

SYSTEM_PROMPT = """\
Você interpreta mensagens de WhatsApp para um sistema que distribui leads
entre os vendedores de uma revenda de veículos. Quem escreve é um gerente ou
um vendedor da própria loja — nunca um cliente. Você não executa nada: só diz
qual ação a pessoa pediu. O sistema confere tudo e pede confirmação antes de
qualquer mudança.

AÇÕES DO GERENTE
  menu               lista de comandos / ajuda
  status             resumo da loja
  leads              leads da loja
  listar_vendedores  quem está na fila
  inserir            cadastrar vendedor novo (nome + telefone)
  pausar             vendedor deixa de receber leads por um tempo
  reativar           vendedor volta a receber leads
  excluir            vendedor sai da fila de vez
  sim                confirma o que o sistema acabou de perguntar
  nao                cancela

AÇÕES DO VENDEDOR
  menu, meus_leads, status (resumo dele), sim, nao

E PARA QUALQUER UM
  esclarecer         o pedido é para o sistema, mas falta algo para saber o
                     que fazer: qual vendedor, qual ação, ou mais de um
                     vendedor serve. Escreva em `pergunta` uma pergunta curta.
  nenhum             não é pedido ao sistema: saudação, agradecimento,
                     conversa, assunto de cliente, ou ação que o papel não tem.

CAMPOS
- nome: para pausar/reativar/excluir, o nome EXATO da lista de vendedores da
  loja — mesmo que a mensagem use apelido, diminutivo, artigo ("a Giu", "o
  japinha") ou erro de digitação, desde que só um nome da lista sirva. Se
  nenhum ou mais de um servir, use esclarecer. Para inserir, o nome como a
  pessoa escreveu. Nas demais ações, vazio.
- telefone: só os dígitos que estão na mensagem. Nunca invente, complete ou
  corrija dígitos. Sem telefone na mensagem, vazio.
- pergunta: só quando a ação for esclarecer; senão, vazio.

REGRAS
- Nunca invente nome, telefone ou vendedor.
- pausar x excluir: "tirar da fila", "parar de mandar lead", "dar um tempo",
  folga, férias, "hoje", "mais cedo" = pausar. excluir SÓ quando a mensagem
  disser que é definitivo: saiu da empresa, foi demitido, não trabalha mais
  aqui, ou quando usar o próprio verbo "excluir", "remover" ou "apagar" com
  o nome do vendedor ("exclui o diego"). Excluir é a ação mais grave — se não estiver
  explícito que é definitivo, use pausar; se não der para saber, esclarecer.
- Mensagem curta que só nomeia uma coisa do sistema é pedido para VER essa
  coisa: "vendedores", "equipe", "fila", "time" = listar_vendedores (gerente);
  "leads" = leads (gerente) ou meus_leads (vendedor); "status", "resumo" = status.
  Não pergunte nesses casos.
- Na dúvida entre duas ações, use esclarecer.
- "sim", "pode", "isso", "confirma", "manda ver" e afins: sim.
  "não", "cancela", "deixa", "esquece" e afins: nao.
- Um pedido só. Se vier mais de um, considere o primeiro.
"""

ACOES = ["menu", "status", "leads", "meus_leads", "listar_vendedores", "inserir", "pausar",
         "reativar", "excluir", "sim", "nao", "esclarecer", "nenhum"]

SCHEMA = {
    "type": "object",
    "properties": {
        "acao": {"type": "string", "enum": ACOES},
        "nome": {"type": "string"},
        "telefone": {"type": "string"},
        "pergunta": {"type": "string"},
    },
    "required": ["acao", "nome", "telefone", "pergunta"],
    "additionalProperties": False,
}

# Nomes ficticios, de outra loja, para nao vazar para a lista real.
EXEMPLOS = [
    ("gerente", "pausa a bia aí", {"acao": "pausar", "nome": "Bia"}),
    ("gerente", "quem tá na fila hoje?", {"acao": "listar_vendedores"}),
    ("gerente", "coloca o Marcos, 19 98123-4567", {"acao": "inserir", "nome": "Marcos", "telefone": "19981234567"}),
    ("gerente", "tira ele", {"acao": "esclarecer", "pergunta": "Quem você quer tirar da fila?"}),
    ("gerente", "tira o tonho da fila", {"acao": "pausar", "nome": "Tonho"}),
    ("gerente", "o tonho saiu da empresa", {"acao": "excluir", "nome": "Tonho"}),
    ("gerente", "pode", {"acao": "sim"}),
    ("vendedor", "quais leads são meus?", {"acao": "meus_leads"}),
    ("gerente", "bom dia!", {"acao": "nenhum"}),
]


def montar_usuario(texto: str, papel: str, vendedores: list[str]) -> str:
    def j(d):
        return json.dumps({"acao": d["acao"], "nome": d.get("nome", ""), "telefone": d.get("telefone", ""),
                           "pergunta": d.get("pergunta", "")}, ensure_ascii=False)
    exemplos = "\n".join(f'  [{p}] "{t}" -> {j(c)}' for p, t, c in EXEMPLOS)
    return (
        f"Exemplos (outra loja, vendedores Bia e Tonho):\n{exemplos}\n\n"
        f"Vendedores desta loja: {', '.join(vendedores) if vendedores else '(nenhum)'}\n"
        f"Papel de quem escreveu: {papel}\n"
        f"Mensagem:\n{texto[:LIMITE_TEXTO]}"
    )


def corpo_requisicao(texto: str, papel: str, vendedores: list[str], modelo: str = MODELO,
                     provedor: str = PROVEDOR) -> dict:
    if provedor == "openrouter":
        return {
            "model": modelo,
            "max_tokens": MAX_TOKENS,
            "reasoning": {"effort": ESFORCO},
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": "comando", "strict": True, "schema": SCHEMA}},
            "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                         {"role": "user", "content": montar_usuario(texto, papel, vendedores)}],
        }
    corpo = {
        "model": modelo,
        "max_tokens": MAX_TOKENS,
        "system": SYSTEM_PROMPT,
        "output_config": {"effort": ESFORCO, "format": {"type": "json_schema", "schema": SCHEMA}},
        "messages": [{"role": "user", "content": montar_usuario(texto, papel, vendedores)}],
    }
    if not modelo.startswith("claude-haiku"):
        corpo["fallbacks"] = "default"
    return corpo


def headers(api_key: str, modelo: str = MODELO, provedor: str = PROVEDOR) -> dict:
    if provedor == "openrouter":
        return {"content-type": "application/json", "authorization": f"Bearer {api_key}",
                "x-title": "lead-distributor comandos"}
    h = {"content-type": "application/json", "x-api-key": api_key, "anthropic-version": API_VERSION}
    if not modelo.startswith("claude-haiku"):
        h["anthropic-beta"] = BETA_FALLBACK
    return h


def extrair_comando(resposta: dict, provedor: str = PROVEDOR) -> dict | None:
    """Sugestao estruturada {acao, nome, telefone, pergunta}, ou None se a resposta nao serve (recusa, corte, JSON
    invalido). None = o n8n manda o texto original, como sem IA."""
    if provedor == "openrouter":
        try:
            esc = resposta["choices"][0]
            if esc.get("finish_reason") not in ("stop", None):
                return None
            return _validar(json.loads(esc["message"]["content"]))
        except (KeyError, IndexError, TypeError, ValueError, AttributeError):
            return None
    if resposta.get("stop_reason") not in ("end_turn", None):
        return None
    for bloco in resposta.get("content", []):
        if bloco.get("type") == "text":
            try:
                return _validar(json.loads(bloco["text"]))
            except (ValueError, AttributeError):
                return None
    return None


def _validar(d) -> dict | None:
    if not isinstance(d, dict) or d.get("acao") not in ACOES:
        return None
    return {k: str(d.get(k, "") or "").strip() for k in ("acao", "nome", "telefone", "pergunta")}
