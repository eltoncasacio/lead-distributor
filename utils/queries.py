"""
Queries SQL para o app.
Todas queries filtradas por loja_id para garantir isolamento.
"""
from typing import List, Optional, Dict, Any
from datetime import date
from .supabase_client import get_cached_supabase_client


# ============================================
# GERENTES
# ============================================

def listar_gerentes(loja_id: str) -> List[Dict[str, Any]]:
    """Lista todos os gerentes da loja."""
    supabase = get_cached_supabase_client()
    response = (
        supabase.table("gerentes")
        .select("*")
        .eq("loja_id", loja_id)
        .order("nome")
        .execute()
    )
    return response.data


def adicionar_gerente(loja_id: str, nome: str, whatsapp: str) -> Dict[str, Any]:
    """Adiciona novo gerente."""
    supabase = get_cached_supabase_client()
    response = (
        supabase.table("gerentes")
        .insert({
            "loja_id": loja_id,
            "nome": nome,
            "numero_whatsapp": whatsapp,
            "ativo": True
        })
        .execute()
    )
    return response.data[0] if response.data else None


def editar_gerente(gerente_id: str, nome: str, whatsapp: str) -> Dict[str, Any]:
    """Edita gerente existente."""
    supabase = get_cached_supabase_client()
    response = (
        supabase.table("gerentes")
        .update({
            "nome": nome,
            "numero_whatsapp": whatsapp
        })
        .eq("id", gerente_id)
        .execute()
    )
    return response.data[0] if response.data else None


def desativar_gerente(gerente_id: str) -> Dict[str, Any]:
    """Desativa gerente (soft delete)."""
    supabase = get_cached_supabase_client()
    response = (
        supabase.table("gerentes")
        .update({"ativo": False})
        .eq("id", gerente_id)
        .execute()
    )
    return response.data[0] if response.data else None


def deletar_gerente(gerente_id: str) -> bool:
    """Deleta gerente permanentemente."""
    supabase = get_cached_supabase_client()
    response = (
        supabase.table("gerentes")
        .delete()
        .eq("id", gerente_id)
        .execute()
    )
    return True


# ============================================
# VENDEDORES
# ============================================

def listar_vendedores(loja_id: str, incluir_inativos: bool = True) -> List[Dict[str, Any]]:
    """Lista vendedores da loja."""
    supabase = get_cached_supabase_client()
    query = supabase.table("vendedores").select("*").eq("loja_id", loja_id)

    if not incluir_inativos:
        query = query.eq("status", "ativo")

    response = query.order("ordem_fila").execute()
    return response.data


def adicionar_vendedor(
    loja_id: str,
    nome: str,
    whatsapp: str,
    ordem_fila: Optional[int] = None
) -> Dict[str, Any]:
    """
    Adiciona novo vendedor.
    Se ordem_fila não fornecida, adiciona no final.
    """
    supabase = get_cached_supabase_client()

    # Se ordem não fornecida, buscar próxima posição
    if ordem_fila is None:
        vendedores = listar_vendedores(loja_id, incluir_inativos=False)
        ordem_fila = max([v["ordem_fila"] for v in vendedores], default=0) + 1

    response = (
        supabase.table("vendedores")
        .insert({
            "loja_id": loja_id,
            "nome": nome,
            "numero_whatsapp": whatsapp,
            "status": "ativo",
            "ordem_fila": ordem_fila
        })
        .execute()
    )
    return response.data[0] if response.data else None


def editar_vendedor(vendedor_id: str, nome: str, whatsapp: str) -> Dict[str, Any]:
    """Edita vendedor existente."""
    supabase = get_cached_supabase_client()
    response = (
        supabase.table("vendedores")
        .update({
            "nome": nome,
            "numero_whatsapp": whatsapp
        })
        .eq("id", vendedor_id)
        .execute()
    )
    return response.data[0] if response.data else None


def alterar_status_vendedor(vendedor_id: str, novo_status: str) -> Dict[str, Any]:
    """
    Altera status do vendedor (ativo/inativo/removido).
    Se inativar/remover, recalcula próximo_vendedor_id da loja.
    """
    supabase = get_cached_supabase_client()

    # Buscar dados do vendedor antes de alterar
    vendedor = supabase.table("vendedores").select("*").eq("id", vendedor_id).execute()
    if not vendedor.data:
        return None

    loja_id = vendedor.data[0]["loja_id"]

    # Alterar status
    response = (
        supabase.table("vendedores")
        .update({"status": novo_status})
        .eq("id", vendedor_id)
        .execute()
    )

    # Se inativou/removeu, recalcular próximo vendedor
    if novo_status in ["inativo", "removido"]:
        atualizar_proximo_vendedor_da_loja(loja_id)

    return response.data[0] if response.data else None


def atualizar_proximo_vendedor_da_loja(loja_id: str):
    """
    Recalcula e atualiza o proximo_vendedor_id da loja.
    Garante que aponta para um vendedor ativo.
    """
    supabase = get_cached_supabase_client()

    # Buscar vendedores ativos
    vendedores_ativos = listar_vendedores(loja_id, incluir_inativos=False)
    vendedores_ativos = [v for v in vendedores_ativos if v["status"] == "ativo"]

    if not vendedores_ativos:
        # Sem vendedores ativos, setar como NULL
        supabase.table("lojas").update(
            {"proximo_vendedor_id": None}
        ).eq("id", loja_id).execute()
        return

    # Buscar próximo atual
    loja = supabase.table("lojas").select("proximo_vendedor_id").eq("id", loja_id).execute()
    proximo_atual = loja.data[0]["proximo_vendedor_id"] if loja.data else None

    # Se próximo atual está ativo, manter
    if proximo_atual and any(v["id"] == proximo_atual for v in vendedores_ativos):
        return

    # Próximo atual não é ativo, setar para primeiro ativo
    supabase.table("lojas").update(
        {"proximo_vendedor_id": vendedores_ativos[0]["id"]}
    ).eq("id", loja_id).execute()


def reordenar_vendedores(loja_id: str, nova_ordem: List[str]) -> bool:
    """
    Reordena vendedores (drag-drop).
    nova_ordem: lista de IDs na ordem desejada (1º ID = posição 1, 2º ID = posição 2, etc.)

    IMPORTANTE: Também recalcula proximo_vendedor_id para garantir consistência.
    """
    supabase = get_cached_supabase_client()

    # Validar que todos IDs pertencem à loja
    for vendedor_id in nova_ordem:
        vendedor = supabase.table("vendedores").select("id, loja_id").eq("id", vendedor_id).execute()
        if not vendedor.data:
            raise ValueError(f"Vendedor {vendedor_id} não encontrado")
        if vendedor.data[0]["loja_id"] != loja_id:
            raise ValueError(f"Vendedor {vendedor_id} não pertence à loja {loja_id}")

    # Atualizar ordem_fila de cada vendedor
    for idx, vendedor_id in enumerate(nova_ordem, start=1):
        response = supabase.table("vendedores").update(
            {"ordem_fila": idx}
        ).eq("id", vendedor_id).execute()

        # Validar que update funcionou
        if not response.data:
            raise Exception(f"Falha ao atualizar vendedor {vendedor_id} para posição {idx}")

    # CRÍTICO: Recalcular proximo_vendedor_id (sempre primeiro da fila)
    # Isso garante que o ponteiro aponta para quem está na posição 1
    if nova_ordem:
        supabase.table("lojas").update({
            "proximo_vendedor_id": nova_ordem[0]  # Primeiro da nova ordem = posição 1
        }).eq("id", loja_id).execute()

    return True


def obter_proximo_vendedor(loja_id: str) -> Optional[Dict[str, Any]]:
    """
    Retorna o próximo vendedor ATIVO que receberá lead.
    Se o proximo_vendedor_id apontar para inativo, busca o próximo ativo.
    """
    supabase = get_cached_supabase_client()

    # Buscar proximo_vendedor_id da loja
    loja_response = (
        supabase.table("lojas")
        .select("proximo_vendedor_id")
        .eq("id", loja_id)
        .execute()
    )

    if not loja_response.data:
        return None

    proximo_id = loja_response.data[0].get("proximo_vendedor_id")

    # Listar vendedores ativos em ordem
    vendedores_ativos = listar_vendedores(loja_id, incluir_inativos=False)
    vendedores_ativos = [v for v in vendedores_ativos if v["status"] == "ativo"]

    if not vendedores_ativos:
        return None

    # Se não tem próximo definido, retornar primeiro ativo
    if not proximo_id:
        return vendedores_ativos[0]

    # Verificar se o próximo está ativo
    vendedor_atual = next((v for v in vendedores_ativos if v["id"] == proximo_id), None)

    if vendedor_atual:
        # Próximo está ativo, retornar ele
        return vendedor_atual

    # Próximo está inativo, buscar o próximo ativo na fila
    # Buscar o vendedor inativo para saber sua ordem
    vendedor_inativo = (
        supabase.table("vendedores")
        .select("ordem_fila")
        .eq("id", proximo_id)
        .execute()
    )

    if vendedor_inativo.data:
        ordem_inativo = vendedor_inativo.data[0]["ordem_fila"]
        # Buscar próximo ativo após essa ordem
        proximo_ativo = next(
            (v for v in vendedores_ativos if v["ordem_fila"] > ordem_inativo),
            vendedores_ativos[0]  # Se não houver após, volta pro primeiro
        )
        return proximo_ativo

    # Fallback: retornar primeiro ativo
    return vendedores_ativos[0]


# ============================================
# VALIDAÇÕES
# ============================================

def whatsapp_ja_existe(whatsapp: str, loja_id: str, excluir_id: Optional[str] = None) -> bool:
    """
    Verifica se WhatsApp já está cadastrado (gerente OU vendedor).
    excluir_id: ID do registro atual (para permitir editar sem conflito)
    """
    supabase = get_cached_supabase_client()

    # Checar gerentes
    gerentes_query = (
        supabase.table("gerentes")
        .select("id")
        .eq("numero_whatsapp", whatsapp)
        .eq("loja_id", loja_id)
    )

    if excluir_id:
        gerentes_query = gerentes_query.neq("id", excluir_id)

    gerentes_response = gerentes_query.execute()

    if gerentes_response.data:
        return True

    # Checar vendedores
    vendedores_query = (
        supabase.table("vendedores")
        .select("id")
        .eq("numero_whatsapp", whatsapp)
        .eq("loja_id", loja_id)
    )

    if excluir_id:
        vendedores_query = vendedores_query.neq("id", excluir_id)

    vendedores_response = vendedores_query.execute()

    return bool(vendedores_response.data)


def contar_vendedores_ativos(loja_id: str) -> int:
    """Conta quantos vendedores ativos a loja tem."""
    vendedores = listar_vendedores(loja_id, incluir_inativos=False)
    return len([v for v in vendedores if v["status"] == "ativo"])


# ============================================
# DASHBOARD - MÉTRICAS E LEADS
# ============================================

def identificar_origem(numero_cliente: str) -> str:
    """
    Identifica origem do lead baseado no número do cliente.

    Mapeamento:
    - 551130044558 → iCarros
    - 551131361712 → NaPista
    - Outros → WhatsApp Direto
    """
    if numero_cliente == "551130044558":
        return "iCarros"
    elif numero_cliente == "551131361712":
        return "NaPista"
    else:
        return "WhatsApp Direto"


def get_metricas_hoje(loja_id: str) -> Dict[str, Any]:
    """
    Retorna métricas de hoje usando RPC comando_status.

    Retorno:
    {
        "total_leads": int,
        "ultimo_lead": str (HH:MM ou null),
        "proximo_vendedor": str (nome),
        "distribuicao": str (texto formatado por vendedor)
    }
    """
    supabase = get_cached_supabase_client()

    response = supabase.rpc("comando_status", {"p_loja_id": loja_id}).execute()

    if not response.data:
        return {
            "total_leads": 0,
            "ultimo_lead": None,
            "proximo_vendedor": "N/A",
            "distribuicao": ""
        }

    dados = response.data
    return {
        "total_leads": dados.get("total_leads", 0),
        "ultimo_lead": dados.get("ultimo_lead"),
        "proximo_vendedor": dados.get("proximo_vendedor", "N/A"),
        "distribuicao": dados.get("distribuicao", "")
    }


def get_leads_por_dia(
    loja_id: str,
    dias: Optional[int] = None,
    data_inicio: Optional[date] = None,
    data_fim: Optional[date] = None
) -> List[Dict[str, Any]]:
    """
    Retorna total de leads por dia.

    Args:
        loja_id: ID da loja
        dias: (LEGACY) Últimos N dias a partir de hoje
        data_inicio: Data inicial customizada (prioridade sobre dias)
        data_fim: Data final customizada (prioridade sobre dias)

    Retorno: [{"data": "2026-03-01", "total": 5}, ...]
    """
    supabase = get_cached_supabase_client()
    from datetime import datetime, timedelta, time

    # Prioridade: datas customizadas > dias > default 30
    if data_inicio and data_fim:
        dt_inicio = datetime.combine(data_inicio, time.min)
        dt_fim = datetime.combine(data_fim, time.max)
    else:
        dias = dias or 30
        agora = datetime.now()
        dt_inicio = agora - timedelta(days=dias)
        dt_fim = agora

    # Buscar todos leads do período (com limite superior)
    response = (
        supabase.table("leads")
        .select("recebido_em")
        .eq("loja_id", loja_id)
        .gte("recebido_em", dt_inicio.isoformat())
        .lte("recebido_em", dt_fim.isoformat())
        .execute()
    )

    if not response.data:
        return []

    # Agrupar por data manualmente
    contagem = {}
    for lead in response.data:
        recebido = datetime.fromisoformat(lead["recebido_em"].replace("Z", "+00:00"))
        data_str = recebido.date().isoformat()
        contagem[data_str] = contagem.get(data_str, 0) + 1

    return [{"data": data, "total": total} for data, total in sorted(contagem.items(), reverse=True)]


def get_leads_por_vendedor(loja_id: str, dias: int = 30) -> List[Dict[str, Any]]:
    """
    Retorna total de leads por vendedor (últimos N dias).

    Retorno: [{"vendedor_nome": "João", "total": 10}, ...]
    """
    supabase = get_cached_supabase_client()
    from datetime import datetime, timedelta

    # Calcular data limite
    data_limite = datetime.now() - timedelta(days=dias)

    # Buscar leads + JOIN com vendedores
    response = (
        supabase.table("leads")
        .select("vendedor_id, vendedores(nome)")
        .eq("loja_id", loja_id)
        .gte("recebido_em", data_limite.isoformat())
        .execute()
    )

    if not response.data:
        return []

    # Agrupar por vendedor manualmente
    contagem = {}
    for lead in response.data:
        vendedor_nome = lead["vendedores"]["nome"] if lead.get("vendedores") else "Sem vendedor"
        contagem[vendedor_nome] = contagem.get(vendedor_nome, 0) + 1

    return [{"vendedor_nome": nome, "total": total} for nome, total in contagem.items()]


def get_leads_por_hora(
    loja_id: str,
    dias: Optional[int] = None,
    data_inicio: Optional[date] = None,
    data_fim: Optional[date] = None
) -> List[Dict[str, Any]]:
    """
    Retorna total de leads por hora do dia.
    Agora inclui hora_formatada (00:00-23:00) para eixo X legível.

    Args:
        loja_id: ID da loja
        dias: (LEGACY) Últimos N dias a partir de hoje
        data_inicio: Data inicial customizada (prioridade sobre dias)
        data_fim: Data final customizada (prioridade sobre dias)

    Retorno: [{"hora": 9, "hora_formatada": "09:00", "total": 15}, ...]
    """
    supabase = get_cached_supabase_client()
    from datetime import datetime, timedelta, time

    # Prioridade: datas customizadas > dias > default 30
    if data_inicio and data_fim:
        dt_inicio = datetime.combine(data_inicio, time.min)
        dt_fim = datetime.combine(data_fim, time.max)
    else:
        dias = dias or 30
        agora = datetime.now()
        dt_inicio = agora - timedelta(days=dias)
        dt_fim = agora

    # Buscar todos leads do período (com limite superior)
    response = (
        supabase.table("leads")
        .select("recebido_em")
        .eq("loja_id", loja_id)
        .gte("recebido_em", dt_inicio.isoformat())
        .lte("recebido_em", dt_fim.isoformat())
        .execute()
    )

    if not response.data:
        # Retornar TODAS as 24 horas mesmo sem dados (para gráfico consistente)
        return [
            {"hora": hora, "hora_formatada": f"{hora:02d}:00", "total": 0}
            for hora in range(24)
        ]

    # Extrair hora e agrupar manualmente
    contagem = {}

    for lead in response.data:
        recebido = datetime.fromisoformat(lead["recebido_em"].replace("Z", "+00:00"))
        hora = recebido.hour
        contagem[hora] = contagem.get(hora, 0) + 1

    # Criar lista com TODAS as 24 horas + formato pt-BR
    resultado = []
    for hora in range(24):
        resultado.append({
            "hora": hora,
            "hora_formatada": f"{hora:02d}:00",  # NOVO: formato legível
            "total": contagem.get(hora, 0)
        })

    return resultado


def get_leads_por_origem_comparativo(
    loja_id: str,
    dias: Optional[int] = None,
    data_inicio: Optional[date] = None,
    data_fim: Optional[date] = None
) -> Dict[str, Any]:
    """
    Retorna contagem de leads por origem para periodo atual e anterior.
    Periodo anterior = mesma duração, imediatamente antes.

    Args:
        loja_id: ID da loja
        dias: (LEGACY) Últimos N dias a partir de hoje
        data_inicio: Data inicial customizada (prioridade sobre dias)
        data_fim: Data final customizada (prioridade sobre dias)

    Returns:
        {
            "atual": {"WhatsApp Direto": 52, "NaPista": 7, "iCarros": 6},
            "anterior": {"WhatsApp Direto": 47, "NaPista": 5, "iCarros": 8},
        }
    """
    supabase = get_cached_supabase_client()
    from datetime import datetime, timedelta, time

    # Calcular período atual
    if data_inicio and data_fim:
        dt_inicio_atual = datetime.combine(data_inicio, time.min)
        dt_fim_atual = datetime.combine(data_fim, time.max)
        duracao = (data_fim - data_inicio).days
    else:
        dias = dias or 30
        agora = datetime.now()
        dt_inicio_atual = agora - timedelta(days=dias)
        dt_fim_atual = agora
        duracao = dias

    # Calcular período anterior (mesma duração)
    dt_fim_anterior = dt_inicio_atual - timedelta(seconds=1)
    dt_inicio_anterior = dt_fim_anterior - timedelta(days=duracao)

    # Buscar leads de ambos os períodos (atual + anterior)
    response = (
        supabase.table("leads")
        .select("numero_cliente, recebido_em")
        .eq("loja_id", loja_id)
        .gte("recebido_em", dt_inicio_anterior.isoformat())
        .lte("recebido_em", dt_fim_atual.isoformat())
        .order("recebido_em", desc=True)
        .limit(5000)
        .execute()
    )

    # Origens possiveis com default 0
    origens = ["WhatsApp Direto", "iCarros", "NaPista"]
    atual = {o: 0 for o in origens}
    anterior = {o: 0 for o in origens}

    if response.data:
        for lead in response.data:
            origem = identificar_origem(lead["numero_cliente"])
            recebido = datetime.fromisoformat(lead["recebido_em"].replace("Z", "+00:00"))
            recebido_naive = recebido.replace(tzinfo=None)

            if dt_inicio_atual <= recebido_naive <= dt_fim_atual:
                atual[origem] = atual.get(origem, 0) + 1
            elif dt_inicio_anterior <= recebido_naive <= dt_fim_anterior:
                anterior[origem] = anterior.get(origem, 0) + 1

    return {"atual": atual, "anterior": anterior}


def get_leads_lista(
    loja_id: str,
    dias: Optional[int] = None,
    vendedor_id: Optional[str] = None,
    origem: Optional[str] = None,
    status_lead: Optional[str] = None,
    data_inicio: Optional[date] = None,
    data_fim: Optional[date] = None
) -> List[Dict[str, Any]]:
    """
    Retorna lista de leads com filtros opcionais.

    Args:
        loja_id: ID da loja
        dias: (LEGACY) Últimos N dias a partir de hoje
        vendedor_id: Filtrar por vendedor específico
        origem: Filtrar por origem (WhatsApp Direto, iCarros, NaPista)
        status_lead: Filtrar por status
        data_inicio: Data inicial customizada (prioridade sobre dias)
        data_fim: Data final customizada (prioridade sobre dias)

    Retorno: [{"recebido_em", "nome_cliente", "anuncio", "vendedor_nome", "status_lead", "numero_cliente"}, ...]
    """
    supabase = get_cached_supabase_client()
    from datetime import datetime, timedelta, time

    # Prioridade: datas customizadas > dias > default 30
    if data_inicio and data_fim:
        dt_inicio = datetime.combine(data_inicio, time.min)
        dt_fim = datetime.combine(data_fim, time.max)
    else:
        dias = dias or 30
        agora = datetime.now()
        dt_inicio = agora - timedelta(days=dias)
        dt_fim = agora

    # Query base (com limite superior)
    query = (
        supabase.table("leads")
        .select("*, vendedores(nome)")
        .eq("loja_id", loja_id)
        .gte("recebido_em", dt_inicio.isoformat())
        .lte("recebido_em", dt_fim.isoformat())
    )

    # Filtros opcionais
    if vendedor_id:
        query = query.eq("vendedor_id", vendedor_id)

    if status_lead:
        query = query.eq("status_lead", status_lead)

    # Ordenar e limitar (aumentado de 100 para 500)
    response = query.order("recebido_em", desc=True).limit(500).execute()

    if not response.data:
        return []

    # Adicionar origem calculada e formatar
    leads_formatados = []
    for lead in response.data:
        lead_formatado = {
            "id": lead["id"],
            "recebido_em": lead["recebido_em"],
            "nome_cliente": lead.get("nome_cliente", "N/A"),
            "anuncio": lead.get("anuncio", "WhatsApp Direto"),
            "numero_cliente": lead["numero_cliente"],
            "vendedor_nome": lead["vendedores"]["nome"] if lead.get("vendedores") else "N/A",
            "status_lead": lead.get("status_lead", "novo"),
            "origem": identificar_origem(lead["numero_cliente"])
        }

        # Filtro de origem (aplicado em Python pois não está no banco)
        if origem and lead_formatado["origem"] != origem:
            continue

        leads_formatados.append(lead_formatado)

    return leads_formatados


def get_atividades_recentes(loja_id: str, limite: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Retorna timeline unificada de atividades recentes:
    - Novos leads (criado_em ≈ atualizado_em)
    - Mudanças de status (atualizado_em > criado_em)

    Args:
        loja_id: ID da loja
        limite: Número máximo de atividades a retornar
        offset: Número de registros a pular (para paginação)

    Returns:
        Lista de atividades ordenadas por timestamp (mais recente primeiro)
    """
    supabase = get_cached_supabase_client()
    from datetime import datetime

    # Buscar leads recentes + atualizados com paginação
    response = (
        supabase.table("leads")
        .select("*, vendedores(nome)")
        .eq("loja_id", loja_id)
        .order("atualizado_em", desc=True)
        .range(offset, offset + limite - 1)
        .execute()
    )

    if not response.data:
        return []

    atividades = []
    for lead in response.data:
        criado = datetime.fromisoformat(lead["criado_em"].replace("Z", "+00:00"))
        atualizado = datetime.fromisoformat(lead["atualizado_em"].replace("Z", "+00:00"))

        # Se diferença > 10 segundos, é atualização de status
        diff_segundos = (atualizado - criado).total_seconds()
        tipo = "status_atualizado" if diff_segundos > 10 else "novo_lead"

        atividades.append({
            "tipo": tipo,
            "timestamp": lead["atualizado_em"],
            "nome_cliente": lead.get("nome_cliente", "N/A"),
            "anuncio": lead.get("anuncio", "WhatsApp Direto"),
            "vendedor_nome": lead["vendedores"]["nome"] if lead.get("vendedores") else "N/A",
            "status_lead": lead.get("status_lead", "novo")
        })

    return atividades


def get_fila_distribuicao(loja_id: str) -> List[Dict[str, Any]]:
    """
    Retorna fila de distribuição na ordem CORRETA (ordem_fila).
    Apenas vendedores ATIVOS.

    Returns:
        Lista com [{id, nome, posicao, proximo: bool}]
    """
    vendedores = listar_vendedores(loja_id, incluir_inativos=False)
    vendedores_ativos = [v for v in vendedores if v["status"] == "ativo"]

    # Já vem ordenado por ordem_fila (ver listar_vendedores linha 93)

    # Buscar próximo vendedor
    proximo = obter_proximo_vendedor(loja_id)
    proximo_id = proximo["id"] if proximo else None

    # Montar fila com posições
    fila = []
    for idx, v in enumerate(vendedores_ativos, start=1):
        fila.append({
            "id": v["id"],
            "nome": v["nome"],
            "posicao": idx,
            "proximo": v["id"] == proximo_id
        })

    return fila
