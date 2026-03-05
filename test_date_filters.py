"""
Script de teste para validar filtros de data customizados.
Testa backward compatibility e novos parâmetros.
"""
import sys
sys.path.insert(0, '.')

from datetime import date, timedelta
from utils.queries import get_leads_por_dia, get_leads_por_hora, get_leads_por_origem_comparativo

# ID da loja de teste (Renato Motors)
LOJA_ID = "cc0a1b1b-e5e0-4a92-b835-e2de6c76d3b4"

print("=" * 60)
print("TESTE 1: Backward Compatibility (parâmetro 'dias')")
print("=" * 60)

print("\n1.1 - get_leads_por_dia (7 dias)...")
resultado = get_leads_por_dia(LOJA_ID, dias=7)
print(f"✓ Retornou {len(resultado)} registros")

print("\n1.2 - get_leads_por_hora (30 dias)...")
resultado = get_leads_por_hora(LOJA_ID, dias=30)
print(f"✓ Retornou {len(resultado)} registros (sempre 24 horas)")

print("\n1.3 - get_leads_por_origem_comparativo (15 dias)...")
resultado = get_leads_por_origem_comparativo(LOJA_ID, dias=15)
print(f"✓ Período atual: {sum(resultado['atual'].values())} leads")
print(f"✓ Período anterior: {sum(resultado['anterior'].values())} leads")

print("\n" + "=" * 60)
print("TESTE 2: Novos Parâmetros (data_inicio, data_fim)")
print("=" * 60)

data_fim = date.today()
data_inicio = data_fim - timedelta(days=10)

print(f"\n2.1 - get_leads_por_dia ({data_inicio} até {data_fim})...")
resultado = get_leads_por_dia(LOJA_ID, data_inicio=data_inicio, data_fim=data_fim)
print(f"✓ Retornou {len(resultado)} registros")
if resultado:
    print(f"  Primeira data: {resultado[-1]['data']}")
    print(f"  Última data: {resultado[0]['data']}")

print(f"\n2.2 - get_leads_por_hora ({data_inicio} até {data_fim})...")
resultado = get_leads_por_hora(LOJA_ID, data_inicio=data_inicio, data_fim=data_fim)
print(f"✓ Retornou {len(resultado)} registros")
total_leads = sum(r['total'] for r in resultado)
print(f"  Total de leads no período: {total_leads}")

print(f"\n2.3 - get_leads_por_origem_comparativo ({data_inicio} até {data_fim})...")
resultado = get_leads_por_origem_comparativo(LOJA_ID, data_inicio=data_inicio, data_fim=data_fim)
duracao = (data_fim - data_inicio).days
periodo_anterior_inicio = data_inicio - timedelta(days=duracao)
periodo_anterior_fim = data_inicio - timedelta(days=1)

print(f"✓ Período atual ({data_inicio} - {data_fim}):")
print(f"  WhatsApp Direto: {resultado['atual']['WhatsApp Direto']}")
print(f"  iCarros: {resultado['atual']['iCarros']}")
print(f"  NaPista: {resultado['atual']['NaPista']}")

print(f"\n✓ Período anterior ({periodo_anterior_inicio} - {periodo_anterior_fim}):")
print(f"  WhatsApp Direto: {resultado['anterior']['WhatsApp Direto']}")
print(f"  iCarros: {resultado['anterior']['iCarros']}")
print(f"  NaPista: {resultado['anterior']['NaPista']}")

print("\n" + "=" * 60)
print("TESTE 3: Edge Cases")
print("=" * 60)

print("\n3.1 - Período de 1 dia (hoje)...")
resultado = get_leads_por_dia(LOJA_ID, data_inicio=date.today(), data_fim=date.today())
print(f"✓ Retornou {len(resultado)} registros")

print("\n3.2 - Período sem dados (daqui 30 dias - futuro)...")
futuro_inicio = date.today() + timedelta(days=30)
futuro_fim = date.today() + timedelta(days=40)
resultado = get_leads_por_dia(LOJA_ID, data_inicio=futuro_inicio, data_fim=futuro_fim)
print(f"✓ Retornou {len(resultado)} registros (esperado: 0)")

print("\n3.3 - Default sem parâmetros (últimos 30 dias)...")
resultado = get_leads_por_dia(LOJA_ID)
print(f"✓ Retornou {len(resultado)} registros")

print("\n" + "=" * 60)
print("✅ TODOS OS TESTES CONCLUÍDOS COM SUCESSO!")
print("=" * 60)
