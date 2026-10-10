-- Fase B — prova de isolamento entre lojas, CONTRA O BANCO DE PRODUCAO.
--
-- Roda tudo dentro de um unico bloco DO que SEMPRE termina com RAISE
-- EXCEPTION: passe ou falhe, a transacao inteira e desfeita. Nada criado aqui
-- (loja de teste, vendedores, leads, atividades, pendencias, contadores de IA)
-- sobra no banco. A Renato Motors so e lida, e o estado dela e comparado no
-- fim com o do comeco.
--
-- Resultado vem na mensagem do erro:
--   FASEB_OK    {...}   todas as verificacoes passaram
--   FASEB_FALHOU <qual> uma verificacao falhou (e tudo foi desfeito igual)
--
-- Uso: sql/fase_b/rodar_teste_isolamento.py (troca :LOJA_REAL pelo LOJA_ID do .env)

DO $$
DECLARE
  RM   uuid := ':LOJA_REAL';
  T    uuid;
  ELTON text := '5519996977453';        -- gerente da Renato Motors; vira gerente da loja T tambem
  T1 text := '5511911111111'; T2 text := '5511922222222'; TGIU text := '5511933333334';
  r json; rr record; n int; s text;
  rm_prox uuid; rm_leads int; rm_ativ int; rm_vend text; rm_ia int; rm_pend int;
  rm_cliente text; vt uuid[]; nomes text[] := '{}';
  checks int := 0;
BEGIN
  -- ---------------------------------------------------------------- foto da Renato Motors
  SELECT proximo_vendedor_id INTO rm_prox FROM lojas WHERE id = RM;
  SELECT count(*) INTO rm_leads FROM leads WHERE loja_id = RM;
  SELECT count(*) INTO rm_ativ FROM atividades WHERE loja_id = RM;
  SELECT string_agg(nome || ':' || status, ',' ORDER BY nome) INTO rm_vend FROM vendedores WHERE loja_id = RM;
  SELECT coalesce(sum(chamadas), 0) INTO rm_ia FROM ia_uso WHERE loja_id = RM;
  SELECT count(*) INTO rm_pend FROM comandos_pendentes WHERE loja_id = RM;
  IF rm_prox IS NULL THEN RAISE EXCEPTION 'FASEB_FALHOU loja real sem ponteiro de fila (LOJA_ID certo?)'; END IF;

  -- ---------------------------------------------------------------- loja T
  INSERT INTO lojas (nome, numero_whatsapp, instancia_evolution, ativa)
  VALUES ('Loja Teste Isolamento', '5511900000000', 'teste-isolamento-faseb', true) RETURNING id INTO T;
  -- criado_em distintos: o rodizio real ordena por criado_em, e dentro de uma
  -- transacao now() e o mesmo para todos (na vida real cada um e cadastrado num momento)
  INSERT INTO vendedores (loja_id, nome, numero_whatsapp, status, ordem_fila, criado_em) VALUES
    (T, 'Vendedor T1', T1, 'ativo', 1, now() - interval '3 minutes'),
    (T, 'Vendedor T2', T2, 'ativo', 2, now() - interval '2 minutes'),
    (T, 'Giu', TGIU, 'ativo', 3, now() - interval '1 minute');   -- mesmo nome de uma vendedora real, outra loja
  INSERT INTO gerentes (loja_id, nome, numero_whatsapp, ativo) VALUES (T, 'Elton', ELTON, true);
  SELECT array_agg(id) INTO vt FROM vendedores WHERE loja_id = T;
  checks := checks + 1;  -- mesmo telefone de gerente e mesmo nome de vendedor em duas lojas: aceito

  -- ---------------------------------------------------------------- 1. distribuicao fica na loja T
  FOR n IN 1..6 LOOP
    SELECT * INTO rr FROM distribuir_lead(T, '551194444444' || n, 'Cliente T' || n, 'Anuncio T', 'oi', now(), 'WhatsApp Direto');
    IF NOT (rr.vendedor_id = ANY (vt)) THEN RAISE EXCEPTION 'FASEB_FALHOU lead da loja T foi para vendedor de fora: %', rr.vendedor_nome; END IF;
    nomes := nomes || rr.vendedor_nome::text;
  END LOOP;
  IF (SELECT count(DISTINCT x) FROM unnest(nomes) x) <> 3 THEN
    RAISE EXCEPTION 'FASEB_FALHOU rodizio da loja T nao passou pelos 3 vendedores: %', nomes;
  END IF;
  checks := checks + 2;

  -- cliente que ja e da Renato Motors escreve para a loja T: NAO pode amarrar no vendedor da RM
  SELECT l.numero_cliente INTO rm_cliente FROM leads l JOIN vendedores v ON v.id = l.vendedor_id
   WHERE l.loja_id = RM AND v.status = 'ativo' ORDER BY l.criado_em DESC LIMIT 1;
  SELECT * INTO rr FROM distribuir_lead(T, rm_cliente, 'Cliente da RM', 'Outro carro', 'oi', now(), 'WhatsApp Direto');
  IF NOT (rr.vendedor_id = ANY (vt)) THEN RAISE EXCEPTION 'FASEB_FALHOU cliente da RM amarrou em vendedor da RM pela loja T'; END IF;
  checks := checks + 1;

  -- ---------------------------------------------------------------- 2. identificacao de quem manda e por loja
  IF (identificar_remetente('teste-isolamento-faseb', ELTON)->>'loja_id')::uuid IS DISTINCT FROM T
     OR (identificar_remetente('renato-motors', ELTON)->>'loja_id')::uuid IS DISTINCT FROM RM THEN
    RAISE EXCEPTION 'FASEB_FALHOU identificar_remetente misturou as lojas';
  END IF;
  IF identificar_remetente('teste-isolamento-faseb', T1)->>'papel' <> 'vendedor'
     OR identificar_remetente('renato-motors', T1)->>'papel' <> 'lead' THEN
    RAISE EXCEPTION 'FASEB_FALHOU vendedor da loja T reconhecido na RM (ou vice-versa)';
  END IF;
  checks := checks + 2;

  -- ---------------------------------------------------------------- 3. comandos do gerente: so a propria loja
  s := executar_comando(T, ELTON, 'listar vendedores')->>'resposta';
  IF s NOT LIKE '%Vendedor T1%' OR s LIKE '%Japa%' OR s LIKE '%Diego%' THEN
    RAISE EXCEPTION 'FASEB_FALHOU listar na loja T mostrou outra loja: %', s;
  END IF;
  s := executar_comando(RM, ELTON, 'listar vendedores')->>'resposta';
  IF s NOT LIKE '%Japa%' OR s LIKE '%Vendedor T%' THEN
    RAISE EXCEPTION 'FASEB_FALHOU listar na RM mostrou a loja T: %', s;
  END IF;
  IF executar_comando(T, ELTON, 'pausar Japa')->>'resposta' NOT LIKE 'Não encontrei%' THEN
    RAISE EXCEPTION 'FASEB_FALHOU gerente da loja T achou vendedor da RM';
  END IF;
  checks := checks + 3;

  -- "pausar Giu" na loja T pega a Giu DA LOJA T (telefone dela), e a pendencia e por loja
  r := executar_comando(T, ELTON, 'pausar Giu');
  IF r->>'acao' <> 'eco' OR r->>'resposta' NOT LIKE '%(11) 93333-3334%' THEN
    RAISE EXCEPTION 'FASEB_FALHOU pausar Giu na loja T nao mirou a Giu da loja T: %', r->>'resposta';
  END IF;
  IF executar_comando(RM, ELTON, 'sim')->>'resposta' NOT LIKE 'Não há nada aguardando%' THEN
    RAISE EXCEPTION 'FASEB_FALHOU "sim" na RM confirmou pendencia da loja T';
  END IF;
  -- o "sim" na RM descartou? nao: "sim" sem pendencia nao apaga a da outra loja
  IF NOT EXISTS (SELECT 1 FROM comandos_pendentes WHERE loja_id = T) THEN
    RAISE EXCEPTION 'FASEB_FALHOU pendencia da loja T sumiu com mensagem enviada para a RM';
  END IF;
  r := executar_comando(T, ELTON, 'sim');
  IF r->>'acao' <> 'executado' THEN RAISE EXCEPTION 'FASEB_FALHOU sim na loja T: %', r; END IF;
  IF (SELECT status FROM vendedores WHERE loja_id = T AND nome = 'Giu') <> 'inativo'
     OR (SELECT status FROM vendedores WHERE loja_id = RM AND nome = 'Giu') <> 'ativo' THEN
    RAISE EXCEPTION 'FASEB_FALHOU pausar Giu na loja T afetou a Giu da RM';
  END IF;
  checks := checks + 4;

  -- ---------------------------------------------------------------- 4. vendedor: so os proprios leads, so na propria loja
  -- a resposta traz "(ultimos 3 dias): N"; N tem de ser exatamente os leads do T1 na loja T
  s := executar_comando(T, T1, 'meus leads')->>'resposta';
  SELECT count(*) INTO n FROM leads l JOIN vendedores v ON v.id = l.vendedor_id
   WHERE l.loja_id = T AND v.numero_whatsapp = T1;
  IF n = 0 OR s NOT LIKE '%(últimos 3 dias): ' || n || '%' THEN
    RAISE EXCEPTION 'FASEB_FALHOU meus leads do vendedor T1 (esperava %): %', n, s;
  END IF;
  IF executar_comando(RM, T1, 'meus leads')->>'acao' <> 'ignorado' THEN
    RAISE EXCEPTION 'FASEB_FALHOU vendedor da loja T falou com a RM';
  END IF;
  SELECT numero_whatsapp INTO s FROM vendedores WHERE loja_id = RM AND nome = 'Japa';
  IF executar_comando(T, s, 'meus leads')->>'acao' <> 'ignorado' THEN
    RAISE EXCEPTION 'FASEB_FALHOU vendedor da RM falou com a loja T';
  END IF;
  checks := checks + 3;

  -- ---------------------------------------------------------------- 5. leitura legada do gerente (status/leads)
  IF (comando_status(T)::json->>'total_leads')::int <> 7 THEN
    RAISE EXCEPTION 'FASEB_FALHOU comando_status da loja T: %', comando_status(T);
  END IF;
  s := comando_leads(T)::text;
  SELECT nome_cliente INTO rm_cliente FROM leads WHERE loja_id = RM AND coalesce(nome_cliente, '') <> ''
   ORDER BY criado_em DESC LIMIT 1;
  IF s NOT LIKE '%Cliente T%' OR s LIKE '%' || rm_cliente || '%' THEN
    RAISE EXCEPTION 'FASEB_FALHOU comando_leads da loja T (nao achou T, ou achou "%" da RM): %', rm_cliente, left(s, 300);
  END IF;
  checks := checks + 2;

  -- ---------------------------------------------------------------- 6. limite de IA por loja
  PERFORM reservar_ia(T, ELTON, 'me mostra a equipe');
  IF (SELECT chamadas FROM ia_uso WHERE loja_id = T AND remetente_chave = chave_telefone(ELTON)) <> 1 THEN
    RAISE EXCEPTION 'FASEB_FALHOU contador de IA da loja T';
  END IF;
  checks := checks + 1;

  -- ---------------------------------------------------------------- 7. nada vazou para a Renato Motors
  IF (SELECT proximo_vendedor_id FROM lojas WHERE id = RM) IS DISTINCT FROM rm_prox THEN
    RAISE EXCEPTION 'FASEB_FALHOU ponteiro da fila da RM mudou'; END IF;
  IF (SELECT count(*) FROM leads WHERE loja_id = RM) <> rm_leads THEN
    RAISE EXCEPTION 'FASEB_FALHOU leads da RM mudaram'; END IF;
  IF (SELECT count(*) FROM atividades WHERE loja_id = RM) <> rm_ativ THEN
    RAISE EXCEPTION 'FASEB_FALHOU atividades da RM mudaram'; END IF;
  IF (SELECT string_agg(nome || ':' || status, ',' ORDER BY nome) FROM vendedores WHERE loja_id = RM) <> rm_vend THEN
    RAISE EXCEPTION 'FASEB_FALHOU vendedores da RM mudaram'; END IF;
  IF (SELECT coalesce(sum(chamadas), 0) FROM ia_uso WHERE loja_id = RM) <> rm_ia THEN
    RAISE EXCEPTION 'FASEB_FALHOU contador de IA da RM mudou'; END IF;
  IF (SELECT count(*) FROM comandos_pendentes WHERE loja_id = RM) <> rm_pend THEN
    RAISE EXCEPTION 'FASEB_FALHOU pendencias da RM mudaram'; END IF;
  IF EXISTS (SELECT 1 FROM leads l JOIN vendedores v ON v.id = l.vendedor_id WHERE l.loja_id <> v.loja_id) THEN
    RAISE EXCEPTION 'FASEB_FALHOU existe lead com vendedor de outra loja (em todo o banco)'; END IF;
  IF EXISTS (SELECT 1 FROM atividades WHERE loja_id = T AND descricao ILIKE ANY (ARRAY['%Japa%', '%Diego%'])) THEN
    RAISE EXCEPTION 'FASEB_FALHOU atividade da loja T cita vendedor da RM'; END IF;
  checks := checks + 7;

  RAISE EXCEPTION 'FASEB_OK %', json_build_object(
    'verificacoes', checks,
    'rodizio_loja_T', nomes,
    'leads_loja_T', (SELECT count(*) FROM leads WHERE loja_id = T),
    'atividades_loja_T', (SELECT count(*) FROM atividades WHERE loja_id = T),
    'rm_intacta', json_build_object('leads', rm_leads, 'atividades', rm_ativ, 'ponteiro', rm_prox));
END $$;
