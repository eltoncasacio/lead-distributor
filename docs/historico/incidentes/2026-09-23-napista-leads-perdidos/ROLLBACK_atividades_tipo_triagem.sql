-- Rollback de FIX_atividades_tipo_triagem.sql.
--
-- Remove o "OR tipo = ANY (ARRAY['mensagem_triada','lead_promovido_de_triagem'])"
-- acrescentado, devolvendo a constraint a expressao original.
--
-- ATENCAO: se ja houver linhas em `atividades` com esses tipos, o ALTER falha
-- na validacao. Apague-as antes, ou deixe a constraint como esta — ela nao
-- causa mal nenhum aceitando dois valores a mais.
--
--   SELECT count(*) FROM atividades
--    WHERE tipo IN ('mensagem_triada','lead_promovido_de_triagem');

BEGIN;

DO $$
DECLARE
  v_nome text;
  v_def  text;
  v_orig text;
BEGIN
  SELECT conname, pg_get_constraintdef(oid)
    INTO v_nome, v_def
    FROM pg_constraint
   WHERE conrelid = 'public.atividades'::regclass
     AND contype = 'c'
     AND pg_get_constraintdef(oid) ILIKE '%lead_promovido_de_triagem%'
   LIMIT 1;

  IF v_nome IS NULL THEN
    RAISE NOTICE 'Constraint ja esta no formato original — nada a fazer.';
    RETURN;
  END IF;

  -- extrai o "((...))" que estava entre 'CHECK (' e ' OR tipo = ANY'
  v_orig := substring(v_def from 'CHECK \((.*) OR tipo = ANY');
  IF v_orig IS NULL THEN
    RAISE EXCEPTION 'Nao consegui extrair a expressao original de: %', v_def;
  END IF;

  EXECUTE format('ALTER TABLE public.atividades DROP CONSTRAINT %I', v_nome);
  EXECUTE format('ALTER TABLE public.atividades ADD CONSTRAINT %I CHECK %s',
                 v_nome, v_orig);
  RAISE NOTICE 'Constraint % revertida.', v_nome;
END $$;

COMMIT;
