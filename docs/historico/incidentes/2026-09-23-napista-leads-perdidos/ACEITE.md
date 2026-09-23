# Critérios de aceite e checklist

Cada item tem um critério objetivo, o comando que prova, e o resultado esperado. Um item só é marcado quando o comando foi rodado e devolveu o esperado — não por inspeção visual.

Pré-requisito para todo comando: `export N8N_KEY=<chave da Public API do n8n>`.

Comando de conferência, usado em vários critérios (lista execuções e diz se cada uma virou lead):

```bash
curl -s -H "X-N8N-API-KEY: $N8N_KEY" "https://n8n.yavoh.cloud/api/v1/executions?limit=50"
```

---

## Portão geral — vale para toda fase

Nenhuma fase é considerada aprovada sem estes quatro:

- [ ] `active: true` e **62 nós** (ou 62 + os nós novos da fase) após a mudança
- [ ] **zero** execuções com `status` diferente de `success` desde a aplicação
- [ ] volume diário de leads distribuídos dentro da média das duas semanas anteriores (~7/dia)
- [ ] `versionId` anterior anotado, e rollback testado pelo menos uma vez em ambiente real

---

## Fase 0 — ligar o alerta de conexão

**Implementado** — aplicado em 2026-09-23 16:27 BRT.

- [x] `Montar Alerta [saída 0]` → `Enviar Alerta Conexão` presente nas conexões
      `versionId` anterior `e14f1ff7-aa49-4989-aaa7-b870a49f0ae8` → novo `e43645a3-2cda-4db7-9f40-6b6b969c1cdb`
- [x] workflow segue `active: true` com 62 nós
- [x] nenhuma execução perdida na janela do save (última antes e depois: id 8863)

**Falta testar:**

- [ ] **Alerta chega de verdade.** Na próxima queda de conexão da Evolution (esperado ~4×/dia), confirmar que a mensagem "❌ DESCONECTADO" ou "✅ RECONECTADO" chega no WhatsApp do operador
- [ ] A execução que dispara o alerta mostra `Enviar Alerta Conexão` no `runData` — hoje ela para em `Montar Alerta`

**Aprovado quando:** um alerta real chegou no aparelho **e** a execução correspondente mostra o nó de envio executado.

**Reverter se:** o volume de alertas impedir o operador de trabalhar. Rollback: apagar a conexão (`fase0.py --reverter`).

---

## Fase 1 — alertar quando um lead não é distribuído

- [ ] Nó `Alerta Lead Nao Distribuido` existe com `onError: continueRegularOutput`
      **Critério de bloqueio:** sem esse `onError`, a fase não pode ir para produção. Uma falha de alerta derrubaria a execução e passaria a perder leads que hoje funcionam.
- [ ] As três conexões refeitas, com o alerta **entre** o nó e seu destino original:
      `Duplicado de Plataforma?` saída 0 → alerta → `Loop Over Items`
      `Vendedor Encontrado?` saída 1 → alerta → `Loop Over Items`
      `Loja Encontrada?` saída 1 → alerta
- [ ] Nenhuma outra conexão do grafo mudou (comparar contra `ROLLBACK_workflow_n8n.json`)

**Testes:**

- [ ] **Duplicata:** reenviar mensagem de cliente existente para o mesmo anúncio → alerta chega, e `Alerta Lead Nao Distribuido` aparece no `runData` da execução
- [ ] **Sem vendedor:** com todos os vendedores inativos (em teste), uma mensagem nova → alerta chega
- [ ] **Alerta falhando não derruba nada:** apontar o nó para uma URL inválida de propósito, mandar uma mensagem, e confirmar que o lead **mesmo assim** foi distribuído e a execução ficou `success`

**Aprovado quando:** os três testes passaram e, ao longo de 48h, todo lead não distribuído gerou alerta — verificado pela conferência, não pela memória de quem estava olhando.

**Reverter se:** aparecer qualquer execução com `status: error` (baseline hoje é 0 em 373), ou se o volume de alertas por repetição legítima passar de ~10/dia.

---

## Fase 2 — causa raiz

**Bloqueio antes de aplicar:**

- [ ] Resolvido: `comando_leads` usa `mensagem_original`?
      `SELECT prosrc FROM pg_proc WHERE proname='comando_leads'`
      Se usar, a mudança de `p_mensagem_original` altera o que o vendedor lê pelo WhatsApp — decidir antes, não depois.

**Implementação:**

- [ ] `Prepara Dados NaPista.telefone` = `{{ $json.telefone }}`
- [ ] `Prepara Dados NaPista.anuncio` = `{{ $json.anuncio || $('Normaliza Dados').item.json.mensagemTexto }}`
- [ ] `Distribuir Lead.p_mensagem_original` = `{{ $input.item.json.mensagemTexto }}`
- [ ] Guarda antes de distribuir: telefone vazio **ou** dígitos iguais a `551131361712` / `551130044558` → não chama `distribuir_lead`, alerta
- [ ] `Separar Leads NaPista` reescrito: lê de `Normaliza Dados`, try/catch, devolve `{parse_ok: true|false}`, **sem** `onError: continueRegularOutput`

**Testes:**

- [ ] **Template com telefone:** `parse_ok: true`, `lead_id` não-nulo, `Encaminhar ao Vendedor` executado
- [ ] **Template sem telefone** (o formato atual da NaPista): não chama `distribuir_lead`, gera alerta, e **não** cria lead com o número da plataforma
- [ ] **`placeholderMessage`:** `parse_ok: false` + alerta, e nenhum objeto de erro descendo o fluxo
- [ ] **Não regrediu nas outras origens:** um lead de WhatsApp direto, um de Mobiauto e um de Facebook distribuídos normalmente depois da mudança

**Aprovado quando:**

- [ ] `SELECT count(*) FROM leads WHERE numero_cliente IN ('551131361712','551130044558')` não cresce
- [ ] Ao longo de 7 dias, nenhuma mensagem NaPista com telefone deixou de virar lead
- [ ] Volume total de leads/dia estável

**Reverter se:** qualquer origem que funcionava parar de distribuir.

> Efeito esperado, não é bug: o volume aparente de NaPista sobe, porque hoje todos colapsam num lead só por causa do `anuncio` vazio.

---

## Fase 3 — registrar toda mensagem

- [ ] Migration aplicada: tabela `mensagens_recebidas` + `UNIQUE(loja_id, canal, mensagem_externa_id)` + 3 índices
- [ ] `atividades.tipo` aceita `mensagem_triada` e `lead_promovido_de_triagem`
- [ ] RPCs `registrar_mensagem_recebida`, `atualizar_desfecho_mensagem`, `promover_mensagem_para_lead` criadas
- [ ] `promover_mensagem_para_lead` **chama `distribuir_lead` internamente** — nenhuma cópia de round-robin/dedup fora do Postgres
- [ ] `python3 validate_signatures.py` passa
- [ ] `leads` e `distribuir_lead` **não** foram alterados (diff vazio)
- [ ] Nó de registro no n8n com `onError: continueRegularOutput` — **critério de bloqueio**, o registro nunca pode impedir a distribuição

**Testes:**

- [ ] Uma mensagem qualquer gera linha em `mensagens_recebidas` **antes** do `distribuir_lead` rodar
- [ ] Derrubar o registro de propósito (URL inválida) → o lead **ainda assim** é distribuído
- [ ] Reenvio do mesmo `mensagem_externa_id` não cria linha duplicada
- [ ] `promover_mensagem_para_lead` numa linha de teste → lead sai pelo round-robin normal, com `registrar_atividade` gravado

**Aprovado quando:** por 7 dias, `count(mensagens_recebidas)` bate com o número de execuções `messages.upsert` do n8n, sem furo.

---

## Fase 4 — Portaria

- [ ] Chave da Anthropic como **credencial do n8n**, não hardcoded no nó
- [ ] Determinístico cobre: eco, vazio, conexão, gerente/vendedor, webhooks dedicados, número de plataforma, e-mail, mídia sem texto, `placeholderMessage`, e remetente que já é cliente com vendedor ativo
- [ ] IA roda **apenas** no balde `Outros`
- [ ] Saída estruturada com todos os campos obrigatórios, `temperature: 0`

**Guardas — critérios de bloqueio:**

- [ ] Telefone só aceito se os dígitos aparecerem **literalmente** no payload bruto. Teste: forçar o modelo a devolver um número inventado e confirmar que é descartado
- [ ] `trecho_evidencia` que não for substring literal do texto força `incerto`
- [ ] **Fail open:** derrubar a IA de propósito (chave inválida) e confirmar que a mensagem é distribuída assim mesmo, marcada `distribuido_com_duvida`

**Aprovado quando:** o portão da Fase 6 passou. Não antes.

---

## Fase 5 — tela de triagem

- [ ] `pages/5_Triagem.py` registrada nos **dois** lugares de `Home.py`
- [ ] Toda leitura/escrita via `utils/queries.py` — nenhuma chamada direta ao Supabase
- [ ] Cards com `st.container(border=True)`, **não** `st.data_editor`
- [ ] KPI "Com dúvida: N" no Dashboard, com link

**Testes:**

- [ ] Promover uma mensagem → lead criado pelo round-robin, `atividades` gravado
- [ ] Arquivar → linha marcada, desfazer funciona
- [ ] Login com código de outra loja não vê as mensagens desta (isolamento por `loja_id`)

---

## Fase 6 — sombra e corte

- [ ] Ramo sombra grava `decisao='sombra'` e **nunca** realimenta a distribuição
- [ ] Ramo vivo byte-a-byte idêntico ao anterior
- [ ] `Config Portaria` com um booleano por origem

**Portão de corte — o critério mais importante do plano:**

- [ ] ≥2 semanas **e** ≥200 mensagens em sombra
- [ ] **zero** casos de `nao_lead` sobre lead real
- [ ] falso `lead` é tolerado (já é o comportamento de hoje)

Corte por origem, nesta ordem, cada um com 7 dias estáveis antes do próximo: NaPista → Mobiauto/Webmotors → iCarros/OLX/Mercado Livre/Facebook → `Outros`.

---

## Fase 7 — monitoramento

- [ ] Workflow `Monitor Origens (Diário)` ativo, 08:00 America/Sao_Paulo
- [ ] Alarme "origem calada", limiar por origem
- [ ] Alarme "chegou e não virou nada" (>50% em 24h)
- [ ] Tabela "Saúde das origens" no Dashboard

**Teste que fecha o ciclo:**

- [ ] **Simular o incidente NaPista** e confirmar que o alarme dispara em ≤24h. Se não disparar, o monitoramento não serve — foi exatamente esse cenário que passou seis semanas invisível.

---

## Encerramento do incidente

- [ ] Os 3 leads recuperados (Gilvam 19/09, Josiel 19/09, Marcio 21/09) foram trabalhados pela loja
- [ ] Documentação atualizada: ADR 0008, ADR 0009, specs corrigidas, `CLAUDE.md` declarando que classificação mora na Portaria
- [ ] Decisão comercial com a NaPista registrada, qualquer que seja
- [ ] Uma semana sem alerta de lead não distribuído por causa técnica
