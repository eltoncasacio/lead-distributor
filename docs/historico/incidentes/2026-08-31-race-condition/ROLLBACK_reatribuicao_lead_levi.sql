-- ROLLBACK da reatribuição do 2º lead do Levi S. (2026-08-31)
-- Devolve o lead para o Japa, exatamente como estava antes.
--
-- Estado original:
--   lead_id     2036bf9c-d94e-4e13-b939-9e6aee653b93
--   vendedor_id 1ad074e5-d217-4031-8f72-7d321fe4df52  (Japa)
--   atualizado_em 2026-08-31T15:56:54.592552+00:00
--   status_lead 'negociando'

UPDATE leads
SET vendedor_id   = '1ad074e5-d217-4031-8f72-7d321fe4df52',
    atualizado_em = '2026-08-31T15:56:54.592552+00:00'
WHERE id = '2036bf9c-d94e-4e13-b939-9e6aee653b93';

-- Nenhuma linha foi gravada em `atividades`: a CHECK constraint
-- `atividades_tipo_check` nao aceita o tipo 'lead_reatribuido'.
-- Portanto nao ha log para remover neste rollback.
