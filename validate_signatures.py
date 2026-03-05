"""
Valida assinaturas das funções refatoradas (sem executar queries).
"""
import inspect
from datetime import date
from typing import Optional

# Simular imports
class MockSupabase:
    pass

# Mock do get_cached_supabase_client
import utils.queries as queries_module
original_get_client = queries_module.get_cached_supabase_client

def mock_client():
    return MockSupabase()

queries_module.get_cached_supabase_client = mock_client

from utils.queries import get_leads_por_dia, get_leads_por_hora, get_leads_por_origem_comparativo

print("=" * 60)
print("VALIDAÇÃO DE ASSINATURAS DAS FUNÇÕES REFATORADAS")
print("=" * 60)

# Validar get_leads_por_dia
sig1 = inspect.signature(get_leads_por_dia)
params1 = list(sig1.parameters.keys())
print("\n✓ get_leads_por_dia")
print(f"  Parâmetros: {params1}")
assert params1 == ['loja_id', 'dias', 'data_inicio', 'data_fim'], "Assinatura incorreta!"
assert sig1.parameters['dias'].annotation == Optional[int], "Tipo 'dias' incorreto!"
assert sig1.parameters['data_inicio'].annotation == Optional[date], "Tipo 'data_inicio' incorreto!"
assert sig1.parameters['data_fim'].annotation == Optional[date], "Tipo 'data_fim' incorreto!"
print("  ✓ Tipos validados")

# Validar get_leads_por_hora
sig2 = inspect.signature(get_leads_por_hora)
params2 = list(sig2.parameters.keys())
print("\n✓ get_leads_por_hora")
print(f"  Parâmetros: {params2}")
assert params2 == ['loja_id', 'dias', 'data_inicio', 'data_fim'], "Assinatura incorreta!"
assert sig2.parameters['dias'].annotation == Optional[int], "Tipo 'dias' incorreto!"
assert sig2.parameters['data_inicio'].annotation == Optional[date], "Tipo 'data_inicio' incorreto!"
assert sig2.parameters['data_fim'].annotation == Optional[date], "Tipo 'data_fim' incorreto!"
print("  ✓ Tipos validados")

# Validar get_leads_por_origem_comparativo
sig3 = inspect.signature(get_leads_por_origem_comparativo)
params3 = list(sig3.parameters.keys())
print("\n✓ get_leads_por_origem_comparativo")
print(f"  Parâmetros: {params3}")
assert params3 == ['loja_id', 'dias', 'data_inicio', 'data_fim'], "Assinatura incorreta!"
assert sig3.parameters['dias'].annotation == Optional[int], "Tipo 'dias' incorreto!"
assert sig3.parameters['data_inicio'].annotation == Optional[date], "Tipo 'data_inicio' incorreto!"
assert sig3.parameters['data_fim'].annotation == Optional[date], "Tipo 'data_fim' incorreto!"
print("  ✓ Tipos validados")

print("\n" + "=" * 60)
print("✅ TODAS AS ASSINATURAS ESTÃO CORRETAS!")
print("=" * 60)

# Restaurar original
queries_module.get_cached_supabase_client = original_get_client
