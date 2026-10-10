-- Desfaz FIX_comandos_whatsapp.sql. Nao mexe em nenhum dado.
BEGIN;
DROP FUNCTION IF EXISTS public.executar_comando_ia(uuid, text, text, jsonb);
DROP FUNCTION IF EXISTS public.executar_comando_ia(uuid, text, text, text);
DROP FUNCTION IF EXISTS public.executar_comando(uuid, text, text);
DROP FUNCTION IF EXISTS public._executar_comando_base(uuid, text, text);
DROP TABLE IF EXISTS public.comandos_pendentes;  -- so pendencias de 5 min, nenhum dado de negocio
DROP INDEX IF EXISTS public.uq_vendedores_loja_nome;
DROP INDEX IF EXISTS public.uq_vendedores_loja_telefone;
DROP FUNCTION IF EXISTS public._cmd_resp(text, text, text);
DROP FUNCTION IF EXISTS public._cmd_eco(text, text, text);
DROP FUNCTION IF EXISTS public.formatar_telefone(text);
DROP FUNCTION IF EXISTS public.chave_telefone(text);
DROP FUNCTION IF EXISTS public.normalizar_telefone_br(text);
DROP FUNCTION IF EXISTS public.somente_digitos(text);
DROP FUNCTION IF EXISTS public.normalizar_nome(text);
COMMIT;
