-- Testes de FIX_portaria_sombra.sql. Rodar em Postgres descartavel depois de
-- ../comandos_whatsapp/teste_schema_producao.sql, ../comandos_whatsapp/FIX_comandos_whatsapp.sql e do FIX.
CREATE OR REPLACE FUNCTION pg_temp.eq(a text, b text, msg text) RETURNS void LANGUAGE plpgsql AS $$
BEGIN IF a IS DISTINCT FROM b THEN RAISE EXCEPTION 'FALHOU: % (obtido=%, esperado=%)', msg, a, b; END IF; END $$;

INSERT INTO lojas (id, nome, instancia_evolution) VALUES ('11111111-1111-1111-1111-111111111111', 'Loja A', 'loja-a'),
                                                         ('22222222-2222-2222-2222-222222222222', 'Loja B', 'loja-b');
INSERT INTO gerentes (loja_id, nome, numero_whatsapp) VALUES ('11111111-1111-1111-1111-111111111111', 'Ger', '5519900000001');
INSERT INTO vendedores (id, loja_id, nome, numero_whatsapp, status, ordem_fila) VALUES
  ('a0000000-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111', 'Ven', '5519911110001', 'ativo', 1);
INSERT INTO leads (loja_id, vendedor_id, nome_cliente, numero_cliente, recebido_em, criado_em) VALUES
  ('11111111-1111-1111-1111-111111111111', 'a0000000-0000-0000-0000-000000000001', 'Antigo', '5519988880001', now() - interval '3 days', now() - interval '3 days'),
  ('11111111-1111-1111-1111-111111111111', 'a0000000-0000-0000-0000-000000000001', 'Agora',  '5519988880002', now(), now());

DO $$
DECLARE A uuid := '11111111-1111-1111-1111-111111111111'; B uuid := '22222222-2222-2222-2222-222222222222'; r json;
BEGIN
  PERFORM pg_temp.eq(portaria_sombra_preparar(A, '5519977770001', 'tem o onix?')->>'motivo', 'numero_novo', 'numero novo usa IA');
  PERFORM pg_temp.eq(portaria_sombra_preparar(A, '5519988880001', 'oi de novo')->>'motivo', 'numero_conhecido', 'cliente antigo nao passa');
  PERFORM pg_temp.eq(portaria_sombra_preparar(A, '5519988880002', 'oi')->>'motivo', 'numero_novo', 'lead desta mesma mensagem (recente) nao conta');
  PERFORM pg_temp.eq(portaria_sombra_preparar(B, '5519988880001', 'oi')->>'motivo', 'numero_novo', 'cliente da loja A e novo na loja B');
  PERFORM pg_temp.eq(portaria_sombra_preparar(A, '5519977770001', '')->>'motivo', 'sem_texto', 'audio/foto nao passa');
  PERFORM pg_temp.eq(portaria_sombra_preparar(A, '551131361712', 'Novo lead NaPista')->>'motivo', 'plataforma', 'NaPista nao passa');
  PERFORM pg_temp.eq(portaria_sombra_preparar(A, '5519900000001', 'menu')->>'motivo', 'equipe', 'gerente nao passa');
  PERFORM pg_temp.eq(portaria_sombra_preparar(A, '551911110001', 'oi')->>'motivo', 'equipe', 'vendedor (JID sem 9) nao passa');
  -- limite diario por loja
  DELETE FROM ia_uso;
  PERFORM portaria_sombra_preparar(A, '5519977770002', 'x', 2);
  PERFORM portaria_sombra_preparar(A, '5519977770003', 'x', 2);
  PERFORM pg_temp.eq(portaria_sombra_preparar(A, '5519977770004', 'x', 2)->>'motivo', 'limite_diario', 'limite por loja');
  PERFORM pg_temp.eq(portaria_sombra_preparar(B, '5519977770004', 'x', 2)->>'usar', 'true', 'limite e por loja');
  PERFORM pg_temp.eq((SELECT count(*) FROM ia_uso WHERE remetente_chave <> 'portaria')::text, '0', 'contador separado dos comandos');

  -- registrar + travas
  r := registrar_portaria_sombra(A, '5519977770001', 'X1', 'Seu boleto encontra-se em aberto', 'nao_lead', 'cobranca', 'boleto encontra-se em aberto', 'm');
  PERFORM pg_temp.eq(r->>'decisao', 'ignorar', 'nao_lead literal -> ignorar');
  r := registrar_portaria_sombra(A, '5519977770001', 'X2', 'Seu boleto encontra-se em aberto', 'nao_lead', 'cobranca', 'boleto em aberto', 'm');
  PERFORM pg_temp.eq(r->>'decisao', 'distribuir', 'parafrase -> duvida -> distribuir');
  PERFORM pg_temp.eq(r->>'trava', 'evidencia_nao_literal', 'trava registrada');
  r := registrar_portaria_sombra(A, '5519977770001', 'X3', 'oi', 'lead_novo', 'x', '', 'm');
  PERFORM pg_temp.eq(r->>'classificacao', 'duvida', 'classificacao invalida -> duvida');
  r := registrar_portaria_sombra(A, '5519977770001', 'X4', 'oi', NULL, NULL, NULL, 'm');
  PERFORM pg_temp.eq(r->>'decisao', 'distribuir', 'IA sem resposta -> distribuir');
  PERFORM pg_temp.eq((SELECT count(*) FROM portaria_sombra)::text, '4', '4 registros');
  PERFORM pg_temp.eq((SELECT count(*) FROM leads)::text, '2', 'sombra nao cria nem apaga lead');
END $$;

DO $$
BEGIN
  SET LOCAL ROLE anon;
  BEGIN
    PERFORM portaria_sombra_preparar('11111111-1111-1111-1111-111111111111', '5519977770001', 'x');
    RAISE EXCEPTION 'FALHOU: anon executou portaria_sombra_preparar';
  EXCEPTION WHEN insufficient_privilege THEN NULL; END;
  BEGIN
    PERFORM 1 FROM portaria_sombra;
    RAISE EXCEPTION 'FALHOU: anon leu portaria_sombra';
  EXCEPTION WHEN insufficient_privilege THEN NULL; END;
  RESET ROLE;
END $$;

SELECT 'TODOS OS TESTES PASSARAM' AS resultado;
