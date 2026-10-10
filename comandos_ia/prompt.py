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
MODELO = {"openrouter": "anthropic/claude-opus-5.5", "anthropic": "claude-opus-5-5"}[PROVEDOR]
ESFORCO = "low"          # tarefa curta e fechada: traducao para vocabulario fixo
MAX_TOKENS = 2048        # cabe o raciocinio em esforco baixo + um JSON pequeno

URL = {"openrouter": "https://openrouter.ai/api/v1/chat/completions",
       "anthropic": "https://api.anthropic.com/v1/messages"}
API_VERSION = "2023-06-01"
# Fallback no servidor da Anthropic quando o modelo recusa por politica
# (so API direta; Haiku nao tem).
BETA_FALLBACK = "server-side-fallback-2026-07-01"

SYSTEM_PROMPT = """\
Você traduz mensagens de WhatsApp para comandos de um sistema que distribui
leads entre os vendedores de uma revenda de veículos. Quem escreve é um
gerente ou um vendedor da própria loja — nunca um cliente.

Responda só o comando, no formato exato do vocabulário abaixo, ou string vazia
quando a mensagem não for um pedido ao sistema.

VOCABULÁRIO DO GERENTE
  menu
  status                       resumo da loja
  leads                        leads da loja
  listar vendedores
  inserir vendedor <Nome> <telefone>
  pausar <Nome>                o vendedor deixa de receber leads
  reativar <Nome>              volta a receber leads
  excluir vendedor <Nome>      sai da fila de vez
  sim                          confirma o que o sistema acabou de perguntar
  nao                          cancela

VOCABULÁRIO DO VENDEDOR
  menu
  meus leads
  status                       resumo dele
  sim
  nao

REGRAS
- Use só o vocabulário do papel de quem escreveu.
- Nome de vendedor que já existe: escreva exatamente como está na lista de
  vendedores da loja, mesmo que a mensagem use apelido, diminutivo, minúscula,
  artigo ("a Giu", "o japinha") ou erro de digitação — desde que só um nome da
  lista sirva. Se mais de um servir, ou nenhum, escreva o nome como veio.
- Vendedor novo (inserir): o nome é o que a pessoa escreveu.
- Telefone: copie só os dígitos que estão na mensagem. Nunca invente,
  complete ou corrija dígitos. Sem telefone na mensagem, não escreva telefone.
- "sim", "pode", "isso", "confirma", "manda ver" e afins viram `sim`.
  "não", "cancela", "deixa", "esquece" e afins viram `nao`.
- Nunca escreva "confirmar".
- Saudação, agradecimento, conversa, ou pedido que nenhum comando atende:
  string vazia.
- Um pedido só. Se vier mais de um, traduza o primeiro.
"""

SCHEMA = {
    "type": "object",
    "properties": {"comando": {"type": "string"}},
    "required": ["comando"],
    "additionalProperties": False,
}

EXEMPLOS = [
    ("gerente", "pausa a giu aí", "pausar Giu"),
    ("gerente", "quem tá na fila hoje?", "listar vendedores"),
    ("gerente", "coloca o Marcos, 19 98123-4567", "inserir vendedor Marcos 19 98123-4567"),
    ("gerente", "pode", "sim"),
    ("vendedor", "quais leads são meus?", "meus leads"),
    ("gerente", "bom dia!", ""),
]


def montar_usuario(texto: str, papel: str, vendedores: list[str]) -> str:
    exemplos = "\n".join(f'  [{p}] "{t}" -> "{c}"' for p, t, c in EXEMPLOS)
    return (
        f"Exemplos (outra loja, nomes fictícios):\n{exemplos}\n\n"
        f"Vendedores desta loja: {', '.join(vendedores) if vendedores else '(nenhum)'}\n"
        f"Papel de quem escreveu: {papel}\n"
        f"Mensagem:\n{texto}"
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


def extrair_comando(resposta: dict, provedor: str = PROVEDOR) -> str | None:
    """Comando sugerido, ou None se a resposta nao serve (recusa, corte, JSON
    invalido). None = o n8n manda o texto original, como sem IA."""
    if provedor == "openrouter":
        try:
            esc = resposta["choices"][0]
            if esc.get("finish_reason") not in ("stop", None):
                return None
            return str(json.loads(esc["message"]["content"]).get("comando", "")).strip()
        except (KeyError, IndexError, TypeError, ValueError, AttributeError):
            return None
    if resposta.get("stop_reason") not in ("end_turn", None):
        return None
    for bloco in resposta.get("content", []):
        if bloco.get("type") == "text":
            try:
                return str(json.loads(bloco["text"]).get("comando", "")).strip()
            except (ValueError, AttributeError):
                return None
    return None
