-- Portaria v3 — MODO SOMBRA (spec 07, topo). 2026-10-10.
--
-- A IA classifica a primeira mensagem de numero novo e o resultado e GRAVADO
-- aqui — e so. Nada e ignorado, nada deixa de ser distribuido: o fluxo de
-- leads continua identico. Serve para o dono olhar, depois de uma semana, o
-- que a Portaria TERIA ignorado.
--
-- Nao toca leads, mensagens_recebidas, vendedores nem distribuir_lead.
-- Depende de: chave_telefone, normalizar_nome, ia_uso (sql/comandos_whatsapp).
-- Rollback: ROLLBACK_portaria_sombra.sql.

BEGIN;

CREATE TABLE IF NOT EXISTS public.portaria_sombra (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  loja_id              uuid NOT NULL REFERENCES public.lojas(id) ON DELETE CASCADE,
  remetente_numero     text NOT NULL,
  mensagem_externa_id  text,
  texto                text,
  classificacao_ia     text,                    -- o que a IA respondeu (cru)
  classificacao        text NOT NULL CHECK (classificacao IN ('lead', 'nao_lead', 'duvida')),  -- depois das travas
  decisao              text NOT NULL CHECK (decisao IN ('distribuir', 'ignorar')),          -- o que a Portaria FARIA
  motivo               text,
  trecho_evidencia     text,
  trava                text,
  modelo               text,
  criado_em            timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_portaria_sombra_loja_criado ON public.portaria_sombra (loja_id, criado_em DESC);
ALTER TABLE public.portaria_sombra ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon')
     AND NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'portaria_sombra') THEN
    EXECUTE 'CREATE POLICY "Deny all for anon" ON public.portaria_sombra FOR ALL TO anon USING (false)';
  END IF;
END $$;

-- Numeros de plataforma (NaPista, iCarros): ja tem tratamento proprio, nao passam pela IA.
CREATE OR REPLACE FUNCTION public.portaria_numero_plataforma(p text) RETURNS boolean
LANGUAGE sql IMMUTABLE AS $$
  SELECT public.chave_telefone(p) IN (public.chave_telefone('551131361712'), public.chave_telefone('551130044558'))
$$;

-- Decide se a mensagem entra na sombra. Nao escreve nada alem do contador.
--   numero novo = nenhum lead desta loja para este numero criado ha mais de
--   2 minutos (o lead DESTA mesma mensagem pode ja ter sido criado na mesma
--   execucao do n8n — ele nao conta).
CREATE OR REPLACE FUNCTION public.portaria_sombra_preparar(
  p_loja_id   uuid,
  p_remetente text,
  p_texto     text,
  p_limite    int DEFAULT 200
) RETURNS json
LANGUAGE plpgsql
SET search_path = public, pg_catalog
AS $fn$
DECLARE
  v_chave text := public.chave_telefone(p_remetente);
  v_dia   date := (now() AT TIME ZONE 'America/Sao_Paulo')::date;
  v_n     int;
BEGIN
  IF p_loja_id IS NULL OR v_chave IS NULL THEN
    RETURN json_build_object('usar', false, 'motivo', 'sem_remetente');
  END IF;
  IF coalesce(trim(p_texto), '') = '' THEN
    RETURN json_build_object('usar', false, 'motivo', 'sem_texto');          -- audio/foto: distribui sempre
  END IF;
  IF public.portaria_numero_plataforma(p_remetente) THEN
    RETURN json_build_object('usar', false, 'motivo', 'plataforma');
  END IF;
  IF EXISTS (SELECT 1 FROM public.gerentes WHERE loja_id = p_loja_id AND public.chave_telefone(numero_whatsapp) = v_chave)
     OR EXISTS (SELECT 1 FROM public.vendedores WHERE loja_id = p_loja_id AND public.chave_telefone(numero_whatsapp) = v_chave) THEN
    RETURN json_build_object('usar', false, 'motivo', 'equipe');
  END IF;
  IF EXISTS (SELECT 1 FROM public.leads WHERE loja_id = p_loja_id
               AND public.chave_telefone(numero_cliente) = v_chave
               AND criado_em < now() - interval '2 minutes') THEN
    RETURN json_build_object('usar', false, 'motivo', 'numero_conhecido');
  END IF;

  -- limite de custo: por loja, por dia (contador separado do dos comandos)
  INSERT INTO public.ia_uso AS u (loja_id, remetente_chave, dia, chamadas)
  VALUES (p_loja_id, 'portaria', v_dia, 1)
  ON CONFLICT (loja_id, remetente_chave, dia)
  DO UPDATE SET chamadas = u.chamadas + 1 WHERE u.chamadas < p_limite
  RETURNING chamadas INTO v_n;
  IF v_n IS NULL THEN
    RETURN json_build_object('usar', false, 'motivo', 'limite_diario');
  END IF;
  RETURN json_build_object('usar', true, 'motivo', 'numero_novo', 'chamadas_hoje', v_n);
END
$fn$;

-- Grava o que a IA disse, aplicando as MESMAS travas de portaria/prompt.py:
--   classificacao fora de {lead, nao_lead, duvida} -> duvida
--   nao_lead sem trecho literal (>= 6 caracteres) da mensagem -> duvida
CREATE OR REPLACE FUNCTION public.registrar_portaria_sombra(
  p_loja_id             uuid,
  p_remetente           text,
  p_mensagem_externa_id text,
  p_texto               text,
  p_classificacao       text,
  p_motivo              text,
  p_trecho              text,
  p_modelo              text
) RETURNS json
LANGUAGE plpgsql
SET search_path = public, pg_catalog
AS $fn$
DECLARE
  v_class text := p_classificacao;
  v_trava text;
  v_trecho text := trim(coalesce(p_trecho, ''));
BEGIN
  IF v_class IS NULL OR v_class NOT IN ('lead', 'nao_lead', 'duvida') THEN
    v_class := 'duvida'; v_trava := 'resposta_invalida';
  ELSIF v_class = 'nao_lead' AND (length(v_trecho) < 6 OR position(v_trecho IN coalesce(p_texto, '')) = 0) THEN
    v_class := 'duvida'; v_trava := 'evidencia_nao_literal';
  END IF;
  INSERT INTO public.portaria_sombra (loja_id, remetente_numero, mensagem_externa_id, texto, classificacao_ia,
                                      classificacao, decisao, motivo, trecho_evidencia, trava, modelo)
  VALUES (p_loja_id, coalesce(p_remetente, '?'), p_mensagem_externa_id, left(p_texto, 1000), p_classificacao,
          v_class, CASE WHEN v_class = 'nao_lead' THEN 'ignorar' ELSE 'distribuir' END,
          left(p_motivo, 300), left(p_trecho, 300), v_trava, p_modelo);
  RETURN json_build_object('classificacao', v_class, 'decisao', CASE WHEN v_class = 'nao_lead' THEN 'ignorar' ELSE 'distribuir' END, 'trava', v_trava);
END
$fn$;

-- So o n8n (service_role).
DO $$
DECLARE f text;
BEGIN
  FOREACH f IN ARRAY ARRAY['public.portaria_sombra_preparar(uuid, text, text, int)',
                           'public.registrar_portaria_sombra(uuid, text, text, text, text, text, text, text)'] LOOP
    EXECUTE 'REVOKE ALL ON FUNCTION ' || f || ' FROM PUBLIC';
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN EXECUTE 'REVOKE ALL ON FUNCTION ' || f || ' FROM anon'; END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN EXECUTE 'REVOKE ALL ON FUNCTION ' || f || ' FROM authenticated'; END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN EXECUTE 'GRANT EXECUTE ON FUNCTION ' || f || ' TO service_role'; END IF;
  END LOOP;
  EXECUTE 'REVOKE ALL ON public.portaria_sombra FROM PUBLIC';
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN EXECUTE 'REVOKE ALL ON public.portaria_sombra FROM anon'; END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN EXECUTE 'REVOKE ALL ON public.portaria_sombra FROM authenticated'; END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
    EXECUTE 'GRANT SELECT, INSERT ON public.portaria_sombra TO service_role';
  END IF;
END $$;

COMMIT;
