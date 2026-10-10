"""Travas da Portaria v3 — o que roda DEPOIS do modelo, como teste.

Desenho v3 (spec 07, topo): numero novo -> IA diz lead / nao_lead / duvida.
So `nao_lead` e ignorado; todo o resto distribui. O unico erro caro e ignorar
um cliente, entao as travas existem para que `nao_lead` so passe com evidencia
literal, e para que qualquer resposta estranha vire `duvida` (= distribui).

Nao chamam a API. Prompt e pedido; codigo e garantia.
(Os testes da v2 — telefone inventado, 4 categorias — sairam junto com a v2.)
"""
from portaria.prompt import aplicar_travas, decidir, extrair

TEXTO_BOLETO = "Informamos que o seu boleto encontra-se em aberto. Evite juros."


# ------------------------------------------------ nao_lead exige evidencia literal

def test_nao_lead_com_trecho_literal_e_ignorado():
    r = aplicar_travas({"classificacao": "nao_lead", "motivo": "cobranca",
                        "trecho_evidencia": "seu boleto encontra-se em aberto"}, TEXTO_BOLETO)
    assert r["classificacao"] == "nao_lead"
    assert decidir(r) == "ignorar"


def test_nao_lead_com_trecho_parafraseado_vira_duvida_e_distribui():
    r = aplicar_travas({"classificacao": "nao_lead", "motivo": "cobranca",
                        "trecho_evidencia": "boleto em aberto"}, TEXTO_BOLETO)
    assert r["classificacao"] == "duvida" and r["trava"] == "evidencia_nao_literal"
    assert decidir(r) == "distribuir"


def test_nao_lead_sem_trecho_vira_duvida():
    r = aplicar_travas({"classificacao": "nao_lead", "motivo": "x", "trecho_evidencia": ""}, TEXTO_BOLETO)
    assert decidir(r) == "distribuir"


def test_nao_lead_com_trecho_curto_demais_vira_duvida():
    # "em" esta no texto, mas nao prova nada
    r = aplicar_travas({"classificacao": "nao_lead", "motivo": "x", "trecho_evidencia": "em"}, TEXTO_BOLETO)
    assert decidir(r) == "distribuir"


# ------------------------------------------------ lead e duvida distribuem, com ou sem evidencia

def test_lead_distribui_mesmo_sem_evidencia():
    r = aplicar_travas({"classificacao": "lead", "motivo": "x", "trecho_evidencia": ""}, "oi")
    assert decidir(r) == "distribuir"


def test_duvida_distribui():
    r = aplicar_travas({"classificacao": "duvida", "motivo": "x", "trecho_evidencia": "x"}, "x")
    assert decidir(r) == "distribuir"


# ------------------------------------------------ fail open: qualquer coisa estranha distribui

def test_resposta_ausente_distribui():
    assert decidir(aplicar_travas(None, "qualquer")) == "distribuir"


def test_classificacao_desconhecida_distribui():
    assert decidir(aplicar_travas({"classificacao": "spam", "trecho_evidencia": "qualquer"}, "qualquer")) == "distribuir"


def test_formato_v2_antigo_distribui():
    # se o n8n ainda tiver o prompt v2 e devolver "lead_novo"/"incerto", nada e ignorado
    assert decidir(aplicar_travas({"classificacao": "incerto"}, "x")) == "distribuir"


def test_extrair_resposta_cortada_ou_recusa_e_none():
    assert extrair({"choices": [{"finish_reason": "length", "message": {"content": "{\"classif"}}]}) is None
    assert extrair({"choices": [{"finish_reason": "stop", "message": {"content": "nao e json"}}]}) is None
    assert extrair({}) is None


def test_extrair_json_valido_e_dentro_de_bloco_de_codigo():
    j = '{"classificacao": "lead", "motivo": "x", "trecho_evidencia": "oi"}'
    assert extrair({"choices": [{"finish_reason": "stop", "message": {"content": j}}]})["classificacao"] == "lead"
    assert extrair({"choices": [{"finish_reason": "stop", "message": {"content": "```json\n" + j + "\n```"}}]})["classificacao"] == "lead"
