-- Desfaz FIX_portaria_sombra.sql. Apaga a tabela de sombra (so registros da avaliacao; nenhum dado de negocio).
BEGIN;
DROP FUNCTION IF EXISTS public.registrar_portaria_sombra(uuid, text, text, text, text, text, text, text);
DROP FUNCTION IF EXISTS public.portaria_sombra_preparar(uuid, text, text, int);
DROP FUNCTION IF EXISTS public.portaria_numero_plataforma(text);
DROP TABLE IF EXISTS public.portaria_sombra;
DELETE FROM public.ia_uso WHERE remetente_chave = 'portaria';
COMMIT;
