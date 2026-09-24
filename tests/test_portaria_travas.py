"""Travas da Portaria — os criterios de bloqueio do ACEITE, como teste.

O ACEITE da Fase 4 lista tres criterios de bloqueio em texto. Aqui eles viram
codigo que roda:

  - "Telefone so aceito se os digitos aparecerem literalmente no payload bruto.
     Teste: forcar o modelo a devolver um numero inventado e confirmar que e
     descartado"
  - "trecho_evidencia que nao for substring literal do texto forca `incerto`"
  - "Fail open: confirmar que a mensagem e distribuida assim mesmo, marcada
     distribuido_com_duvida"

Nao chamam a API. Testam o codigo que roda DEPOIS do modelo — que e onde mora
a garantia. Prompt e pedido; codigo e garantia.
"""
from portaria.prompt import aplicar_travas, decidir


def _ia(**kw):
    base = {
        "classificacao": "lead_novo", "intencao": "comprar", "confianca": 0.95,
        "motivo": "x", "categoria_nao_lead": None, "nome_cliente": None,
        "telefone_cliente": None, "anuncio": None, "trecho_evidencia": None,
    }
    base.update(kw)
    return base


# ------------------------------------------------ trava 1: telefone inventado

def test_telefone_inventado_e_descartado():
    texto = "Tenho interesse no Onix, pode me passar mais informações?"
    saida, disparos = aplicar_travas(
        _ia(telefone_cliente="11987654321", trecho_evidencia="Tenho interesse no Onix"),
        texto, payload_bruto=texto)

    assert saida["telefone_cliente"] is None, "numero inventado passou"
    assert saida["telefone_verificado"] is False
    assert any("inventado" in d for d in disparos)


def test_telefone_que_esta_na_mensagem_e_aceito():
    texto = "Oi, me liga no (19) 99123-4567 que eu quero ver o Onix"
    saida, _ = aplicar_travas(
        _ia(telefone_cliente="19991234567",
            trecho_evidencia="quero ver o Onix"), texto, payload_bruto=texto)

    assert saida["telefone_verificado"] is True
    assert saida["telefone_cliente"] == "19991234567"


def test_telefone_aceito_mesmo_com_formatacao_diferente():
    """O cliente escreve com pontuacao; o modelo devolve so digitos."""
    texto = "meu whats e 19 9 9123-4567"
    saida, _ = aplicar_travas(
        _ia(telefone_cliente="(19) 99123-4567", trecho_evidencia="meu whats e"),
        texto, payload_bruto=texto)

    assert saida["telefone_verificado"] is True


def test_telefone_curto_demais_nao_vale():
    texto = "quero o carro por 1234"
    saida, _ = aplicar_travas(
        _ia(telefone_cliente="1234", trecho_evidencia="quero o carro"),
        texto, payload_bruto=texto)

    assert saida["telefone_verificado"] is False
    assert saida["telefone_cliente"] is None


# --------------------------------------------- trava 2: evidencia nao literal

def test_evidencia_parafraseada_forca_incerto():
    texto = "Bom dia, gostaria de saber o valor do Corolla 2018"
    saida, disparos = aplicar_travas(
        _ia(classificacao="nao_lead", confianca=0.99,
            trecho_evidencia="o cliente perguntou sobre o preco"),  # parafrase
        texto, payload_bruto=texto)

    assert saida["classificacao"] == "incerto"
    assert any("evidencia" in d for d in disparos)


def test_evidencia_ausente_forca_incerto():
    texto = "Tenho interesse"
    saida, _ = aplicar_travas(
        _ia(classificacao="nao_lead", confianca=0.99, trecho_evidencia=None),
        texto, payload_bruto=texto)

    assert saida["classificacao"] == "incerto"


def test_evidencia_literal_preserva_a_classificacao():
    texto = "Olá! Informamos que sua fatura já está disponível"
    saida, disparos = aplicar_travas(
        _ia(classificacao="nao_lead", categoria_nao_lead="cobranca", confianca=0.97,
            trecho_evidencia="sua fatura já está disponível"),
        texto, payload_bruto=texto)

    assert saida["classificacao"] == "nao_lead"
    assert disparos == []


def test_trava_de_evidencia_nao_deixa_arquivar_por_engano():
    """A trava existe para proteger o cliente: sem citacao literal, nao arquiva."""
    texto = "quero comprar um carro"
    saida, _ = aplicar_travas(
        _ia(classificacao="nao_lead", confianca=0.99, trecho_evidencia="spam"),
        texto, payload_bruto=texto)

    assert decidir(saida) != "arquivar"


# ------------------------------------------------- trava 3: custo assimetrico

def test_fail_open_quando_incerto():
    assert decidir(_ia(classificacao="incerto", confianca=0.2)) == "distribuir_com_duvida"


def test_fail_open_quando_confianca_baixa():
    assert decidir(_ia(classificacao="lead_novo", confianca=0.5)) == "distribuir_com_duvida"


def test_nao_lead_com_confianca_media_nao_arquiva():
    """O corte de nao_lead e 0.90, mais alto que o de lead_novo de proposito."""
    assert decidir(_ia(classificacao="nao_lead", confianca=0.85)) == "distribuir_com_duvida"
    assert decidir(_ia(classificacao="nao_lead", confianca=0.95)) == "arquivar"


def test_lead_novo_confiante_distribui():
    assert decidir(_ia(classificacao="lead_novo", confianca=0.93)) == "distribuir"


def test_pos_venda_distribui_mas_nao_conta_como_lead_novo():
    assert decidir(_ia(classificacao="pos_venda", confianca=0.96)) \
        == "distribuir_sem_contar_lead_novo"


def test_resposta_vazia_ou_quebrada_nao_arquiva():
    """API fora, timeout, JSON torto: o caminho tem que cair em distribuir."""
    for lixo in ({}, {"classificacao": None}, {"classificacao": "coisa_nova"},
                 {"classificacao": "nao_lead"}):  # sem confianca
        assert decidir(lixo) == "distribuir_com_duvida"
