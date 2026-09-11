-- =====================================================================
-- FIX: race condition em public.distribuir_lead (7 args)
-- Data: 2026-08-31
-- Baseado no dump verificado md5 2fe1bc6ac396bea8727c5628b8cf56f9
--
-- Unica alteracao: bloco PASSO 0 (lock consultivo por loja+cliente).
-- Nenhuma outra linha muda. Assinatura, tipo de retorno, search_path,
-- dono e grants preservados pelo CREATE OR REPLACE.
-- NAO dropa a sobrecarga de 6 args. NAO altera dados.
--
-- Rollback: rodar backup-20260831/ROLLBACK_distribuir_lead.sql
-- =====================================================================

CREATE OR REPLACE FUNCTION public.distribuir_lead(p_loja_id uuid, p_numero_cliente character varying, p_nome_cliente character varying, p_anuncio character varying, p_mensagem_original text, p_recebido_em timestamp with time zone, p_origem character varying DEFAULT 'WhatsApp Direto'::character varying)
 RETURNS TABLE(lead_id uuid, vendedor_id uuid, vendedor_nome character varying, vendedor_numero_whatsapp character varying, duplicado boolean)
 LANGUAGE plpgsql
 SET search_path TO 'public'
AS $function$
DECLARE
  v_lead_id UUID;
  v_vendedor_id UUID;
  v_vendedor_historico UUID;
  v_vendedor_ativo UUID;
  v_vendedor_nome VARCHAR;
  v_vendedor_numero VARCHAR;
  v_duplicado BOOLEAN := false;
  v_proximo_vendedor_id UUID;
  v_executar_round_robin BOOLEAN := true;
BEGIN
  -- =========================================================
  -- PASSO 0: LOCK POR CLIENTE (anti-race) -- adicionado 2026-08-31
  -- Duas mensagens do mesmo cliente chegando juntas geram duas execucoes
  -- n8n paralelas. Sem este lock, ambas passam pelos Passos 1 e 2 sem
  -- enxergar o INSERT ainda nao commitado da outra, caem no Round-Robin
  -- e o cliente vai para DOIS vendedores.
  -- Serializa apenas chamadas do mesmo (loja, cliente); clientes
  -- diferentes seguem em paralelo. Liberado no fim da transacao.
  -- Adquirido SEMPRE antes do FOR UPDATE em lojas => sem deadlock.
  -- =========================================================
  PERFORM pg_advisory_xact_lock(
    hashtextextended(p_loja_id::text || '|' || COALESCE(p_numero_cliente, ''), 0)
  );

  -- =========================================================
  -- PASSO 1: DUPLICATA EXATA — (numero_cliente, loja_id, anuncio)
  -- Se já existe lead com mesmo cliente + loja + anúncio E vendedor ativo:
  --   → duplicado=true, retorna vendedor, NÃO cria lead
  -- =========================================================
  SELECT l.vendedor_id INTO v_vendedor_historico
  FROM leads l
  WHERE l.numero_cliente = p_numero_cliente
    AND l.loja_id = p_loja_id
    AND l.anuncio = p_anuncio
  ORDER BY l.recebido_em DESC
  LIMIT 1;

  IF FOUND THEN
    -- Verificar se vendedor está ativo
    SELECT id INTO v_vendedor_ativo
    FROM vendedores
    WHERE id = v_vendedor_historico
      AND loja_id = p_loja_id
      AND status = 'ativo';

    IF FOUND THEN
      -- Duplicata exata com vendedor ativo: silenciar
      SELECT nome, numero_whatsapp INTO v_vendedor_nome, v_vendedor_numero
      FROM vendedores
      WHERE id = v_vendedor_historico;

      RETURN QUERY
      SELECT NULL::UUID, v_vendedor_historico, v_vendedor_nome, v_vendedor_numero, true;
      RETURN;
    END IF;
    -- Se vendedor inativo, cair para Passo 2/3 (não é duplicata válida)
    v_vendedor_historico := NULL;
  END IF;

  -- =========================================================
  -- PASSO 2: AMARRAÇÃO DE CLIENTE — (numero_cliente, loja_id)
  -- Se cliente já tem QUALQUER lead com vendedor ativo:
  --   → usa esse vendedor (NÃO faz Round-Robin)
  -- =========================================================
  SELECT l.vendedor_id INTO v_vendedor_historico
  FROM leads l
  INNER JOIN vendedores v ON v.id = l.vendedor_id
  WHERE l.numero_cliente = p_numero_cliente
    AND l.loja_id = p_loja_id
    AND v.status = 'ativo'
    AND v.loja_id = p_loja_id
  ORDER BY l.recebido_em DESC
  LIMIT 1;

  IF FOUND THEN
    -- Cliente amarrado: usar mesmo vendedor, pular Round-Robin
    v_vendedor_id := v_vendedor_historico;
    v_executar_round_robin := false;
  END IF;

  -- =========================================================
  -- PASSO 3: ROUND-ROBIN (cliente novo OU todos vendedores anteriores inativos)
  -- =========================================================
  IF v_executar_round_robin THEN
    -- Lock na linha da loja para atomicidade
    SELECT proximo_vendedor_id INTO v_vendedor_id
    FROM lojas
    WHERE id = p_loja_id
    FOR UPDATE;

    -- Se proximo_vendedor_id é NULL, buscar primeiro ativo
    IF v_vendedor_id IS NULL THEN
      SELECT id INTO v_vendedor_id
      FROM vendedores
      WHERE loja_id = p_loja_id
        AND status = 'ativo'
      ORDER BY criado_em ASC
      LIMIT 1;
    ELSE
      -- Verificar se o vendedor apontado ainda está ativo
      SELECT id INTO v_vendedor_ativo
      FROM vendedores
      WHERE id = v_vendedor_id
        AND loja_id = p_loja_id
        AND status = 'ativo';

      -- Se não ativo, buscar próximo ativo após ele
      IF v_vendedor_ativo IS NULL THEN
        SELECT id INTO v_vendedor_id
        FROM vendedores
        WHERE loja_id = p_loja_id
          AND status = 'ativo'
          AND criado_em > (SELECT criado_em FROM vendedores WHERE id = v_vendedor_id)
        ORDER BY criado_em ASC
        LIMIT 1;

        -- Se não encontrou após, voltar pro primeiro
        IF v_vendedor_id IS NULL THEN
          SELECT id INTO v_vendedor_id
          FROM vendedores
          WHERE loja_id = p_loja_id
            AND status = 'ativo'
          ORDER BY criado_em ASC
          LIMIT 1;
        END IF;
      END IF;
    END IF;

    -- Se não encontrou nenhum vendedor ativo, retornar erro
    IF v_vendedor_id IS NULL THEN
      RAISE EXCEPTION 'Nenhum vendedor ativo disponível na loja';
    END IF;

    -- Encontrar PRÓXIMO vendedor para atualizar ponteiro
    SELECT id INTO v_proximo_vendedor_id
    FROM vendedores
    WHERE loja_id = p_loja_id
      AND status = 'ativo'
      AND criado_em > (SELECT criado_em FROM vendedores WHERE id = v_vendedor_id)
    ORDER BY criado_em ASC
    LIMIT 1;

    -- Se não há próximo, voltar pro primeiro
    IF v_proximo_vendedor_id IS NULL THEN
      SELECT id INTO v_proximo_vendedor_id
      FROM vendedores
      WHERE loja_id = p_loja_id
        AND status = 'ativo'
      ORDER BY criado_em ASC
      LIMIT 1;
    END IF;

    -- Atualizar ponteiro Round-Robin para o PRÓXIMO
    UPDATE lojas
    SET proximo_vendedor_id = v_proximo_vendedor_id,
        ultima_distribuicao_em = NOW()
    WHERE id = p_loja_id;
  END IF;

  -- =========================================================
  -- PASSO 4: INSERÇÃO — novo lead com vendedor do Passo 2 ou 3
  -- =========================================================
  INSERT INTO leads (
    loja_id,
    vendedor_id,
    numero_cliente,
    nome_cliente,
    anuncio,
    mensagem_original,
    recebido_em,
    distribuido_em,
    origem
  ) VALUES (
    p_loja_id,
    v_vendedor_id,
    p_numero_cliente,
    p_nome_cliente,
    p_anuncio,
    p_mensagem_original,
    p_recebido_em,
    NOW(),
    p_origem
  ) RETURNING id INTO v_lead_id;

  -- BUSCAR DADOS DO VENDEDOR
  SELECT nome, numero_whatsapp INTO v_vendedor_nome, v_vendedor_numero
  FROM vendedores
  WHERE id = v_vendedor_id;

  -- =========================================================
  -- PASSO 5: LOG DE ATIVIDADE
  -- =========================================================
  INSERT INTO atividades (loja_id, tipo, descricao)
  VALUES (p_loja_id, 'novo_lead',
    'Lead de ' || COALESCE(p_nome_cliente, p_numero_cliente) ||
    ' encaminhado para ' || v_vendedor_nome);

  -- RETORNO: duplicado=false (novo lead criado)
  RETURN QUERY
  SELECT
    v_lead_id,
    v_vendedor_id,
    v_vendedor_nome,
    v_vendedor_numero,
    v_duplicado;
END;
$function$;
