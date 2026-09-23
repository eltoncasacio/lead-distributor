-- Fase 3 — registrar toda mensagem que chega, com o desfecho dela.
--
-- NAO altera a tabela `leads` nem a funcao `distribuir_lead`. A regra de
-- distribuicao continua inteira no Postgres (ADR 0001) e este arquivo nao a
-- toca. A tabela nova e um livro-razao de entrada: uma linha por mensagem
-- candidata, com o que o sistema decidiu e por que.
--
-- Por que tabela nova e nao um `status_lead` novo: `status_lead` e o estado
-- COMERCIAL de um lead que ja tem dono. Um 'pendente_triagem' contaminaria
-- get_leads_lista, o funil, o KPI "Leads Hoje" e as RPCs comando_status /
-- comando_leads que os vendedores leem pelo WhatsApp. E um boleto de banco
-- nao pode ocupar linha em `leads`, ou os numeros da loja param de significar
-- alguma coisa.
--
-- A constraint CHECK de atividades.tipo NAO e alterada aqui de proposito:
-- ela so e necessaria na Fase 5 (tela de triagem), e estende-la sem ver a
-- definicao exata e arriscado. Fica para a migration daquela fase.
--
-- Rollback: ROLLBACK_mensagens_recebidas.sql (mesmo diretorio).

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Tabela
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.mensagens_recebidas (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  loja_id              uuid NOT NULL REFERENCES public.lojas(id) ON DELETE CASCADE,

  -- de onde veio
  canal                varchar NOT NULL,          -- whatsapp | email | webhook
  origem_detectada     varchar,                   -- NaPista, Mobiauto, ... ou NULL
  mensagem_externa_id  varchar,                   -- Evolution data.key.id
  remetente_numero     varchar,
  remetente_nome       varchar,
  texto                text,
  payload_bruto        jsonb,                     -- nulado apos 90d, linha mantida
  recebido_em          timestamptz NOT NULL DEFAULT now(),

  -- o que o sistema decidiu
  classificacao        varchar,                   -- lead_novo|pos_venda|nao_lead|incerto
  classificado_por     varchar,                   -- regra | llm | humano
  confianca            numeric(3,2),
  motivo               text,
  telefone_extraido    varchar,
  telefone_verificado  boolean NOT NULL DEFAULT false,
  anuncio_extraido     varchar,

  -- desfecho
  decisao              varchar,                   -- distribuido | distribuido_com_duvida
                                                  -- | duplicado | arquivado | erro | sombra
  lead_id              uuid REFERENCES public.leads(id) ON DELETE SET NULL,
  erro                 text,

  -- revisao humana
  revisado_em          timestamptz,
  revisao_acao         varchar,                   -- promovido | arquivado | ignorado

  n8n_execution_id     varchar,
  criado_em            timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.mensagens_recebidas IS
  'Livro-razao de toda mensagem candidata a lead, com classificacao e desfecho. '
  'Nao substitui `leads`: um lead so existe quando distribuir_lead o cria.';

-- Fecha a lacuna de reenvio da Evolution: o mesmo evento chegando duas vezes
-- nao cria duas linhas. Parcial porque mensagem_externa_id e nulo em canais
-- que nao tem id proprio (ex.: webhook de portal).
CREATE UNIQUE INDEX IF NOT EXISTS uq_mensagens_recebidas_externa
  ON public.mensagens_recebidas (loja_id, canal, mensagem_externa_id)
  WHERE mensagem_externa_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_mensagens_recebidas_loja_recebido
  ON public.mensagens_recebidas (loja_id, recebido_em DESC);

-- Monitor de saude por origem (Fase 7)
CREATE INDEX IF NOT EXISTS ix_mensagens_recebidas_origem
  ON public.mensagens_recebidas (loja_id, origem_detectada, recebido_em DESC);

-- Fila da tela de triagem: parcial, so o que precisa de humano
CREATE INDEX IF NOT EXISTS ix_mensagens_recebidas_revisao
  ON public.mensagens_recebidas (loja_id, recebido_em DESC)
  WHERE decisao IN ('distribuido_com_duvida', 'erro') AND revisado_em IS NULL;

ALTER TABLE public.mensagens_recebidas ENABLE ROW LEVEL SECURITY;
-- Sem policy: nega tudo para anon/authenticated, como o resto do schema.
-- O acesso e via service_role (n8n e Dashboard), que contorna RLS.

-- ---------------------------------------------------------------------------
-- 2. Registrar a mensagem — chamada ANTES de distribuir_lead
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.registrar_mensagem_recebida(
  p_loja_id             uuid,
  p_canal               varchar,
  p_origem_detectada    varchar    DEFAULT NULL,
  p_mensagem_externa_id varchar    DEFAULT NULL,
  p_remetente_numero    varchar    DEFAULT NULL,
  p_remetente_nome      varchar    DEFAULT NULL,
  p_texto               text       DEFAULT NULL,
  p_payload_bruto       jsonb      DEFAULT NULL,
  p_recebido_em         timestamptz DEFAULT now(),
  p_classificacao       varchar    DEFAULT NULL,
  p_classificado_por    varchar    DEFAULT NULL,
  p_confianca           numeric    DEFAULT NULL,
  p_motivo              text       DEFAULT NULL,
  p_telefone_extraido   varchar    DEFAULT NULL,
  p_telefone_verificado boolean    DEFAULT false,
  p_anuncio_extraido    varchar    DEFAULT NULL,
  p_n8n_execution_id    varchar    DEFAULT NULL
) RETURNS uuid
LANGUAGE plpgsql
AS $$
DECLARE
  v_id uuid;
BEGIN
  INSERT INTO public.mensagens_recebidas (
    loja_id, canal, origem_detectada, mensagem_externa_id, remetente_numero,
    remetente_nome, texto, payload_bruto, recebido_em, classificacao,
    classificado_por, confianca, motivo, telefone_extraido,
    telefone_verificado, anuncio_extraido, n8n_execution_id
  ) VALUES (
    p_loja_id, p_canal, p_origem_detectada, p_mensagem_externa_id,
    p_remetente_numero, p_remetente_nome, p_texto, p_payload_bruto,
    p_recebido_em, p_classificacao, p_classificado_por, p_confianca,
    p_motivo, p_telefone_extraido, p_telefone_verificado,
    p_anuncio_extraido, p_n8n_execution_id
  )
  -- reenvio do mesmo evento devolve a linha que ja existe, nao cria outra
  ON CONFLICT (loja_id, canal, mensagem_externa_id)
    WHERE mensagem_externa_id IS NOT NULL
    DO UPDATE SET texto = COALESCE(EXCLUDED.texto, mensagens_recebidas.texto)
  RETURNING id INTO v_id;

  RETURN v_id;
END;
$$;

COMMENT ON FUNCTION public.registrar_mensagem_recebida IS
  'Grava a mensagem ANTES de tentar distribuir. Idempotente por '
  '(loja_id, canal, mensagem_externa_id).';

-- ---------------------------------------------------------------------------
-- 3. Carimbar o desfecho — chamada DEPOIS de distribuir_lead
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.atualizar_desfecho_mensagem(
  p_id      uuid,
  p_decisao varchar,
  p_lead_id uuid DEFAULT NULL,
  p_erro    text DEFAULT NULL
) RETURNS boolean
LANGUAGE plpgsql
AS $$
BEGIN
  UPDATE public.mensagens_recebidas
     SET decisao = p_decisao,
         lead_id = COALESCE(p_lead_id, lead_id),
         erro    = COALESCE(p_erro, erro)
   WHERE id = p_id;
  RETURN FOUND;
END;
$$;

-- ---------------------------------------------------------------------------
-- 4. Promover para lead — o humano completa o que faltava
-- ---------------------------------------------------------------------------
-- Chama distribuir_lead POR DENTRO. A fila humana nao pode ter copia propria
-- de round-robin nem de deduplicacao: e isso que preserva o ADR 0001.

CREATE OR REPLACE FUNCTION public.promover_mensagem_para_lead(
  p_loja_id     uuid,
  p_mensagem_id uuid,
  p_telefone    varchar,
  p_nome        varchar DEFAULT NULL,
  p_anuncio     varchar DEFAULT NULL
) RETURNS TABLE (
  lead_id                  uuid,
  vendedor_id              uuid,
  vendedor_nome            varchar,
  vendedor_numero_whatsapp varchar,
  duplicado                boolean
)
LANGUAGE plpgsql
AS $$
DECLARE
  v_msg public.mensagens_recebidas%ROWTYPE;
  v_res record;
BEGIN
  SELECT * INTO v_msg
    FROM public.mensagens_recebidas
   WHERE id = p_mensagem_id AND loja_id = p_loja_id;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'mensagem % nao encontrada na loja %', p_mensagem_id, p_loja_id;
  END IF;

  IF v_msg.revisado_em IS NOT NULL THEN
    RAISE EXCEPTION 'mensagem % ja foi revisada em %', p_mensagem_id, v_msg.revisado_em;
  END IF;

  IF coalesce(regexp_replace(p_telefone, '\D', '', 'g'), '') = '' THEN
    RAISE EXCEPTION 'telefone obrigatorio para promover a lead';
  END IF;

  SELECT * INTO v_res FROM public.distribuir_lead(
    p_loja_id           := p_loja_id,
    p_numero_cliente    := regexp_replace(p_telefone, '\D', '', 'g'),
    p_nome_cliente      := COALESCE(p_nome, v_msg.remetente_nome, p_telefone),
    p_anuncio           := COALESCE(p_anuncio, v_msg.anuncio_extraido, ''),
    p_mensagem_original := COALESCE(v_msg.texto, ''),
    p_recebido_em       := v_msg.recebido_em,
    p_origem            := COALESCE(v_msg.origem_detectada, 'Triagem manual')
  ) LIMIT 1;

  UPDATE public.mensagens_recebidas
     SET decisao      = 'distribuido',
         lead_id      = v_res.lead_id,
         revisado_em  = now(),
         revisao_acao = 'promovido',
         telefone_extraido   = regexp_replace(p_telefone, '\D', '', 'g'),
         telefone_verificado = true,
         classificado_por    = 'humano'
   WHERE id = p_mensagem_id;

  lead_id                  := v_res.lead_id;
  vendedor_id              := v_res.vendedor_id;
  vendedor_nome            := v_res.vendedor_nome;
  vendedor_numero_whatsapp := v_res.vendedor_numero_whatsapp;
  duplicado                := v_res.duplicado;
  RETURN NEXT;
END;
$$;

COMMENT ON FUNCTION public.promover_mensagem_para_lead IS
  'Promove uma mensagem em triagem a lead chamando distribuir_lead por dentro. '
  'Round-robin e deduplicacao continuam morando so la (ADR 0001).';

-- ---------------------------------------------------------------------------
-- 5. Arquivar — o humano diz que nao era lead
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.arquivar_mensagem(
  p_loja_id     uuid,
  p_mensagem_id uuid,
  p_motivo      text DEFAULT NULL
) RETURNS boolean
LANGUAGE plpgsql
AS $$
BEGIN
  UPDATE public.mensagens_recebidas
     SET decisao      = 'arquivado',
         revisado_em  = now(),
         revisao_acao = 'arquivado',
         motivo       = COALESCE(p_motivo, motivo),
         classificado_por = 'humano'
   WHERE id = p_mensagem_id AND loja_id = p_loja_id;
  RETURN FOUND;
END;
$$;

-- ---------------------------------------------------------------------------
-- 6. Permissoes — so service_role, como o resto do schema
-- ---------------------------------------------------------------------------

REVOKE ALL ON FUNCTION public.registrar_mensagem_recebida FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.atualizar_desfecho_mensagem  FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.promover_mensagem_para_lead  FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.arquivar_mensagem            FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION public.registrar_mensagem_recebida TO service_role;
GRANT EXECUTE ON FUNCTION public.atualizar_desfecho_mensagem  TO service_role;
GRANT EXECUTE ON FUNCTION public.promover_mensagem_para_lead  TO service_role;
GRANT EXECUTE ON FUNCTION public.arquivar_mensagem            TO service_role;

COMMIT;

-- ---------------------------------------------------------------------------
-- Conferir depois de aplicar
-- ---------------------------------------------------------------------------
--
-- 1) a tabela existe e esta vazia
--    SELECT count(*) FROM public.mensagens_recebidas;           -- 0
--
-- 2) `leads` e `distribuir_lead` intocados
--    SELECT count(*) FROM leads;                                -- mesmo de antes
--    SELECT pg_get_function_identity_arguments(oid)
--      FROM pg_proc WHERE proname='distribuir_lead';            -- 7 argumentos
--
-- 3) as 4 funcoes novas existem
--    SELECT proname FROM pg_proc
--     WHERE proname IN ('registrar_mensagem_recebida','atualizar_desfecho_mensagem',
--                       'promover_mensagem_para_lead','arquivar_mensagem');
--
-- 4) anon nao executa nenhuma delas
--    SELECT has_function_privilege('anon','promover_mensagem_para_lead(uuid,uuid,character varying,character varying,character varying)','EXECUTE');
--    -- false
