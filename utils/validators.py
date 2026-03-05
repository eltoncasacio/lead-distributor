"""
Validadores para formulários.
"""
import re
from typing import Optional, Tuple


def validar_whatsapp(whatsapp: str) -> Tuple[bool, Optional[str]]:
    """
    Valida formato de WhatsApp brasileiro.

    Returns:
        (valido, mensagem_erro)
    """
    # Remover caracteres não numéricos
    numeros = re.sub(r'\D', '', whatsapp)

    # Deve ter 12 ou 13 dígitos (55 + DDD + número)
    if len(numeros) < 12 or len(numeros) > 13:
        return False, "WhatsApp deve ter formato: 5511999998888 (com DDI 55)"

    # Deve começar com 55 (Brasil)
    if not numeros.startswith('55'):
        return False, "WhatsApp deve começar com código do Brasil (55)"

    # DDD deve ter 2 dígitos
    ddd = numeros[2:4]
    if not ddd.isdigit() or int(ddd) < 11:
        return False, "DDD inválido"

    return True, None


def validar_nome(nome: str) -> Tuple[bool, Optional[str]]:
    """
    Valida nome (gerente ou vendedor).

    Returns:
        (valido, mensagem_erro)
    """
    nome = nome.strip()

    if len(nome) < 2:
        return False, "Nome deve ter pelo menos 2 caracteres"

    if len(nome) > 100:
        return False, "Nome muito longo (máximo 100 caracteres)"

    if not re.match(r'^[a-zA-ZÀ-ÿ\s]+$', nome):
        return False, "Nome deve conter apenas letras e espaços"

    return True, None


def formatar_whatsapp(whatsapp: str) -> str:
    """
    Formata WhatsApp removendo caracteres especiais.
    Retorna apenas números.
    """
    return re.sub(r'\D', '', whatsapp)
