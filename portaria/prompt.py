"""Portaria — prompt, schema e travas. FONTE UNICA.

O documento [docs/specs/tecnica/07-portaria-classificacao.md] explica o
raciocinio; este arquivo e o que efetivamente roda. Se os dois divergirem,
**este arquivo ganha** e o documento e que esta errado — foi divergencia entre
doc e sistema que gerou a auditoria de 2026-09-11.

O mesmo prompt e schema usados aqui devem ser os colados no no do n8n. Quando
mudar aqui, mude la, e rode `portaria/avaliar.py` de novo antes de subir.
"""

MODELO = "claude-opus-5"

SYSTEM_PROMPT = """\
Você classifica mensagens que chegam no WhatsApp de uma revenda de veículos
usados no interior de São Paulo. Decida em qual categoria a mensagem se
encaixa e extraia o que der.

CATEGORIAS

lead_novo — pessoa interessada em comprar, trocar, financiar ou vender um
  veículo para a loja. Inclui quem pergunta sobre um anúncio, pede simulação,
  oferece o próprio carro em troca ou consignação, ou pergunta se aprova
  financiamento no nome dela.

pos_venda — pessoa que JÁ COMPROU desta loja e escreve sobre revisão,
  garantia, documentação, emplacamento ou pós-venda. O sinal é passado:
  "comprei", "peguei o carro", "da minha compra".

nao_lead — não é cliente em potencial. Cobrança, boleto, fatura, aviso de
  banco ou operadora, marketing, oferta comercial B2B, corretor de outro
  ramo, engano de número.

incerto — use sempre que não tiver convicção. Não force uma categoria.

REGRA DE CUSTO ASSIMÉTRICO

Errar chamando de nao_lead uma mensagem que era cliente faz a loja perder
uma venda e o cliente nunca ser respondido. Errar mandando ruído para um
vendedor custa trinta segundos de atenção dele. Na dúvida, escolha incerto.
Só use nao_lead quando a mensagem for inequivocamente comercial ou
automática.

EVIDÊNCIA

Em trecho_evidencia, copie um pedaço LITERAL da mensagem que justifica sua
decisão — caracteres exatos, sem parafrasear. Se não conseguir citar um
trecho literal, use incerto.

TELEFONE

Só preencha telefone_cliente se um número aparecer escrito na mensagem.
Nunca deduza, nunca complete, nunca invente. Sem número escrito, use null.\
"""

# Exemplos reais da Renato Motors. Ver o spec para a origem de cada um.
FEW_SHOT = [
    ("Olá! Tenho interesse e queria mais informações, por favor.",
     {"classificacao": "lead_novo", "intencao": "comprar", "confianca": 0.93,
      "motivo": "demonstra interesse e pede informações",
      "categoria_nao_lead": None, "nome_cliente": None, "telefone_cliente": None,
      "anuncio": None, "trecho_evidencia": "Tenho interesse e queria mais informações"}),
    ("Trnho interesse no fusion, fariam permuta?",
     {"classificacao": "lead_novo", "intencao": "vender_ou_trocar", "confianca": 0.95,
      "motivo": "interesse em veículo com proposta de permuta",
      "categoria_nao_lead": None, "nome_cliente": None, "telefone_cliente": None,
      "anuncio": "Fusion", "trecho_evidencia": "interesse no fusion, fariam permuta"}),
    ("Tenho um kia soul 2015",
     {"classificacao": "lead_novo", "intencao": "vender_ou_trocar", "confianca": 0.71,
      "motivo": "oferece o próprio carro — consignação ou troca",
      "categoria_nao_lead": None, "nome_cliente": None, "telefone_cliente": None,
      "anuncio": None, "trecho_evidencia": "Tenho um kia soul 2015"}),
    ("Bom dia, aqui é o Josiel que comprou o Palio na sexta-feira, preciso "
     "fazer aquela revisãozinha para ativar a garantia dele",
     {"classificacao": "pos_venda", "intencao": "servico", "confianca": 0.96,
      "motivo": "já comprou e pede revisão de garantia",
      "categoria_nao_lead": None, "nome_cliente": "Josiel", "telefone_cliente": None,
      "anuncio": None, "trecho_evidencia": "que comprou o Palio na sexta-feira"}),
    ("Olá! Informamos que sua fatura já está disponível, com vencimento em "
     "11/05. O boleto foi enviado para o seu e-mail",
     {"classificacao": "nao_lead", "intencao": "outro", "confianca": 0.97,
      "motivo": "aviso automático de cobrança",
      "categoria_nao_lead": "cobranca", "nome_cliente": None, "telefone_cliente": None,
      "anuncio": None, "trecho_evidencia": "sua fatura já está disponível, com vencimento"}),
    ("Oiee, eu sou a Josi e estou em um pré-lançamento de apartamentos no "
     "Bairro Parque Gabriel em Hortolândia-SP",
     {"classificacao": "nao_lead", "intencao": "outro", "confianca": 0.95,
      "motivo": "marketing de outro ramo",
      "categoria_nao_lead": "marketing", "nome_cliente": "Josi", "telefone_cliente": None,
      "anuncio": None, "trecho_evidencia": "pré-lançamento de apartamentos"}),
]

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["classificacao", "intencao", "confianca", "motivo",
                 "categoria_nao_lead", "nome_cliente", "telefone_cliente",
                 "anuncio", "trecho_evidencia"],
    "properties": {
        "classificacao": {"enum": ["lead_novo", "pos_venda", "nao_lead", "incerto"]},
        "intencao": {"enum": ["comprar", "vender_ou_trocar", "servico", "outro"]},
        "confianca": {"type": "number", "minimum": 0, "maximum": 1},
        "motivo": {"type": "string", "maxLength": 140},
        "categoria_nao_lead": {"type": ["string", "null"],
                               "enum": ["cobranca", "spam", "marketing", "pessoal",
                                        "engano", "outro", None]},
        "nome_cliente": {"type": ["string", "null"]},
        "telefone_cliente": {"type": ["string", "null"]},
        "anuncio": {"type": ["string", "null"]},
        "trecho_evidencia": {"type": ["string", "null"]},
    },
}


def so_digitos(s):
    return "".join(c for c in str(s or "") if c.isdigit())


def aplicar_travas(ia, texto, payload_bruto=""):
    """Prompt e pedido; codigo e garantia.

    Duas travas, ambas do spec:
      - telefone so vale se os digitos aparecerem LITERALMENTE no payload
      - trecho_evidencia que nao seja substring literal do texto forca `incerto`

    Devolve (resultado_ajustado, lista_de_travas_que_dispararam).
    """
    out = dict(ia)
    disparos = []

    tel = so_digitos(ia.get("telefone_cliente"))
    bruto = so_digitos(str(payload_bruto) + " " + str(texto))
    tel_ok = len(tel) >= 10 and tel in bruto
    out["telefone_verificado"] = tel_ok
    if ia.get("telefone_cliente") and not tel_ok:
        disparos.append("telefone inventado — descartado")
        out["telefone_cliente"] = None

    trecho = ia.get("trecho_evidencia")
    citou = bool(trecho) and trecho in (texto or "")
    if not citou:
        if out.get("classificacao") != "incerto":
            disparos.append("evidencia nao literal — forcado a incerto")
        out["classificacao"] = "incerto"

    return out, disparos


def decidir(resultado):
    """Traduz a classificacao em acao, conforme a tabela "Decisao final" do spec.

    Fail open por construcao: tudo que nao casa com um caso explicito cai em
    distribuir com duvida.
    """
    c = resultado.get("classificacao")
    conf = resultado.get("confianca") or 0
    if c == "lead_novo" and conf >= 0.80:
        return "distribuir"
    if c == "pos_venda" and conf >= 0.80:
        return "distribuir_sem_contar_lead_novo"
    if c == "nao_lead" and conf >= 0.90:
        return "arquivar"
    return "distribuir_com_duvida"
