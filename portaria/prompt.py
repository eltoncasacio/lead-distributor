"""Portaria v3 — prompt, schema e travas. FONTE UNICA.

Desenho (docs/specs/tecnica/07-portaria-classificacao.md, topo): so a mensagem
de NUMERO NOVO (nunca foi lead desta loja) passa por aqui. A IA responde se e
lead; `nao_lead` e ignorado (gravado em silencio), `lead` e `duvida`
distribuem. Erro, recusa, timeout ou resposta invalida = duvida = distribui.

O unico erro caro e chamar de `nao_lead` um cliente. Por isso:
  - o prompt manda usar `nao_lead` so quando for inequivoco;
  - a trava (codigo, nao prompt) exige trecho LITERAL da mensagem para
    `nao_lead` — sem isso vira `duvida`.

Mudou aqui: rode `portaria/avaliar.py` antes de levar ao n8n.
(A versao v2, com 4 categorias e extracao de telefone, esta no historico do git
e na secao "Desenho v2" do spec.)
"""
import json

PROVEDOR = "openrouter"
MODELO = "anthropic/claude-haiku-5.5"      # producao (barato). Iteracao: modelos :free
ESFORCO = "low"
MAX_TOKENS = 1024
LIMITE_TEXTO = 500
URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT = """\
Você lê a PRIMEIRA mensagem que um número desconhecido mandou para o WhatsApp
de uma revenda de veículos usados, e diz se é um possível cliente (lead).

lead — qualquer pessoa que possa estar interessada em comprar, trocar,
  financiar, vender ou consignar um veículo, ou que pergunta algo à loja
  (estoque, preço, disponibilidade, endereço, horário). Inclui mensagens
  automáticas de portais de carros avisando de um interessado, e mensagens
  que só cumprimentam ("bom dia", "olá, tudo bem?") — quem cumprimenta uma
  revenda costuma ser cliente.

nao_lead — SÓ quando for inequívoco que não é cliente:
  - cobrança, boleto, fatura, pendência financeira, aviso de banco,
    operadora ou prestador de serviço;
  - empresa oferecendo produto ou serviço PARA a loja (fornecedor, plataforma,
    sistema, marketing, pesquisa de satisfação de fornecedor);
  - propaganda de outro ramo;
  - conversa claramente pessoal entre conhecidos, sem relação com compra
    de veículo.

duvida — quando não der para ter certeza. Na dúvida entre lead e nao_lead,
  responda duvida: a mensagem será tratada como lead.

CUSTO ASSIMÉTRICO: chamar de nao_lead um cliente faz a loja perder a venda e o
cliente nunca ser respondido. Mandar uma mensagem que não era cliente para o
vendedor custa trinta segundos dele. Use nao_lead só com convicção.

EVIDÊNCIA: em trecho_evidencia, copie um pedaço LITERAL da mensagem (os mesmos
caracteres, sem parafrasear) que justifica a decisão. Para nao_lead isso é
obrigatório; se não conseguir citar, responda duvida.
"""

# Exemplos ficticios, de proposito fora da amostra de avaliacao.
EXEMPLOS = [
    ("Boa tarde, ainda tem aquele Corolla prata do anúncio?", "lead", "ainda tem aquele Corolla prata"),
    ("oi tudo bem", "lead", "oi tudo bem"),
    ("Quero vender meu Gol 2018, vocês avaliam?", "lead", "Quero vender meu Gol 2018"),
    ("Sua fatura de internet vence amanhã. Pague pelo app e evite juros.", "nao_lead", "Sua fatura de internet vence amanhã"),
    ("Olá lojista! Conheça nosso sistema de gestão para revendas, 30 dias grátis.", "nao_lead", "Conheça nosso sistema de gestão para revendas"),
    ("kkkk vc viu o jogo ontem?", "nao_lead", "vc viu o jogo ontem"),
    ("Passei aí ontem mas estava fechado", "duvida", "Passei aí ontem mas estava fechado"),
]

SCHEMA = {
    "type": "object",
    "properties": {
        "classificacao": {"type": "string", "enum": ["lead", "nao_lead", "duvida"]},
        "motivo": {"type": "string"},
        "trecho_evidencia": {"type": "string"},
    },
    "required": ["classificacao", "motivo", "trecho_evidencia"],
    "additionalProperties": False,
}


def montar_usuario(texto: str) -> str:
    ex = "\n".join(f'  "{t}" -> {json.dumps({"classificacao": c, "motivo": "...", "trecho_evidencia": e}, ensure_ascii=False)}'
                   for t, c, e in EXEMPLOS)
    return f"Exemplos:\n{ex}\n\nMensagem:\n{texto[:LIMITE_TEXTO]}"


def corpo_requisicao(texto: str, modelo: str = MODELO, com_esforco: bool = True) -> dict:
    corpo = {
        "model": modelo,
        "max_tokens": MAX_TOKENS,
        "response_format": {"type": "json_schema",
                            "json_schema": {"name": "portaria", "strict": True, "schema": SCHEMA}},
        "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                     {"role": "user", "content": montar_usuario(texto)}],
    }
    if com_esforco:
        corpo["reasoning"] = {"effort": ESFORCO}
    return corpo


def extrair(resposta: dict):
    """dict da IA, ou None se a resposta nao serve (vira duvida nas travas)."""
    try:
        esc = resposta["choices"][0]
        if esc.get("finish_reason") not in ("stop", None):
            return None
        conteudo = esc["message"]["content"]
        if isinstance(conteudo, str):
            conteudo = conteudo.strip()
            if conteudo.startswith("```"):
                conteudo = conteudo.strip("`").split("\n", 1)[-1]
            return json.loads(conteudo)
        return conteudo
    except (KeyError, IndexError, TypeError, ValueError, AttributeError):
        return None


def aplicar_travas(ia, texto: str) -> dict:
    """Garantias em codigo. Qualquer coisa fora do esperado vira `duvida`.

    - classificacao fora de {lead, nao_lead, duvida} -> duvida
    - nao_lead sem trecho literal da mensagem -> duvida
    """
    if not isinstance(ia, dict) or ia.get("classificacao") not in ("lead", "nao_lead", "duvida"):
        return {"classificacao": "duvida", "motivo": "resposta da IA invalida ou ausente", "trecho_evidencia": "",
                "trava": "resposta_invalida"}
    r = {"classificacao": ia["classificacao"], "motivo": str(ia.get("motivo") or "")[:200],
         "trecho_evidencia": str(ia.get("trecho_evidencia") or ""), "trava": None}
    if r["classificacao"] == "nao_lead":
        trecho = r["trecho_evidencia"].strip()
        if len(trecho) < 6 or trecho not in (texto or ""):
            r["classificacao"] = "duvida"
            r["trava"] = "evidencia_nao_literal"
    return r


def decidir(resultado: dict) -> str:
    """'ignorar' so para nao_lead que passou nas travas; o resto distribui."""
    return "ignorar" if resultado.get("classificacao") == "nao_lead" else "distribuir"
