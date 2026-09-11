-- Recria o 2º lead do Levi S., caso a exclusão precise ser desfeita.
-- Linha capturada em 2026-08-31 antes do DELETE.
-- Nenhuma outra tabela referencia `leads` (zero foreign keys apontando
-- para ela), então o DELETE não teve efeito cascata.

INSERT INTO leads (
  id, loja_id, vendedor_id, numero_cliente, nome_cliente, anuncio,
  mensagem_original, recebido_em, distribuido_em, criado_em,
  status_lead, atualizado_em, origem
) VALUES (
  '2036bf9c-d94e-4e13-b939-9e6aee653b93',
  '<LOJA_ID>',
  '77b0e908-97c1-4c4c-92fe-c5d604d6d6d6',   -- André (já reatribuído; original era Japa 1ad074e5-d217-4031-8f72-7d321fe4df52)
  '5519XXXXXXXXX',
  'Levi S.',
  '',
  'Me chamo Levi',
  '2026-08-31T15:56:51+00:00',
  '2026-08-31T15:56:54.592552+00:00',
  '2026-08-31T15:56:54.592552+00:00',
  'negociando',
  '2026-08-31T20:27:53.506455+00:00',
  'WhatsApp Direto'
);
