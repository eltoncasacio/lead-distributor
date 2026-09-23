-- Rollback da Fase 3 (FIX_mensagens_recebidas.sql).
--
-- Reverte ao estado anterior: nenhuma tabela `mensagens_recebidas`, nenhuma
-- das 4 funcoes novas. `leads` e `distribuir_lead` nunca foram tocados pela
-- migration, entao nao ha o que restaurar neles.
--
-- ATENCAO: DROP TABLE apaga os dados registrados desde a aplicacao. Se ja
-- houver linhas que importam (mensagens em triagem ainda nao trabalhadas),
-- exporte antes:
--
--   COPY (SELECT * FROM public.mensagens_recebidas)
--     TO '/tmp/mensagens_recebidas_backup.csv' CSV HEADER;
--
-- ou, pelo Dashboard do Supabase, Table Editor -> Export.
--
-- Se o objetivo for so parar de gravar sem perder o que ja foi registrado,
-- NAO rode este arquivo: desligue o no de registro no n8n. A tabela parada
-- nao faz mal nenhum.

BEGIN;

DROP FUNCTION IF EXISTS public.arquivar_mensagem(uuid, uuid, text);
DROP FUNCTION IF EXISTS public.promover_mensagem_para_lead(uuid, uuid, character varying, character varying, character varying);
DROP FUNCTION IF EXISTS public.atualizar_desfecho_mensagem(uuid, character varying, uuid, text);
DROP FUNCTION IF EXISTS public.registrar_mensagem_recebida(
  uuid, character varying, character varying, character varying, character varying,
  character varying, text, jsonb, timestamptz, character varying, character varying,
  numeric, text, character varying, boolean, character varying, character varying);

DROP TABLE IF EXISTS public.mensagens_recebidas;

COMMIT;

-- Conferir:
--   SELECT to_regclass('public.mensagens_recebidas');   -- NULL
--   SELECT count(*) FROM pg_proc
--    WHERE proname IN ('registrar_mensagem_recebida','atualizar_desfecho_mensagem',
--                      'promover_mensagem_para_lead','arquivar_mensagem');  -- 0
--   SELECT count(*) FROM leads;                          -- inalterado
