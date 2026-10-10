-- Testes de FIX_comandos_whatsapp.sql. Rodar em Postgres descartavel, depois
-- de teste_schema_producao.sql (schema real, gerado do catalogo) e do FIX. Falha com EXCEPTION no primeiro erro.
CREATE OR REPLACE FUNCTION pg_temp.ok(c boolean, msg text) RETURNS void LANGUAGE plpgsql AS $$
BEGIN IF c IS NOT TRUE THEN RAISE EXCEPTION 'FALHOU: %', msg; END IF; END $$;

CREATE OR REPLACE FUNCTION pg_temp.eq(a text, b text, msg text) RETURNS void LANGUAGE plpgsql AS $$
BEGIN IF a IS DISTINCT FROM b THEN RAISE EXCEPTION 'FALHOU: % (obtido=%, esperado=%)', msg, a, b; END IF; END $$;

-- ---------------------------------------------------------------- normalizacao
DO $$ BEGIN
  PERFORM pg_temp.eq(normalizar_nome('João'),  'joao', 'João');
  PERFORM pg_temp.eq(normalizar_nome('Joao'),  'joao', 'Joao');
  PERFORM pg_temp.eq(normalizar_nome('JOÃO'),  'joao', 'JOÃO');
  PERFORM pg_temp.eq(normalizar_nome('joão'),  'joao', 'joão');
  PERFORM pg_temp.eq(normalizar_nome('  João  '), 'joao', 'espacos nas pontas');
  PERFORM pg_temp.eq(normalizar_nome('João   Silva'), 'joao silva', 'espacos repetidos');
  PERFORM pg_temp.eq(normalizar_nome('Ávila Çé Ñ'), 'avila ce n', 'outros acentos');
  PERFORM pg_temp.eq(normalizar_nome(E'João Silva'), 'joao silva', 'nbsp');
  PERFORM pg_temp.eq(normalizar_nome(NULL), '', 'null');
  PERFORM pg_temp.eq(length('ÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇÑáàâãäéèêëíìîïóòôõöúùûüçñ')::text, '48', 'tabela from tem 48');
  PERFORM pg_temp.eq(somente_digitos('a1b2-c3 (4)'), '1234', 'digitos');
  PERFORM pg_temp.eq(somente_digitos(NULL), '', 'digitos null');
  PERFORM pg_temp.eq(normalizar_telefone_br('19 99974-6219'),       '5519999746219', 'tel com espaco e hifen');
  PERFORM pg_temp.eq(normalizar_telefone_br('(19) 99974-6219'),     '5519999746219', 'tel parenteses');
  PERFORM pg_temp.eq(normalizar_telefone_br('+55 19 99974-6219'),   '5519999746219', 'tel +55');
  PERFORM pg_temp.eq(normalizar_telefone_br('5519999746219'),       '5519999746219', 'tel ja normalizado');
  PERFORM pg_temp.eq(normalizar_telefone_br('1999746219'),          NULL, 'tel sem o nono digito');
  PERFORM pg_temp.eq(normalizar_telefone_br('1933334444'),          NULL, 'fixo');
  PERFORM pg_temp.eq(normalizar_telefone_br('0199974621'),          NULL, 'ddd comecando com zero');
  PERFORM pg_temp.eq(normalizar_telefone_br('abc'),                 NULL, 'sem digitos');
  PERFORM pg_temp.eq(chave_telefone('551999746219'),  chave_telefone('5519999746219'), 'JID sem o 9 casa com o cadastro');
  PERFORM pg_temp.eq(formatar_telefone('5519999746219'), '(19) 99974-6219', 'formatar');
END $$;

-- ---------------------------------------------------------------- cenario
INSERT INTO lojas (id, nome, instancia_evolution) VALUES ('11111111-1111-1111-1111-111111111111', 'Loja A', 'loja-a'),
                                    ('22222222-2222-2222-2222-222222222222', 'Loja B', 'loja-b');
INSERT INTO gerentes (loja_id, nome, numero_whatsapp) VALUES
  ('11111111-1111-1111-1111-111111111111', 'Gerente A', '5519900000001'),
  ('22222222-2222-2222-2222-222222222222', 'Gerente B', '5519900000002');
INSERT INTO vendedores (id, loja_id, nome, numero_whatsapp, status, ordem_fila) VALUES
  ('a0000000-0000-0000-0000-000000000001','11111111-1111-1111-1111-111111111111','Giu',   '5519911110001','ativo',1),
  ('a0000000-0000-0000-0000-000000000002','11111111-1111-1111-1111-111111111111','Diego', '5519911110002','ativo',2),
  ('a0000000-0000-0000-0000-000000000003','11111111-1111-1111-1111-111111111111','Felipe','5519911110003','removido',3),
  ('a0000000-0000-0000-0000-000000000004','11111111-1111-1111-1111-111111111111','André', '5519911110004','inativo',4),
  ('b0000000-0000-0000-0000-000000000001','22222222-2222-2222-2222-222222222222','Beto',  '5519922220001','ativo',1);
UPDATE lojas SET proximo_vendedor_id = 'a0000000-0000-0000-0000-000000000001' WHERE id = '11111111-1111-1111-1111-111111111111';
INSERT INTO leads (loja_id, vendedor_id, nome_cliente, numero_cliente, anuncio, origem, recebido_em) VALUES
  ('11111111-1111-1111-1111-111111111111','a0000000-0000-0000-0000-000000000001','Cliente Da Giu','5519988880001','Onix','OLX', now()),
  ('11111111-1111-1111-1111-111111111111','a0000000-0000-0000-0000-000000000002','Cliente Do Diego','5519988880002','Argo','NaPista', now());

CREATE OR REPLACE FUNCTION pg_temp.cmd(loja text, rem text, txt text) RETURNS json LANGUAGE sql AS
$$ SELECT executar_comando(loja::uuid, rem, txt) $$;
CREATE OR REPLACE FUNCTION pg_temp.resp(loja text, rem text, txt text) RETURNS text LANGUAGE sql AS
$$ SELECT (executar_comando(loja::uuid, rem, txt))->>'resposta' $$;
CREATE OR REPLACE FUNCTION pg_temp.acao(loja text, rem text, txt text) RETURNS text LANGUAGE sql AS
$$ SELECT (executar_comando(loja::uuid, rem, txt))->>'acao' $$;

-- ---------------------------------------------------------------- unicidade no banco
DO $$ BEGIN
  BEGIN
    INSERT INTO vendedores (loja_id, nome, numero_whatsapp, status, ordem_fila)
    VALUES ('11111111-1111-1111-1111-111111111111', 'GIU ', '5519977770000', 'ativo', 9);
    RAISE EXCEPTION 'FALHOU: indice deveria barrar GIU duplicado';
  EXCEPTION WHEN unique_violation THEN NULL; END;
  BEGIN
    INSERT INTO vendedores (loja_id, nome, numero_whatsapp, status, ordem_fila)
    VALUES ('11111111-1111-1111-1111-111111111111', 'Outro', '551911110001', 'ativo', 9); -- JID do Giu sem o 9
    RAISE EXCEPTION 'FALHOU: indice deveria barrar telefone duplicado';
  EXCEPTION WHEN unique_violation THEN NULL; END;
  -- mesmo nome em outra loja pode
  INSERT INTO vendedores (loja_id, nome, numero_whatsapp, status, ordem_fila)
  VALUES ('22222222-2222-2222-2222-222222222222', 'Giu', '5519977770009', 'ativo', 9);
  DELETE FROM vendedores WHERE numero_whatsapp = '5519977770009';
END $$;

-- ---------------------------------------------------------------- papel e escopo
DO $$
DECLARE A text := '11111111-1111-1111-1111-111111111111'; B text := '22222222-2222-2222-2222-222222222222';
BEGIN
  PERFORM pg_temp.eq(pg_temp.acao(A, '5519955550000', 'menu'), 'ignorado', 'numero desconhecido e ignorado');
  PERFORM pg_temp.eq(pg_temp.acao(A, NULL, 'menu'), 'ignorado', 'remetente nulo');
  PERFORM pg_temp.eq(pg_temp.acao(A, '5519911110003', 'menu'), 'ignorado', 'vendedor removido nao e staff');

  -- vendedor: so o dele
  PERFORM pg_temp.ok(pg_temp.resp(A, '5519911110001', 'meus leads') LIKE '%Cliente Da Giu%', 'Giu ve o dela');
  PERFORM pg_temp.ok(pg_temp.resp(A, '5519911110001', 'meus leads') NOT LIKE '%Diego%', 'Giu NAO ve o do Diego');
  PERFORM pg_temp.ok(pg_temp.resp(A, '5519911110001', 'leads')      NOT LIKE '%Cliente Do Diego%', 'vendedor digitando leads nao ve o da loja');
  PERFORM pg_temp.ok(pg_temp.resp(A, '551911110001',  'meus leads') LIKE '%Cliente Da Giu%', 'JID sem o 9 tambem identifica');
  PERFORM pg_temp.ok(pg_temp.resp(A, '5519911110001', 'status') LIKE '%Leads recebidos: 1%', 'status do vendedor e pessoal');
  PERFORM pg_temp.eq(pg_temp.acao(A, '5519911110001', 'inserir vendedor Zeca 19 99999-8888'), 'negado', 'vendedor nao escreve');
  PERFORM pg_temp.eq(pg_temp.acao(A, '5519911110001', 'excluir Diego'), 'negado', 'vendedor nao exclui');
  PERFORM pg_temp.eq(pg_temp.acao(A, '5519911110001', 'listar vendedores'), 'negado', 'vendedor nao lista');
  PERFORM pg_temp.ok((SELECT count(*) FROM vendedores WHERE nome = 'Zeca') = 0, 'nada foi inserido pelo vendedor');
  PERFORM pg_temp.ok((SELECT status FROM vendedores WHERE nome = 'Diego') = 'ativo', 'Diego continua ativo');

  -- gerente: status/leads ficam no caminho antigo; menu proprio
  PERFORM pg_temp.eq(pg_temp.acao(A, '5519900000001', 'status'), 'legado', 'gerente status -> legado');
  PERFORM pg_temp.eq(pg_temp.acao(A, '5519900000001', 'LEADS'),  'legado', 'gerente leads -> legado');
  PERFORM pg_temp.ok(pg_temp.resp(A, '5519900000001', 'menu') LIKE '%inserir vendedor%', 'menu do gerente');
  PERFORM pg_temp.ok(pg_temp.resp(A, '5519911110001', 'menu') NOT LIKE '%inserir vendedor%', 'menu do vendedor nao oferece escrita');
  PERFORM pg_temp.eq(pg_temp.acao(A, '5519900000001', 'bla bla'), 'erro', 'comando desconhecido');
  PERFORM pg_temp.eq(pg_temp.acao(A, '5519900000001', ''), 'info', 'texto vazio vira menu');
END $$;

-- ---------------------------------------------------------------- inserir
DO $$
DECLARE A text := '11111111-1111-1111-1111-111111111111'; G text := '5519900000001'; r json;
BEGIN
  r := pg_temp.cmd(A, G, 'inserir vendedor João Silva 19 99999-8888');
  PERFORM pg_temp.eq(r->>'acao', 'eco', 'inserir solto so devolve eco');
  PERFORM pg_temp.ok((SELECT count(*) FROM vendedores WHERE nome ILIKE 'Jo%') = 0, 'eco nao grava');
  PERFORM pg_temp.ok(r->>'resposta' LIKE '%confirmar inserir vendedor João Silva 5519999998888%', 'eco traz o comando exato');

  -- o comando do eco, reenviado, executa
  r := pg_temp.cmd(A, G, 'confirmar inserir vendedor João Silva 5519999998888');
  PERFORM pg_temp.eq(r->>'acao', 'executado', 'confirmar executa');
  PERFORM pg_temp.eq((SELECT numero_whatsapp FROM vendedores WHERE nome = 'João Silva'), '5519999998888', 'telefone normalizado');
  PERFORM pg_temp.eq((SELECT status FROM vendedores WHERE nome = 'João Silva'), 'ativo', 'entra ativo');
  PERFORM pg_temp.eq((SELECT ordem_fila::text FROM vendedores WHERE nome = 'João Silva'), '5', 'fim da fila');
  PERFORM pg_temp.ok((SELECT descricao FROM atividades WHERE tipo = 'vendedor_adicionado' ORDER BY criado_em DESC LIMIT 1) LIKE '%comando de Gerente A%', 'atividade diz quem fez');

  -- nome repetido: acento, caixa, espaco
  PERFORM pg_temp.ok(pg_temp.resp(A, G, 'inserir vendedor Joao Silva 19 98888-7777') LIKE '%Já existe um vendedor chamado%', 'Joao Silva = João Silva');
  PERFORM pg_temp.ok(pg_temp.resp(A, G, 'confirmar inserir vendedor JOÃO  SILVA 5519988887777') LIKE '%Já existe%', 'confirmar tambem barra duplicado');
  PERFORM pg_temp.ok(pg_temp.resp(A, G, 'inserir vendedor giu 19 98888-7777') LIKE '%Já existe%', 'nome de vendedor ativo');
  -- nome de removido: avisa e sugere reativar
  PERFORM pg_temp.ok(pg_temp.resp(A, G, 'inserir vendedor Felipe 19 98888-7777') LIKE '%reativar Felipe%', 'removido sugere reativar');
  -- sem telefone
  PERFORM pg_temp.ok(pg_temp.resp(A, G, 'inserir vendedor Zeca') LIKE '%é preciso o telefone%', 'telefone obrigatorio');
  PERFORM pg_temp.ok(pg_temp.resp(A, G, 'inserir vendedor 19 98888-7777') LIKE '%Faltou o nome%', 'nome obrigatorio');
  PERFORM pg_temp.ok(pg_temp.resp(A, G, 'inserir vendedor Zeca 3333-4444') LIKE '%Telefone inválido%', 'telefone invalido');
  -- telefone repetido (vendedor e gerente)
  PERFORM pg_temp.ok(pg_temp.resp(A, G, 'inserir vendedor Zeca 19 91111-0001') LIKE '%já está cadastrado para *Giu*%', 'telefone de vendedor');
  PERFORM pg_temp.ok(pg_temp.resp(A, G, 'inserir vendedor Zeca 19 90000-0001') LIKE '%já está cadastrado para *Gerente A*%', 'telefone de gerente');
  PERFORM pg_temp.ok((SELECT count(*) FROM vendedores WHERE nome = 'Zeca') = 0, 'nenhum Zeca foi criado');
  -- mesma pessoa em outra loja nao conflita
  PERFORM pg_temp.eq(pg_temp.acao('22222222-2222-2222-2222-222222222222', '5519900000002', 'inserir vendedor Giu 19 91111-0001'), 'eco', 'outra loja pode ter o mesmo nome e telefone');
END $$;

-- ---------------------------------------------------------------- pausar / reativar / excluir
DO $$
DECLARE A text := '11111111-1111-1111-1111-111111111111'; G text := '5519900000001'; r json;
BEGIN
  -- eco sem executar
  r := pg_temp.cmd(A, G, 'pausar diego');
  PERFORM pg_temp.eq(r->>'acao', 'eco', 'pausar solto e eco');
  PERFORM pg_temp.eq((SELECT status FROM vendedores WHERE nome='Diego'), 'ativo', 'eco nao altera');
  PERFORM pg_temp.ok(r->>'resposta' LIKE '%confirmar pausar Diego 5519911110002%', 'eco do pausar');
  -- confirmar sem telefone ainda e eco
  PERFORM pg_temp.eq(pg_temp.acao(A, G, 'confirmar pausar Diego'), 'eco', 'confirmar sem telefone nao executa');
  PERFORM pg_temp.eq((SELECT status FROM vendedores WHERE nome='Diego'), 'ativo', 'segue ativo');
  -- telefone errado: checksum
  PERFORM pg_temp.ok(pg_temp.resp(A, G, 'confirmar pausar Diego 5519911119999') LIKE '%não confere%', 'checksum barra telefone errado');
  PERFORM pg_temp.eq((SELECT status FROM vendedores WHERE nome='Diego'), 'ativo', 'segue ativo apos checksum');
  -- nome inexistente lista os existentes
  PERFORM pg_temp.ok(pg_temp.resp(A, G, 'pausar Fulano') LIKE '%Não encontrei%Vendedores:%Giu%', 'nome inexistente');
  -- outra loja nao alcanca
  PERFORM pg_temp.ok(pg_temp.resp('22222222-2222-2222-2222-222222222222', '5519900000002', 'excluir Diego') LIKE '%Não encontrei%', 'gerente da loja B nao acha vendedor da loja A');

  -- executa pausar do Diego (Giu segue ativa, ha mais de um ativo)
  PERFORM pg_temp.eq(pg_temp.acao(A, G, 'confirmar pausar Diego 5519911110002'), 'executado', 'pausar Diego');
  PERFORM pg_temp.eq((SELECT status FROM vendedores WHERE nome='Diego'), 'inativo', 'Diego inativo');
  PERFORM pg_temp.ok(pg_temp.resp(A, G, 'pausar Diego') LIKE '%já está inativo%', 'pausar de novo');

  -- reativar inativo
  PERFORM pg_temp.eq(pg_temp.acao(A, G, 'confirmar despausar Diego 5519911110002'), 'executado', 'despausar e alias de reativar');
  PERFORM pg_temp.eq((SELECT status FROM vendedores WHERE nome='Diego'), 'ativo', 'Diego ativo de novo');
  PERFORM pg_temp.ok(pg_temp.resp(A, G, 'reativar Diego') LIKE '%já está ativo%', 'reativar ativo');

  -- ponteiro da fila: ao excluir quem esta na vez, passa para o primeiro ativo por ordem_fila
  PERFORM pg_temp.eq((SELECT proximo_vendedor_id::text FROM lojas WHERE id = A::uuid), 'a0000000-0000-0000-0000-000000000001', 'ponteiro na Giu');
  PERFORM pg_temp.eq(pg_temp.acao(A, G, 'confirmar excluir vendedor Giu 5519911110001'), 'executado', 'excluir Giu');
  PERFORM pg_temp.eq((SELECT status FROM vendedores WHERE nome='Giu'), 'removido', 'Giu removida');
  PERFORM pg_temp.eq((SELECT proximo_vendedor_id::text FROM lojas WHERE id = A::uuid), 'a0000000-0000-0000-0000-000000000002', 'ponteiro foi para Diego');
  PERFORM pg_temp.ok((SELECT count(*) FROM leads WHERE vendedor_id = 'a0000000-0000-0000-0000-000000000001') = 1, 'historico de leads da Giu mantido');

  -- protecao do ultimo ativo: ativos agora = Diego e João Silva
  PERFORM pg_temp.eq(pg_temp.acao(A, G, 'confirmar excluir Diego 5519911110002'), 'executado', 'ainda sobra João Silva');
  PERFORM pg_temp.ok(pg_temp.resp(A, G, 'excluir João Silva') LIKE '%único vendedor ativo%', 'ultimo ativo protegido (excluir)');
  PERFORM pg_temp.ok(pg_temp.resp(A, G, 'pausar João Silva') LIKE '%único vendedor ativo%', 'ultimo ativo protegido (pausar)');
  PERFORM pg_temp.eq((SELECT status FROM vendedores WHERE nome='João Silva'), 'ativo', 'João Silva segue ativo');

  -- reativar removido
  PERFORM pg_temp.eq(pg_temp.acao(A, G, 'confirmar reativar Felipe 5519911110003'), 'executado', 'reativar removido');
  PERFORM pg_temp.eq((SELECT status FROM vendedores WHERE nome='Felipe'), 'ativo', 'Felipe voltou');
  -- reativar removido cujo telefone foi tomado por outro
  UPDATE vendedores SET status='removido' WHERE nome='Giu';
  -- em producao o mesmo texto e barrado por uk_vendedores_loja_whatsapp; o caso
  -- real e o mesmo numero sem o nono digito (JID antigo)
  UPDATE vendedores SET numero_whatsapp='551911110001' WHERE nome='André';
  PERFORM pg_temp.ok(pg_temp.resp(A, G, 'reativar Giu') LIKE '%já é de *André*%', 'telefone tomado impede reativar');

  -- atividades tipadas
  PERFORM pg_temp.ok((SELECT count(*) FROM atividades WHERE tipo='vendedor_inativado')  >= 1, 'atividade inativado');
  PERFORM pg_temp.ok((SELECT count(*) FROM atividades WHERE tipo='vendedor_reativado')  >= 2, 'atividade reativado');
  PERFORM pg_temp.ok((SELECT count(*) FROM atividades WHERE tipo='vendedor_removido')   >= 2, 'atividade removido');
END $$;

-- ---------------------------------------------------------------- listar e gerente-vendedor
DO $$
DECLARE A text := '11111111-1111-1111-1111-111111111111'; G text := '5519900000001';
BEGIN
  PERFORM pg_temp.ok(pg_temp.resp(A, G, 'listar vendedores') LIKE '%João Silva — ativo — (19) 99999-8888%', 'listar mostra telefone formatado');
  PERFORM pg_temp.ok(pg_temp.resp(A, G, 'listar vendedores') LIKE '%removido(s) não aparecem%', 'listar conta removidos');
  -- gerente que tambem e vendedor
  INSERT INTO gerentes (loja_id, nome, numero_whatsapp) VALUES (A::uuid, 'Dono Vende', '5519911110001');
  PERFORM pg_temp.eq(pg_temp.acao(A, '5519911110001', 'status'), 'legado', 'gerente-vendedor: status segue o legado');
  PERFORM pg_temp.ok(pg_temp.resp(A, '5519911110001', 'meus leads') LIKE '%Nenhum lead seu%', 'gerente-vendedor: meus leads usa a linha de vendedor');
END $$;

-- ---------------------------------------------------------------- permissoes
DO $$
BEGIN
  SET LOCAL ROLE anon;
  BEGIN
    PERFORM executar_comando('11111111-1111-1111-1111-111111111111', '5519900000001', 'menu');
    RAISE EXCEPTION 'FALHOU: anon executou executar_comando';
  EXCEPTION WHEN insufficient_privilege THEN NULL; END;
  RESET ROLE;
  SET LOCAL ROLE authenticated;
  BEGIN
    PERFORM executar_comando('11111111-1111-1111-1111-111111111111', '5519900000001', 'menu');
    RAISE EXCEPTION 'FALHOU: authenticated executou executar_comando';
  EXCEPTION WHEN insufficient_privilege THEN NULL; END;
  RESET ROLE;
  SET LOCAL ROLE service_role;
  PERFORM executar_comando('11111111-1111-1111-1111-111111111111', '5519900000001', 'menu');
  RESET ROLE;
END $$;

-- ---------------------------------------------------------------- telefone de removido
-- Em producao uk_vendedores_loja_whatsapp vale tambem para removidos. O inserir
-- tem de avisar ja no eco, e nao falhar so na confirmacao.
DO $$
DECLARE A text := '11111111-1111-1111-1111-111111111111'; G text := '5519900000001'; r text;
BEGIN
  INSERT INTO vendedores (loja_id, nome, numero_whatsapp, status, ordem_fila)
  VALUES (A::uuid, 'Silas', '5519911110005', 'removido', 50);
  r := pg_temp.resp(A, G, 'inserir vendedor Novato 19 91111-0005');
  PERFORM pg_temp.ok(r LIKE '%Silas%' AND r LIKE '%reativar Silas%', 'telefone de removido avisa no eco: ' || r);
  PERFORM pg_temp.eq(pg_temp.acao(A, G, 'confirmar inserir vendedor Novato 5519911110005'), 'erro', 'confirmar tambem recusa');
  PERFORM pg_temp.ok(NOT EXISTS (SELECT 1 FROM vendedores WHERE nome = 'Novato'), 'Novato nao foi inserido');
END $$;

-- ---------------------------------------------------------------- confirmacao por "sim"
DO $$
DECLARE A text := '11111111-1111-1111-1111-111111111111'; G text := '5519900000001'; r json; n int;
BEGIN
  DELETE FROM comandos_pendentes;
  -- sim sem nada pendente
  PERFORM pg_temp.ok(pg_temp.resp(A, G, 'sim') LIKE '%Não há nada aguardando%', 'sim sem pendencia');

  -- eco guarda pendencia; "Sim!" (maiuscula, pontuacao) executa
  r := pg_temp.cmd(A, G, 'inserir vendedor Paula 19 97777-0001');
  PERFORM pg_temp.eq(r->>'acao', 'eco', 'inserir da eco');
  PERFORM pg_temp.ok(r->>'resposta' LIKE '%responda *sim*%', 'eco pede sim');
  PERFORM pg_temp.eq((SELECT count(*) FROM comandos_pendentes)::text, '1', 'pendencia criada');
  PERFORM pg_temp.ok(NOT EXISTS (SELECT 1 FROM vendedores WHERE nome = 'Paula'), 'eco nao insere');
  r := pg_temp.cmd(A, G, 'Sim!');
  PERFORM pg_temp.eq(r->>'acao', 'executado', 'sim executa');
  PERFORM pg_temp.ok(EXISTS (SELECT 1 FROM vendedores WHERE nome = 'Paula' AND status = 'ativo'), 'Paula inserida');
  PERFORM pg_temp.eq((SELECT count(*) FROM comandos_pendentes)::text, '0', 'pendencia consumida');
  -- segundo sim nao repete
  PERFORM pg_temp.ok(pg_temp.resp(A, G, 'sim') LIKE '%Não há nada aguardando%', 'sim nao executa duas vezes');

  -- nao cancela
  PERFORM pg_temp.eq(pg_temp.acao(A, G, 'pausar Paula'), 'eco', 'pausar eco');
  PERFORM pg_temp.eq(pg_temp.acao(A, G, 'não'), 'cancelado', 'nao cancela');
  PERFORM pg_temp.eq((SELECT status FROM vendedores WHERE nome = 'Paula'), 'ativo', 'cancelado nao pausa');

  -- outra mensagem descarta a pendencia
  PERFORM pg_temp.eq(pg_temp.acao(A, G, 'pausar Paula'), 'eco', 'pausar eco 2');
  PERFORM pg_temp.eq(pg_temp.acao(A, G, 'listar vendedores'), 'info', 'troca de assunto');
  PERFORM pg_temp.ok(pg_temp.resp(A, G, 'pode') LIKE '%Não há nada aguardando%', 'pendencia descartada');
  PERFORM pg_temp.eq((SELECT status FROM vendedores WHERE nome = 'Paula'), 'ativo', 'descartado nao pausa');

  -- expirada nao executa
  PERFORM pg_temp.eq(pg_temp.acao(A, G, 'excluir vendedor Paula'), 'eco', 'excluir eco');
  UPDATE comandos_pendentes SET expira_em = now() - interval '1 second';
  PERFORM pg_temp.ok(pg_temp.resp(A, G, 'confirma') LIKE '%expirou%', 'expirada avisa');
  PERFORM pg_temp.eq((SELECT status FROM vendedores WHERE nome = 'Paula'), 'ativo', 'expirada nao exclui');

  -- pendencia e por pessoa: outro gerente nao confirma a minha
  INSERT INTO gerentes (loja_id, nome, numero_whatsapp) VALUES (A::uuid, 'Gerente A2', '5519900000003');
  PERFORM pg_temp.eq(pg_temp.acao(A, G, 'pausar Paula'), 'eco', 'pausar eco 3');
  PERFORM pg_temp.ok(pg_temp.resp(A, '5519900000003', 'sim') LIKE '%Não há nada aguardando%', 'outro gerente nao confirma');
  PERFORM pg_temp.eq((SELECT status FROM vendedores WHERE nome = 'Paula'), 'ativo', 'ainda ativa');
  -- e a pendencia e por loja: o mesmo numero em outra loja nao enxerga
  PERFORM pg_temp.eq(pg_temp.acao('22222222-2222-2222-2222-222222222222', G, 'sim'), 'ignorado', 'outra loja ignora');
  -- confirmacao exata antiga continua valendo
  r := pg_temp.cmd(A, G, 'confirmar pausar Paula 5519977770001');
  PERFORM pg_temp.eq(r->>'acao', 'executado', 'confirmar exato ainda funciona');
  PERFORM pg_temp.eq((SELECT status FROM vendedores WHERE nome = 'Paula'), 'inativo', 'Paula pausada');

  -- estado mudou entre o eco e o sim: a base revalida
  PERFORM pg_temp.eq(pg_temp.acao(A, G, 'reativar Paula'), 'eco', 'reativar eco');
  UPDATE vendedores SET status = 'ativo' WHERE nome = 'Paula';
  PERFORM pg_temp.ok(pg_temp.resp(A, G, 'sim') LIKE '%já está ativo%', 'revalida no sim');

  -- vendedor: "sim" nao tem o que confirmar, e cliente desconhecido e ignorado
  PERFORM pg_temp.ok(pg_temp.resp(A, '5519911110001', 'sim') LIKE '%Não há nada aguardando%', 'vendedor sim');
  PERFORM pg_temp.eq(pg_temp.acao(A, '5519955550000', 'sim'), 'ignorado', 'desconhecido ignorado');

  -- quem nao e service_role nao le nem escreve pendencias
  SET LOCAL ROLE anon;
  BEGIN
    PERFORM 1 FROM comandos_pendentes;
    RAISE EXCEPTION 'FALHOU: anon leu comandos_pendentes';
  EXCEPTION WHEN insufficient_privilege THEN NULL; END;
  RESET ROLE;
  DELETE FROM vendedores WHERE nome = 'Paula';
  DELETE FROM gerentes WHERE nome = 'Gerente A2';
END $$;

-- ---------------------------------------------------------------- camada de IA (travas)
DO $$
DECLARE A text := '11111111-1111-1111-1111-111111111111'; G text := '5519900000001'; r json; st text;
BEGIN
  DELETE FROM comandos_pendentes;
  -- sugestao boa e usada
  r := executar_comando_ia(A::uuid, G, 'me mostra a turma ai', 'listar vendedores');
  PERFORM pg_temp.eq(r->>'ia', 'sugestao_usada', 'sugestao boa usada');
  PERFORM pg_temp.eq(r->>'acao', 'info', 'listar via IA');
  -- sem sugestao (IA caiu): texto original, igual a sem IA
  r := executar_comando_ia(A::uuid, G, 'listar vendedores', NULL);
  PERFORM pg_temp.eq(r->>'ia', 'sem_sugestao', 'sem sugestao');
  PERFORM pg_temp.eq(r->>'acao', 'info', 'original funciona');
  -- verbo fora do vocabulario: descartado
  r := executar_comando_ia(A::uuid, G, 'apaga tudo', 'drop table vendedores');
  PERFORM pg_temp.eq(r->>'ia', 'verbo_desconhecido', 'verbo desconhecido');
  PERFORM pg_temp.eq(r->>'interpretado', 'apaga tudo', 'usa o original');
  -- IA nao pode confirmar sozinha
  st := (SELECT status FROM vendedores WHERE nome = 'Diego');
  r := executar_comando_ia(A::uuid, G, 'pausa o diego', 'confirmar pausar Diego 5519911110002');
  PERFORM pg_temp.eq(r->>'ia', 'verbo_desconhecido', 'confirmar vindo da IA e barrado');
  PERFORM pg_temp.eq((SELECT status FROM vendedores WHERE nome = 'Diego'), st, 'Diego nao mudou');
  -- telefone inventado: descartado
  r := executar_comando_ia(A::uuid, G, 'coloca o Beto na fila', 'inserir vendedor Beto 19 98888-1234');
  PERFORM pg_temp.eq(r->>'ia', 'telefone_inventado', 'telefone inventado barrado');
  PERFORM pg_temp.ok(NOT EXISTS (SELECT 1 FROM comandos_pendentes), 'nada pendente');
  -- telefone que esta no texto: aceito (com ou sem 55, com mascara)
  r := executar_comando_ia(A::uuid, G, 'bota o Beto, numero (19) 98888-1234', 'inserir vendedor Beto 19988881234');
  PERFORM pg_temp.eq(r->>'ia', 'sugestao_usada', 'telefone literal aceito');
  PERFORM pg_temp.eq(r->>'acao', 'eco', 'inserir via IA so faz eco');
  PERFORM pg_temp.ok(NOT EXISTS (SELECT 1 FROM vendedores WHERE nome = 'Beto' AND loja_id = A::uuid), 'eco nao insere');
  r := executar_comando_ia(A::uuid, G, 'pode', 'sim');
  PERFORM pg_temp.eq(r->>'acao', 'executado', 'sim via IA executa a pendencia');
  PERFORM pg_temp.ok(EXISTS (SELECT 1 FROM vendedores WHERE nome = 'Beto' AND loja_id = A::uuid), 'Beto inserido');
  -- vendedor continua sem poder escrever, com ou sem IA
  INSERT INTO vendedores (loja_id, nome, numero_whatsapp, status, ordem_fila) VALUES (A::uuid, 'Vend IA', '5519966660001', 'ativo', 60);
  r := executar_comando_ia(A::uuid, '5519966660001', 'tira o diego da fila', 'excluir vendedor Diego');
  PERFORM pg_temp.eq(r->>'acao', 'negado', 'vendedor negado via IA');
  DELETE FROM vendedores WHERE nome = 'Vend IA';
  -- cliente desconhecido continua ignorado
  r := executar_comando_ia(A::uuid, '5519955550000', 'oi', 'menu');
  PERFORM pg_temp.eq(r->>'acao', 'ignorado', 'desconhecido ignorado via IA');
  DELETE FROM vendedores WHERE nome = 'Beto' AND loja_id = A::uuid;
END $$;

DO $$
BEGIN
  SET LOCAL ROLE anon;
  BEGIN
    PERFORM executar_comando_ia('11111111-1111-1111-1111-111111111111', '5519900000001', 'menu', 'menu');
    RAISE EXCEPTION 'FALHOU: anon executou executar_comando_ia';
  EXCEPTION WHEN insufficient_privilege THEN NULL; END;
  RESET ROLE;
END $$;

SELECT 'TODOS OS TESTES PASSARAM' AS resultado;
