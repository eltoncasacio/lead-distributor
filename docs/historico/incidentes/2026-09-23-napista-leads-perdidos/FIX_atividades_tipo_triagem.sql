-- Fase 5 — permitir os dois tipos de atividade da tela de triagem.
--
-- `atividades.tipo` tem CHECK restritivo (confirmado: INSERT com
-- 'lead_promovido_de_triagem' devolve 23514). Os tipos EM USO hoje sao
-- novo_lead, fila_reordenada, status_lead_alterado, vendedor_adicionado,
-- vendedor_removido, vendedor_inativado e vendedor_reativado — mas a
-- constraint pode aceitar outros que ainda nao apareceram nos dados
-- (utils/queries.py usa gerente_adicionado e gerente_desativado, por
-- exemplo).
--
-- Por isso este script NAO reescreve a lista: ele le a definicao atual e
-- acrescenta os dois valores novos com um OR. Nada que era aceito deixa de
-- ser. Sem isso, a tela de triagem promoveria o lead e falharia ao gravar a
-- atividade.
--
-- Rollback: ROLLBACK_atividades_tipo_triagem.sql

BEGIN;

DO $$
DECLARE
  v_nome text;
  v_def  text;
BEGIN
  SELECT conname, pg_get_constraintdef(oid)
    INTO v_nome, v_def
    FROM pg_constraint
   WHERE conrelid = 'public.atividades'::regclass
     AND contype = 'c'
     AND pg_get_constraintdef(oid) ILIKE '%tipo%'
   LIMIT 1;

  IF v_nome IS NULL THEN
    RAISE NOTICE 'Nenhuma CHECK sobre atividades.tipo — nada a fazer.';
    RETURN;
  END IF;

  IF v_def ILIKE '%lead_promovido_de_triagem%' THEN
    RAISE NOTICE 'Constraint % ja aceita os tipos da triagem.', v_nome;
    RETURN;
  END IF;

  RAISE NOTICE 'Constraint atual: % -> %', v_nome, v_def;

  EXECUTE format('ALTER TABLE public.atividades DROP CONSTRAINT %I', v_nome);

  -- substring(v_def from 7) remove o prefixo 'CHECK ' e preserva os
  -- parenteses da expressao original intactos.
  EXECUTE format(
    'ALTER TABLE public.atividades ADD CONSTRAINT %I CHECK ((%s) OR tipo = ANY (ARRAY[%L, %L]))',
    v_nome, substring(v_def from 7), 'mensagem_triada', 'lead_promovido_de_triagem');

  RAISE NOTICE 'Constraint % estendida.', v_nome;
END $$;

COMMIT;

-- Conferir depois de aplicar:
--
--   SELECT pg_get_constraintdef(oid) FROM pg_constraint
--    WHERE conrelid='public.atividades'::regclass AND contype='c';
--
--   -- deve aceitar os dois novos:
--   INSERT INTO atividades (loja_id, tipo, descricao)
--   VALUES ('<LOJA_ID>','lead_promovido_de_triagem','teste');
--   DELETE FROM atividades WHERE descricao = 'teste';
--
--   -- e continuar aceitando os antigos:
--   INSERT INTO atividades (loja_id, tipo, descricao)
--   VALUES ('<LOJA_ID>','novo_lead','teste');
--   DELETE FROM atividades WHERE descricao = 'teste';
