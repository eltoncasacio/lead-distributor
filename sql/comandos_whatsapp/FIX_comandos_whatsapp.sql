-- Comandos por WhatsApp: gerente administra vendedores, vendedor ve so o seu.
--
-- NAO altera `distribuir_lead`, `identificar_remetente`, `comando_status` nem
-- `comando_leads`. Cria funcoes novas e dois indices unicos. A regra de
-- distribuicao continua inteira no Postgres (ADR 0001).
--
-- O n8n chama UMA funcao, `executar_comando(loja_id, remetente, texto)`, e
-- envia de volta o campo `resposta`. Toda a logica (papel, parsing,
-- validacao, confirmacao, escrita, atividade) vive aqui.
--
-- Sem regex de proposito: nome e telefone sao normalizados com translate().
--
-- Confirmacao: o comando de escrita digitado "solto" devolve o que o sistema
-- entendeu (eco) e guarda a acao em `comandos_pendentes` por 5 minutos. A
-- resposta "sim" (ou "pode", "confirma"...) executa; "nao"/"cancela" descarta;
-- qualquer outra mensagem tambem descarta. O reenvio exato
-- `confirmar <comando> <telefone completo>` continua valendo (2026-10-10).
--
-- Estrutura: `_executar_comando_base` tem toda a regra (papel, parsing,
-- validacao, escrita). `executar_comando` e uma camada fina na frente que so
-- cuida da pendencia. A assinatura de `executar_comando` nao mudou: o n8n nao
-- precisa saber de nada disso.
--
-- Rollback: ROLLBACK_comandos_whatsapp.sql (mesmo diretorio).

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Funcoes puras de normalizacao
-- ---------------------------------------------------------------------------

-- "Joao", "JOAO", " joão ", "João  Silva" -> mesma chave. Sem regex.
CREATE OR REPLACE FUNCTION public.normalizar_nome(p text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
  SELECT array_to_string(
           array_remove(
             string_to_array(
               lower(translate(
                 coalesce(p, ''),
                 'ÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇÑáàâãäéèêëíìîïóòôõöúùûüçñ' || chr(160) || chr(9) || chr(10) || chr(13),
                 'AAAAAEEEEIIIIOOOOOUUUUCNaaaaaeeeeiiiiooooouuuucn' || '    '
               )),
               ' '),
             ''),
           ' ')
$$;

-- Remove tudo que nao for 0-9: apaga de `p` cada caractere que sobra quando
-- se tiram os digitos.
CREATE OR REPLACE FUNCTION public.somente_digitos(p text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
  SELECT translate(coalesce(p, ''), translate(coalesce(p, ''), '0123456789', ''), '')
$$;

-- Celular brasileiro valido -> '55' || DDD || '9' || 8 digitos (13 digitos).
-- Aceita com ou sem o 55. Qualquer outra coisa -> NULL.
CREATE OR REPLACE FUNCTION public.normalizar_telefone_br(p text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
  WITH d AS (SELECT public.somente_digitos(p) AS v),
       n AS (SELECT CASE WHEN length(v) = 13 AND left(v, 2) = '55' THEN v
                         WHEN length(v) = 11 THEN '55' || v
                    END AS v
               FROM d)
  SELECT CASE WHEN v IS NOT NULL
               AND substr(v, 3, 1) BETWEEN '1' AND '9'
               AND substr(v, 5, 1) = '9'
              THEN v
         END
    FROM n
$$;

-- Chave de comparacao entre numeros: DDD + ultimos 8 digitos. Tolera o JID do
-- WhatsApp sem o nono digito (12 digitos), que chega assim para contas antigas.
CREATE OR REPLACE FUNCTION public.chave_telefone(p text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
  WITH d AS (SELECT public.somente_digitos(p) AS v),
       s AS (SELECT CASE WHEN left(v, 2) = '55' AND length(v) IN (12, 13) THEN substr(v, 3) ELSE v END AS v
               FROM d)
  SELECT CASE WHEN length(v) IN (10, 11) THEN left(v, 2) || right(v, 8) END FROM s
$$;

-- Exibicao: 5519999746219 -> (19) 99974-6219. Fora do padrao, devolve os digitos.
CREATE OR REPLACE FUNCTION public.formatar_telefone(p text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
  WITH d AS (SELECT public.somente_digitos(p) AS v)
  SELECT CASE WHEN length(v) = 13 AND left(v, 2) = '55'
              THEN '(' || substr(v, 3, 2) || ') ' || substr(v, 5, 5) || '-' || substr(v, 10)
              ELSE v
         END
    FROM d
$$;

CREATE OR REPLACE FUNCTION public._cmd_resp(p_papel text, p_acao text, p_resposta text) RETURNS json
LANGUAGE sql IMMUTABLE AS $$
  SELECT json_build_object('papel', p_papel, 'acao', p_acao, 'resposta', p_resposta)
$$;

-- Eco de comando de escrita: leva junto o comando exato que confirma, para a
-- camada de pendencia guardar.
CREATE OR REPLACE FUNCTION public._cmd_eco(p_papel text, p_resposta text, p_confirmacao text) RETURNS json
LANGUAGE sql IMMUTABLE AS $$
  SELECT json_build_object('papel', p_papel, 'acao', 'eco',
    'resposta', p_resposta
      || E'\n\nPara confirmar, responda *sim* (vale por 5 minutos). Para cancelar, *não*.'
      || E'\nOu envie: *' || p_confirmacao || '*',
    'confirmacao', p_confirmacao)
$$;

-- ---------------------------------------------------------------------------
-- 2. Unicidade no banco (vale para comando, Dashboard e SQL direto)
-- ---------------------------------------------------------------------------

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM public.vendedores
              GROUP BY loja_id, public.normalizar_nome(nome) HAVING count(*) > 1) THEN
    RAISE EXCEPTION 'Existem vendedores com nome repetido na mesma loja (apos normalizar). Resolva antes de aplicar.';
  END IF;
  IF EXISTS (SELECT 1 FROM public.vendedores
              WHERE status <> 'removido' AND public.chave_telefone(numero_whatsapp) IS NOT NULL
              GROUP BY loja_id, public.chave_telefone(numero_whatsapp) HAVING count(*) > 1) THEN
    RAISE EXCEPTION 'Existem vendedores nao removidos com o mesmo telefone na mesma loja. Resolva antes de aplicar.';
  END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_vendedores_loja_nome
  ON public.vendedores (loja_id, public.normalizar_nome(nome));

-- Removido nao ocupa o numero: a mesma linha pode ser reaproveitada.
CREATE UNIQUE INDEX IF NOT EXISTS uq_vendedores_loja_telefone
  ON public.vendedores (loja_id, public.chave_telefone(numero_whatsapp))
  WHERE status <> 'removido' AND public.chave_telefone(numero_whatsapp) IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 3. executar_comando
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public._executar_comando_base(
  p_loja_id   uuid,
  p_remetente text,
  p_texto     text
) RETURNS json
LANGUAGE plpgsql
SET search_path = public, pg_catalog
AS $fn$
DECLARE
  v_chave     text := public.chave_telefone(p_remetente);
  v_ger       public.gerentes%ROWTYPE;
  v_vend      public.vendedores%ROWTYPE;
  v_alvo      public.vendedores%ROWTYPE;
  v_papel     text := 'desconhecido';
  v_quem      text;
  v_orig      text[];
  v_norm      text[];
  v_confirma  boolean := false;
  v_verbo     text;
  v_ini       int;
  v_nome      text;
  v_fone_raw  text;
  v_tel       text;
  v_resp      text;
  v_linhas    text;
  v_outro     text;
  v_n_ativos  int;
  v_total     int;
  v_desde     timestamptz;
  v_ordem     int;
  v_menu      text;
  i           int;
BEGIN
  IF p_loja_id IS NULL OR v_chave IS NULL THEN
    RETURN public._cmd_resp('desconhecido', 'ignorado', NULL);
  END IF;

  -- Papel. Gerente ativo ganha de vendedor.
  SELECT * INTO v_ger FROM public.gerentes
   WHERE loja_id = p_loja_id AND ativo AND public.chave_telefone(numero_whatsapp) = v_chave
   LIMIT 1;
  SELECT * INTO v_vend FROM public.vendedores
   WHERE loja_id = p_loja_id AND status IN ('ativo', 'inativo')
     AND public.chave_telefone(numero_whatsapp) = v_chave
   LIMIT 1;

  IF v_ger.id IS NOT NULL THEN
    v_papel := 'gerente';  v_quem := v_ger.nome;
  ELSIF v_vend.id IS NOT NULL THEN
    v_papel := 'vendedor'; v_quem := v_vend.nome;
  ELSE
    RETURN public._cmd_resp('desconhecido', 'ignorado', NULL);
  END IF;

  -- Serializa comandos da mesma loja (dois gerentes digitando ao mesmo tempo).
  PERFORM pg_advisory_xact_lock(hashtextextended('executar_comando:' || p_loja_id::text, 0));

  -- Palavras do texto, no original (para guardar o nome como foi digitado) e
  -- normalizadas (para comparar).
  v_orig := array_remove(string_to_array(
              translate(coalesce(p_texto, ''), chr(9) || chr(10) || chr(13) || chr(160), '    '),
              ' '), '');
  IF coalesce(array_length(v_orig, 1), 0) = 0 THEN
    v_orig := ARRAY['menu'];
  END IF;
  SELECT array_agg(public.normalizar_nome(t) ORDER BY o) INTO v_norm
    FROM unnest(v_orig) WITH ORDINALITY AS u(t, o);

  IF v_norm[1] = 'confirmar' THEN
    v_confirma := true;
    v_orig := v_orig[2:array_length(v_orig, 1)];
    v_norm := v_norm[2:array_length(v_norm, 1)];
    IF coalesce(array_length(v_norm, 1), 0) = 0 THEN
      RETURN public._cmd_resp(v_papel, 'erro', 'Faltou o comando depois de *confirmar*. Envie *menu* para ver as opções.');
    END IF;
  END IF;

  v_verbo := v_norm[1];

  -- Menu -------------------------------------------------------------------
  v_menu := '*Comandos disponíveis*';
  IF v_papel = 'gerente' THEN
    v_menu := v_menu || E'\n• status — resumo da loja'
                     || E'\n• leads — leads da loja'
                     || E'\n• listar vendedores'
                     || E'\n• inserir vendedor Nome 19 99999-8888'
                     || E'\n• pausar Nome'
                     || E'\n• reativar Nome'
                     || E'\n• excluir vendedor Nome'
                     || E'\n\nOs comandos que mudam a fila pedem confirmação: eu mostro o que vou fazer e você responde *sim*.';
  ELSE
    v_menu := v_menu || E'\n• meus leads'
                     || E'\n• status — seu resumo';
  END IF;
  IF v_papel = 'gerente' AND v_vend.id IS NOT NULL THEN
    v_menu := v_menu || E'\n• meus leads — os leads que são seus';
  END IF;

  IF v_verbo IN ('menu', 'ajuda', 'help') THEN
    RETURN public._cmd_resp(v_papel, 'info', v_menu);
  END IF;

  -- Leitura do vendedor: so o que e dele ------------------------------------
  IF (v_verbo = 'meus' AND v_norm[2] = 'leads')
     OR (v_verbo = 'leads' AND v_papel = 'vendedor')
     OR (v_verbo = 'status' AND v_papel = 'vendedor') THEN
    IF v_vend.id IS NULL THEN
      RETURN public._cmd_resp(v_papel, 'info', 'Você não está cadastrado como vendedor desta loja, então não há leads seus para mostrar.');
    END IF;
    v_desde := (date_trunc('day', now() AT TIME ZONE 'America/Sao_Paulo') - interval '2 days')
               AT TIME ZONE 'America/Sao_Paulo';
    SELECT count(*) INTO v_total FROM public.leads
     WHERE loja_id = p_loja_id AND vendedor_id = v_vend.id AND criado_em >= v_desde;
    SELECT string_agg(s.linha, E'\n' ORDER BY s.criado_em DESC) INTO v_linhas FROM (
      SELECT l.criado_em,
             '• ' || to_char(l.criado_em AT TIME ZONE 'America/Sao_Paulo', 'DD/MM HH24:MI')
             || ' ' || coalesce(nullif(l.nome_cliente, ''), '(sem nome)')
             || coalesce(' — ' || nullif(l.anuncio, ''), '')
             || ' [' || coalesce(l.origem, '?') || ']'
             || coalesce(' ' || nullif(public.formatar_telefone(l.numero_cliente), ''), '')
             || ' (' || coalesce(l.status_lead, '?') || ')' AS linha
        FROM public.leads l
       WHERE l.loja_id = p_loja_id AND l.vendedor_id = v_vend.id AND l.criado_em >= v_desde
       ORDER BY l.criado_em DESC
       LIMIT 30
    ) s;
    IF v_verbo = 'status' THEN
      RETURN public._cmd_resp(v_papel, 'info',
        '*Seu resumo* (últimos 3 dias)' || E'\nLeads recebidos: ' || v_total
        || E'\nSua situação na fila: ' || v_vend.status);
    END IF;
    IF v_total = 0 THEN
      RETURN public._cmd_resp(v_papel, 'info', 'Nenhum lead seu nos últimos 3 dias.');
    END IF;
    RETURN public._cmd_resp(v_papel, 'info',
      '*Seus leads* (últimos 3 dias): ' || v_total || E'\n\n' || v_linhas
      || CASE WHEN v_total > 30 THEN E'\n\nMostrando os 30 mais recentes.' ELSE '' END);
  END IF;

  -- Gerente: leitura que ja existe no n8n (status / leads) fica no caminho antigo.
  IF v_papel = 'gerente' AND v_verbo IN ('status', 'leads') THEN
    RETURN public._cmd_resp(v_papel, 'legado', NULL);
  END IF;

  -- A partir daqui, so gerente ------------------------------------------------
  IF v_verbo IN ('listar', 'inserir', 'pausar', 'despausar', 'reativar', 'excluir') THEN
    IF v_papel <> 'gerente' THEN
      RETURN public._cmd_resp(v_papel, 'negado', 'Esse comando é só para gerentes. Envie *menu* para ver o que você pode fazer.');
    END IF;
  ELSE
    RETURN public._cmd_resp(v_papel, 'erro', 'Comando não reconhecido.' || E'\n\n' || v_menu);
  END IF;

  -- listar vendedores
  IF v_verbo = 'listar' THEN
    IF coalesce(v_norm[2], '') NOT IN ('vendedores', 'vendedor') THEN
      RETURN public._cmd_resp(v_papel, 'erro', 'Quis dizer *listar vendedores*?');
    END IF;
    SELECT string_agg(
             '• ' || v.nome || ' — ' || v.status || ' — ' || coalesce(public.formatar_telefone(v.numero_whatsapp), 'sem telefone'),
             E'\n' ORDER BY CASE v.status WHEN 'ativo' THEN 0 WHEN 'inativo' THEN 1 ELSE 2 END, v.ordem_fila)
      INTO v_linhas
      FROM public.vendedores v WHERE v.loja_id = p_loja_id AND v.status <> 'removido';
    SELECT count(*) INTO v_total FROM public.vendedores WHERE loja_id = p_loja_id AND status = 'removido';
    RETURN public._cmd_resp(v_papel, 'info',
      '*Vendedores*' || E'\n' || coalesce(v_linhas, '(nenhum)')
      || CASE WHEN v_total > 0 THEN E'\n\n' || v_total || ' removido(s) não aparecem na lista.' ELSE '' END);
  END IF;

  -- Argumentos: palavras sem digito formam o nome; palavras com digito, o telefone.
  v_ini := 2;
  IF coalesce(v_norm[2], '') IN ('vendedor', 'vendedores') THEN v_ini := 3; END IF;
  FOR i IN v_ini .. coalesce(array_length(v_orig, 1), 0) LOOP
    IF public.somente_digitos(v_orig[i]) <> '' THEN
      v_fone_raw := coalesce(v_fone_raw, '') || public.somente_digitos(v_orig[i]);
    ELSIF translate(v_orig[i], '-+()./', '') <> '' THEN
      v_nome := trim(coalesce(v_nome, '') || ' ' || v_orig[i]);
    END IF;
  END LOOP;
  v_tel := public.normalizar_telefone_br(v_fone_raw);

  -- inserir vendedor ---------------------------------------------------------
  IF v_verbo = 'inserir' THEN
    IF coalesce(v_norm[2], '') NOT IN ('vendedor', 'vendedores') THEN
      RETURN public._cmd_resp(v_papel, 'erro', 'Quis dizer *inserir vendedor Nome 19 99999-8888*?');
    END IF;
    IF v_nome IS NULL THEN
      RETURN public._cmd_resp(v_papel, 'erro', 'Faltou o nome. Exemplo: *inserir vendedor João 19 99999-8888*');
    END IF;
    IF v_fone_raw IS NULL THEN
      RETURN public._cmd_resp(v_papel, 'erro', 'Para inserir é preciso o telefone. Exemplo: *inserir vendedor ' || v_nome || ' 19 99999-8888*');
    END IF;
    IF v_tel IS NULL THEN
      RETURN public._cmd_resp(v_papel, 'erro', 'Telefone inválido: ' || v_fone_raw || '. Use DDD + celular com 9 dígitos, por exemplo *19 99999-8888*.');
    END IF;

    SELECT * INTO v_alvo FROM public.vendedores
     WHERE loja_id = p_loja_id AND public.normalizar_nome(nome) = public.normalizar_nome(v_nome) LIMIT 1;
    IF v_alvo.id IS NOT NULL THEN
      RETURN public._cmd_resp(v_papel, 'erro',
        'Já existe um vendedor chamado *' || v_alvo.nome || '* (' || v_alvo.status || '). Os nomes não podem se repetir.'
        || CASE WHEN v_alvo.status <> 'ativo' THEN E'\nPara trazer de volta: *reativar ' || v_alvo.nome || '*' ELSE '' END);
    END IF;

    SELECT nome INTO v_outro FROM public.vendedores
     WHERE loja_id = p_loja_id AND status <> 'removido' AND public.chave_telefone(numero_whatsapp) = public.chave_telefone(v_tel) LIMIT 1;
    IF v_outro IS NULL THEN
      SELECT nome INTO v_outro FROM public.gerentes
       WHERE loja_id = p_loja_id AND ativo AND public.chave_telefone(numero_whatsapp) = public.chave_telefone(v_tel) LIMIT 1;
    END IF;
    IF v_outro IS NOT NULL THEN
      RETURN public._cmd_resp(v_papel, 'erro', 'Esse telefone (' || public.formatar_telefone(v_tel) || ') já está cadastrado para *' || v_outro || '*.');
    END IF;

    -- Em producao, uk_vendedores_loja_whatsapp (loja_id, numero_whatsapp) vale
    -- tambem para removidos: o numero de quem saiu continua ocupado. Avisar
    -- aqui, antes do eco, em vez de falhar so na confirmacao.
    SELECT nome INTO v_outro FROM public.vendedores
     WHERE loja_id = p_loja_id AND status = 'removido' AND public.chave_telefone(numero_whatsapp) = public.chave_telefone(v_tel) LIMIT 1;
    IF v_outro IS NOT NULL THEN
      RETURN public._cmd_resp(v_papel, 'erro', 'Esse telefone (' || public.formatar_telefone(v_tel) || ') é de *' || v_outro
        || E'*, que foi removido(a).\nPara trazer de volta: *reativar ' || v_outro || '*');
    END IF;

    IF NOT v_confirma THEN
      RETURN public._cmd_eco(v_papel,
        'Entendi: inserir o vendedor *' || v_nome || '* com o WhatsApp ' || public.formatar_telefone(v_tel)
        || E'.\nEntra no fim da fila.',
        'confirmar inserir vendedor ' || v_nome || ' ' || v_tel);
    END IF;

    SELECT coalesce(max(ordem_fila), 0) + 1 INTO v_ordem FROM public.vendedores WHERE loja_id = p_loja_id;
    BEGIN
      INSERT INTO public.vendedores (loja_id, nome, numero_whatsapp, status, ordem_fila)
      VALUES (p_loja_id, v_nome, v_tel, 'ativo', v_ordem);
    EXCEPTION WHEN unique_violation THEN
      RETURN public._cmd_resp(v_papel, 'erro', 'Não consegui inserir: nome ou telefone já existem nesta loja.');
    END;
    INSERT INTO public.atividades (loja_id, tipo, descricao)
    VALUES (p_loja_id, 'vendedor_adicionado', 'Vendedor ' || v_nome || ' adicionado à fila (comando de ' || v_quem || ')');
    RETURN public._cmd_resp(v_papel, 'executado',
      '✅ Vendedor *' || v_nome || '* adicionado à fila, WhatsApp ' || public.formatar_telefone(v_tel) || '.');
  END IF;

  -- pausar / despausar / reativar / excluir -----------------------------------
  IF v_nome IS NULL THEN
    RETURN public._cmd_resp(v_papel, 'erro', 'Faltou o nome do vendedor. Exemplo: *' || v_verbo || ' João*');
  END IF;
  IF v_verbo = 'despausar' THEN v_verbo := 'reativar'; END IF;

  SELECT * INTO v_alvo FROM public.vendedores
   WHERE loja_id = p_loja_id AND public.normalizar_nome(nome) = public.normalizar_nome(v_nome) LIMIT 1;
  IF v_alvo.id IS NULL THEN
    SELECT string_agg(nome, ', ' ORDER BY ordem_fila) INTO v_linhas
      FROM public.vendedores WHERE loja_id = p_loja_id AND status <> 'removido';
    RETURN public._cmd_resp(v_papel, 'erro',
      'Não encontrei vendedor com o nome *' || v_nome || '*.' || E'\nVendedores: ' || coalesce(v_linhas, '(nenhum)'));
  END IF;

  -- Telefone digitado, se vier, tem de conferir (checksum contra homonimo e erro de digito).
  IF v_fone_raw IS NOT NULL AND public.chave_telefone(v_fone_raw) IS DISTINCT FROM public.chave_telefone(v_alvo.numero_whatsapp) THEN
    RETURN public._cmd_resp(v_papel, 'erro',
      'O telefone informado não confere com o cadastro de *' || v_alvo.nome || '* (termina em '
      || right(public.somente_digitos(v_alvo.numero_whatsapp), 4) || '). Nada foi alterado.');
  END IF;

  IF v_verbo = 'pausar' AND v_alvo.status <> 'ativo' THEN
    RETURN public._cmd_resp(v_papel, 'erro', '*' || v_alvo.nome || '* já está ' || v_alvo.status || '.');
  ELSIF v_verbo = 'excluir' AND v_alvo.status = 'removido' THEN
    RETURN public._cmd_resp(v_papel, 'erro', '*' || v_alvo.nome || '* já foi removido.');
  ELSIF v_verbo = 'reativar' AND v_alvo.status = 'ativo' THEN
    RETURN public._cmd_resp(v_papel, 'erro', '*' || v_alvo.nome || '* já está ativo.');
  END IF;

  IF v_verbo IN ('pausar', 'excluir') AND v_alvo.status = 'ativo' THEN
    SELECT count(*) INTO v_n_ativos FROM public.vendedores WHERE loja_id = p_loja_id AND status = 'ativo';
    IF v_n_ativos <= 1 THEN
      RETURN public._cmd_resp(v_papel, 'erro',
        'Não dá para ' || v_verbo || ' *' || v_alvo.nome || '*: é o único vendedor ativo e a loja ficaria sem ninguém para receber leads.');
    END IF;
  END IF;

  IF v_verbo = 'reativar' THEN
    SELECT nome INTO v_outro FROM public.vendedores
     WHERE loja_id = p_loja_id AND status <> 'removido' AND id <> v_alvo.id
       AND public.chave_telefone(numero_whatsapp) = public.chave_telefone(v_alvo.numero_whatsapp) LIMIT 1;
    IF v_outro IS NOT NULL THEN
      RETURN public._cmd_resp(v_papel, 'erro', 'Não dá para reativar: o telefone de *' || v_alvo.nome || '* já é de *' || v_outro || '*.');
    END IF;
  END IF;

  IF NOT v_confirma OR v_fone_raw IS NULL THEN
    RETURN public._cmd_eco(v_papel,
      'Entendi: ' || v_verbo || ' *' || v_alvo.nome || '* (' || public.formatar_telefone(v_alvo.numero_whatsapp) || ').'
      || CASE v_verbo
           WHEN 'pausar'   THEN E'\nDeixa de receber novos leads até ser reativado(a).'
           WHEN 'excluir'  THEN E'\nSai da fila. O histórico de leads é mantido.'
           ELSE E'\nVolta a receber leads.'
         END,
      'confirmar ' || v_verbo || ' ' || v_alvo.nome || ' ' || public.somente_digitos(v_alvo.numero_whatsapp));
  END IF;

  UPDATE public.vendedores
     SET status = CASE v_verbo WHEN 'pausar' THEN 'inativo' WHEN 'excluir' THEN 'removido' ELSE 'ativo' END,
         atualizado_em = now()
   WHERE id = v_alvo.id AND loja_id = p_loja_id;

  INSERT INTO public.atividades (loja_id, tipo, descricao)
  VALUES (p_loja_id,
          CASE v_verbo WHEN 'pausar' THEN 'vendedor_inativado' WHEN 'excluir' THEN 'vendedor_removido' ELSE 'vendedor_reativado' END,
          CASE v_verbo
            WHEN 'pausar'  THEN 'Vendedor ' || v_alvo.nome || ' inativado'
            WHEN 'excluir' THEN 'Vendedor ' || v_alvo.nome || ' removido da fila'
            ELSE                'Vendedor ' || v_alvo.nome || ' reativado'
          END || ' (comando de ' || v_quem || ')');

  -- Mesmo recalculo de utils/queries.py::atualizar_proximo_vendedor_da_loja,
  -- feito la apenas ao inativar/remover.
  IF v_verbo IN ('pausar', 'excluir') THEN
    IF NOT EXISTS (SELECT 1 FROM public.vendedores WHERE loja_id = p_loja_id AND status = 'ativo') THEN
      UPDATE public.lojas SET proximo_vendedor_id = NULL WHERE id = p_loja_id;
    ELSIF NOT EXISTS (SELECT 1 FROM public.lojas l JOIN public.vendedores v ON v.id = l.proximo_vendedor_id
                       WHERE l.id = p_loja_id AND v.status = 'ativo') THEN
      UPDATE public.lojas
         SET proximo_vendedor_id = (SELECT id FROM public.vendedores
                                     WHERE loja_id = p_loja_id AND status = 'ativo'
                                     ORDER BY ordem_fila LIMIT 1)
       WHERE id = p_loja_id;
    END IF;
  END IF;

  RETURN public._cmd_resp(v_papel, 'executado',
    '✅ ' || CASE v_verbo WHEN 'pausar' THEN 'Pausado: ' WHEN 'excluir' THEN 'Removido da fila: ' ELSE 'Reativado: ' END
    || '*' || v_alvo.nome || '*.');
END
$fn$;


-- ---------------------------------------------------------------------------
-- 4. Confirmacao por "sim": pendencia + camada executar_comando
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.comandos_pendentes (
  loja_id          uuid NOT NULL REFERENCES public.lojas(id) ON DELETE CASCADE,
  remetente_chave  text NOT NULL,
  comando          text NOT NULL,
  criado_em        timestamptz NOT NULL DEFAULT now(),
  expira_em        timestamptz NOT NULL,
  PRIMARY KEY (loja_id, remetente_chave)
);
ALTER TABLE public.comandos_pendentes ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon')
     AND NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'comandos_pendentes') THEN
    EXECUTE 'CREATE POLICY "Deny all for anon" ON public.comandos_pendentes FOR ALL TO anon USING (false)';
  END IF;
END $$;

CREATE OR REPLACE FUNCTION public.executar_comando(
  p_loja_id   uuid,
  p_remetente text,
  p_texto     text
) RETURNS json
LANGUAGE plpgsql
SET search_path = public, pg_catalog
AS $fn$
DECLARE
  v_chave  text := public.chave_telefone(p_remetente);
  v_txt    text;
  v_pend   public.comandos_pendentes%ROWTYPE;
  v_r      json;
BEGIN
  IF p_loja_id IS NULL OR v_chave IS NULL THEN
    RETURN public._executar_comando_base(p_loja_id, p_remetente, p_texto);
  END IF;

  -- Mesmo lock da base (reentrante na transacao): pendencia e escrita andam juntas.
  PERFORM pg_advisory_xact_lock(hashtextextended('executar_comando:' || p_loja_id::text, 0));

  v_txt := trim(translate(public.normalizar_nome(p_texto), '.,!?;:', ''));
  SELECT * INTO v_pend FROM public.comandos_pendentes
   WHERE loja_id = p_loja_id AND remetente_chave = v_chave;

  IF v_txt IN ('sim', 's', 'ss', 'sim sim', 'pode', 'pode sim', 'sim pode', 'pode ser', 'confirma', 'confirmo',
               'confirmar', 'confirmado', 'ok', 'okay', 'isso', 'isso mesmo', 'isso ai', 'manda', 'pode mandar',
               'positivo', 'claro', 'certo', 'fechado', 'beleza', 'blz', 'yes', 'faz', 'pode fazer', 'faca') THEN
    IF v_pend.loja_id IS NULL THEN
      v_r := public._executar_comando_base(p_loja_id, p_remetente, 'menu');
      IF v_r->>'papel' = 'desconhecido' THEN RETURN v_r; END IF;
      RETURN public._cmd_resp(v_r->>'papel', 'erro', 'Não há nada aguardando confirmação. Envie *menu* para ver os comandos.');
    END IF;
    DELETE FROM public.comandos_pendentes WHERE loja_id = p_loja_id AND remetente_chave = v_chave;
    IF v_pend.expira_em < now() THEN
      v_r := public._executar_comando_base(p_loja_id, p_remetente, 'menu');
      RETURN public._cmd_resp(v_r->>'papel', 'erro', 'A confirmação expirou (5 minutos). Envie o comando de novo. Nada foi alterado.');
    END IF;
    -- Executa exatamente o comando guardado, com as mesmas validacoes de sempre
    -- (o estado pode ter mudado nesses minutos: a base confere tudo de novo).
    RETURN public._executar_comando_base(p_loja_id, p_remetente, v_pend.comando);
  END IF;

  IF v_txt IN ('nao', 'n', 'nao nao', 'cancela', 'cancelar', 'cancelado', 'cancele', 'esquece', 'deixa', 'deixa pra la',
               'nao quero', 'negativo', 'pare', 'no') THEN
    IF v_pend.loja_id IS NOT NULL THEN
      DELETE FROM public.comandos_pendentes WHERE loja_id = p_loja_id AND remetente_chave = v_chave;
      v_r := public._executar_comando_base(p_loja_id, p_remetente, 'menu');
      RETURN public._cmd_resp(v_r->>'papel', 'cancelado', 'Cancelado. Nada foi alterado.');
    END IF;
  END IF;

  -- Qualquer outra mensagem descarta a pendencia anterior.
  DELETE FROM public.comandos_pendentes WHERE loja_id = p_loja_id AND remetente_chave = v_chave;

  v_r := public._executar_comando_base(p_loja_id, p_remetente, p_texto);
  IF v_r->>'acao' = 'eco' AND v_r->>'confirmacao' IS NOT NULL THEN
    INSERT INTO public.comandos_pendentes (loja_id, remetente_chave, comando, expira_em)
    VALUES (p_loja_id, v_chave, v_r->>'confirmacao', now() + interval '5 minutes');
  END IF;
  RETURN v_r;
END
$fn$;


-- ---------------------------------------------------------------------------
-- 5. Camada de IA: a IA so SUGERE o comando; aqui se decide se a sugestao vale
-- ---------------------------------------------------------------------------
-- O n8n manda o texto original e a sugestao da IA (ou NULL, se a IA caiu).
-- A sugestao so e usada se passar nas travas; senao vale o texto original,
-- que e exatamente o comportamento sem IA. A IA nunca executa nada: o que ela
-- sugere passa por executar_comando, com eco e "sim" para qualquer escrita.
--
-- Travas:
--   1. primeira palavra tem de ser um verbo conhecido;
--   2. "confirmar ..." nunca vem da IA (a confirmacao e do humano);
--   3. todo digito da sugestao tem de estar no texto original, na mesma ordem
--      (a IA nao inventa telefone).
CREATE OR REPLACE FUNCTION public.executar_comando_ia(
  p_loja_id   uuid,
  p_remetente text,
  p_texto     text,
  p_sugestao  text
) RETURNS json
LANGUAGE plpgsql
SET search_path = public, pg_catalog
AS $fn$
DECLARE
  v_sug    text := nullif(trim(coalesce(p_sugestao, '')), '');
  v_verbo  text;
  v_dig_s  text;
  v_dig_t  text;
  v_usar   text;
  v_motivo text;
  v_r      json;
BEGIN
  v_usar := p_texto;
  IF v_sug IS NULL THEN
    v_motivo := 'sem_sugestao';
  ELSE
    v_verbo := split_part(public.normalizar_nome(v_sug), ' ', 1);
    v_dig_s := public.somente_digitos(v_sug);
    v_dig_t := public.somente_digitos(p_texto);
    IF v_verbo NOT IN ('menu', 'ajuda', 'status', 'leads', 'meus', 'listar', 'inserir', 'pausar',
                       'despausar', 'reativar', 'excluir', 'sim', 'nao') THEN
      v_motivo := 'verbo_desconhecido';
    ELSIF v_dig_s <> '' AND position(v_dig_s IN v_dig_t) = 0
          AND position(v_dig_s IN '55' || v_dig_t) = 0 THEN
      v_motivo := 'telefone_inventado';
    ELSE
      v_usar := v_sug;
      v_motivo := 'sugestao_usada';
    END IF;
  END IF;

  v_r := public.executar_comando(p_loja_id, p_remetente, v_usar);
  RETURN (v_r::jsonb || jsonb_build_object('interpretado', v_usar, 'ia', v_motivo))::json;
END
$fn$;

-- Chamada so pelo n8n (service_role). Nunca por anon/authenticated.
DO $$
DECLARE f text;
BEGIN
  FOREACH f IN ARRAY ARRAY['public.executar_comando(uuid, text, text)', 'public._executar_comando_base(uuid, text, text)',
                           'public.executar_comando_ia(uuid, text, text, text)'] LOOP
    EXECUTE 'REVOKE ALL ON FUNCTION ' || f || ' FROM PUBLIC';
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
      EXECUTE 'REVOKE ALL ON FUNCTION ' || f || ' FROM anon';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
      EXECUTE 'REVOKE ALL ON FUNCTION ' || f || ' FROM authenticated';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
      EXECUTE 'GRANT EXECUTE ON FUNCTION ' || f || ' TO service_role';
    END IF;
  END LOOP;
  -- tabela de pendencias: so o service_role (RLS + policy acima barram anon)
  EXECUTE 'REVOKE ALL ON public.comandos_pendentes FROM PUBLIC';
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN EXECUTE 'REVOKE ALL ON public.comandos_pendentes FROM anon'; END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN EXECUTE 'REVOKE ALL ON public.comandos_pendentes FROM authenticated'; END IF;
  -- explicito: nao depender do default privileges do Supabase para tabela nova
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
    EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON public.comandos_pendentes TO service_role';
  END IF;
END $$;

COMMIT;
