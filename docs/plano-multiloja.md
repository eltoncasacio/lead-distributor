# Plano — vender o sistema para várias lojas

> Escrito em 2026-09-23, depois de uma sessão de investigação e correção do incidente NaPista. Tudo aqui foi medido contra o sistema real (n8n Public API + Supabase), não inferido da documentação. Onde a medição não foi possível, está dito.

## Decisão de fundo: reformar, não reconstruir

A parte cara deste sistema já está paga: as regras de distribuição sob concorrência (round-robin, deduplicação, o lock que resolveu a race condition de 2026-08-31), a integração de WhatsApp, e os parsers de sete portais. Nada disso é óbvio, e só se aprende operando — o incidente NaPista desta semana é a prova.

O modelo de dados já nasceu multi-loja: toda tabela relevante tem `loja_id`, as funções do Postgres recebem `loja_id`, e **19 dos 67 nós do n8n já leem a loja do banco** em vez de tê-la fixa.

**Não falta sistema. Falta casca de produto.** Reconstruir jogaria fora sete meses de operação real para reaprender as mesmas lições.

---

## O que já existe e faz sentido manter

| Peça | Estado | Observação |
|---|---|---|
| `distribuir_lead` e as regras de negócio | sólido | Mantém a atomicidade no Postgres ([ADR 0001](adr/0001-postgres-rpc-dono-da-atomicidade.md)). Não mexer |
| Identificação de loja por instância Evolution | funciona | [ADR 0003](adr/0003-identificacao-loja-por-instancia.md). É o que torna o fluxo multi-loja |
| Parsers de 7 origens | funcionam, frágeis | Quebram em silêncio quando o portal muda o formato. Ver Fase 7 |
| `utils/queries.py` (39 funções) | bom padrão | Todas por `loja_id`. É a única defesa do isolamento hoje |
| Tabela `mensagens_recebidas` + 4 RPCs | novo, 2026-09-23 | Livro-razão de toda mensagem. Base do monitoramento por origem |
| Tela de Triagem | nova, 2026-09-23 | Onde um humano completa o que a automação não conseguiu |
| Alertas de lead não distribuído | novos, 2026-09-23 | Já pegaram um caso real em produção |

## O que falta, e por quê importa

| Falta | Hoje | Impacto de não ter |
|---|---|---|
| **Cadastro de loja** | SQL direto na tabela | Sem isso não existe "vender". Cada cliente novo é trabalho de engenharia |
| **Geração de `codigo_acesso`** | ninguém gera; o código é só lido, nunca escrito (verificado em todo o código) | Não há "esqueci meu código" nem rotação |
| **Autenticação de verdade** | UUID da loja na URL, sem expiração nem revogação | Link vazado = acesso total e permanente. Trocar o código **não** invalida links antigos |
| **Isolamento provado** | nunca testado com 2 lojas | É a base da promessa comercial |
| **8 nós fixos na Renato Motors** | `renato-motors` e números fixos | **Loja 2 mandaria alerta pela instância da loja 1, para o número da loja 1** |
| **`limite_leads`** | coluna existe, nada lê | Sem diferenciação de plano |

---

## Os três riscos reais

Não são os riscos que costumam preocupar. Estes foram medidos.

### 1. Vazamento entre lojas — risco de perder o cliente, não só um bug

O RLS está habilitado, mas as políticas negam tudo para `anon` e o sistema acessa com a `service_role`, que passa por cima. **A única defesa real é o código lembrar de filtrar por `loja_id` em toda consulta.** Um filtro esquecido e a loja A vê os leads da loja B.

Com um cliente isso é um bug. Com clientes pagantes é fim de contrato e de reputação.

### 2. A Evolution vira o maior custo de suporte

Medido em 2026-09-23: **62 quedas de conexão em 14 dias**, com **uma** loja. Cerca de 4 por dia. Cada queda produz `placeholderMessage` — mensagem que chega sem conteúdo decifrável (9 casos na janela).

Com dez lojas isso é queda a cada poucas horas. Não é problema de software: é operação, e vai consumir o dia de quem der suporte.

### 3. Parser quebra em silêncio

Foi exatamente o que aconteceu: a NaPista mudou o template e o sistema perdeu 14 de 15 leads durante seis semanas sem um único erro. Com N lojas e N portais, a superfície multiplica.

O alarme por origem deixa de ser desejável e passa a ser condição de operação.

---

## Fases

### Fase A — tirar os hardcodes (pequena, faz antes de tudo)

Hoje, se uma segunda loja entrar, os alertas dela saem pela instância Evolution da Renato Motors e vão para o número do dono dela. É um bug esperando o primeiro cliente.

**Change-set levantado nó a nó em 2026-09-23: [dev/fase-a-tirar-hardcodes-n8n.md](dev/fase-a-tirar-hardcodes-n8n.md).** Ainda não aplicado — depende de 3 decisões listadas lá.

Correções ao que estava escrito aqui:

- São **14 nós** com valor fixo, não 8 — mas só **6** são hardcode de loja. Os números `551131361712`/`551130044558` em `Duplicado de Plataforma?`, `Filtro Msg Vazia`, `Verificar Origem` e `Telefone do Cliente?` identificam **a plataforma**, são iguais para qualquer loja e **ficam**.
- **`Alerta Loja Nao Encontrada` e o alerta de conexão não têm contexto de loja** (rodam antes de a loja ser identificada, ou num ramo que desvia de `Normaliza Dados`). São alertas de **operador** — o número do dono neles não é bug. Sai a URL/instância/chave, não o destino.
- **"Buscar o gerente pelo `loja_id`" pode não ser necessário**: `Identificar Loja` já traz `numero_whatsapp` e `Preparar Dados Loja` já expõe como `lojaNumero`. Se o número da loja servir de destino, o custo é zero nó novo.
- **`Extrai Dados NaPista` não é mecânico.** O hardcode ali existe porque **e-mail não tem instância** — não há discriminador de loja no ramo do Gmail. Exige coluna `lojas.email_leads` + nó de consulta pelo cabeçalho `to`. Ver o change-set.

> Três deles (`Alerta *`) foram criados em 2026-09-23 copiando o padrão hardcoded existente em vez de ler do banco como faz `Encaminhar ao Vendedor`. Foi decisão errada e é barata de corrigir.

**Checklist**
- [x] Alertas usam `$('Normaliza Dados').item.json.evolutionServerUrl` e `.instancia`, como `Encaminhar ao Vendedor` (10/10)
- [ ] Destino do alerta vem do gerente da loja, não de número fixo — **adiado por decisão do dono (10/10): alertas seguem para ele**
- [ ] `Extrai Dados NaPista` deixa de ter `lojaId` fixo — **fica para a loja 2**
- [ ] O nome do path do webhook (`renato-motors`) pode ficar — é só um nome; `Identificar Loja` resolve pela instância

**Critérios de aceite**
- [ ] Nenhum nó do workflow contém a string `renato-motors` fora do path do webhook
- [ ] Nenhum nó contém número de WhatsApp fixo
- [ ] Um lead da Renato Motors continua sendo distribuído normalmente depois da mudança
- [ ] Um alerta da Renato Motors continua chegando

### Fase B — provar o isolamento (pequena, obrigatória)

Existe roteiro pronto em [dev/roteiro-loja-fake-multitenant.md](dev/roteiro-loja-fake-multitenant.md).

**Checklist**
- [x] Criar loja de teste e vendedores próprios (10/10, dentro de transação desfeita — ver abaixo)
- [x] Simular leads chamando `distribuir_lead` por SQL
- [ ] ~~Entrar no Dashboard com o código da loja de teste~~ — Streamlit fora do plano (decisão de 10/10)
- [x] Revisar as 39 funções de `utils/queries.py` conferindo `.eq("loja_id", loja_id)` em **todas** — feito em 2026-09-23, ver abaixo

#### Resultado da prova de isolamento (2026-10-10)

`sql/fase_b/teste_isolamento.sql`, rodado **contra o banco de produção** por `sql/fase_b/rodar_teste_isolamento.py`, dentro de um bloco que sempre termina desfeito (nada sobra — conferido depois). **26 verificações, todas OK:**

- **Distribuição:** 6 leads na loja de teste foram só para os 3 vendedores dela, em rodízio (T1, T2, Giu, T1, T2, Giu); cliente que já é da Renato Motors, escrevendo para a loja de teste, **não** foi amarrado ao vendedor da RM.
- **Quem manda:** `identificar_remetente` devolve a loja certa pelo par instância+número; o mesmo número de gerente nas duas lojas é reconhecido em cada uma; vendedor de uma loja é "cliente" na outra.
- **Comandos:** `listar vendedores` só mostra a própria loja; `pausar Japa` na loja de teste não acha o Japa da RM; `pausar Giu` na loja de teste mira a Giu **dela** (mesmo nome, outra loja); "sim" mandado na RM não confirma pendência da loja de teste; a pausa não tocou a Giu da RM.
- **Vendedor:** "meus leads" traz só os dele; vendedor de uma loja é ignorado pela outra.
- **Legado do gerente:** `comando_status` e `comando_leads` só com dados da loja.
- **IA:** contador de uso separado por loja.
- **Renato Motors intacta:** ponteiro da fila, leads (1.299), atividades (1.403), vendedores, pendências e contador de IA iguais antes e depois; nenhum lead do banco inteiro com vendedor de outra loja.

**Não coberto (fica para a loja real):** segunda instância Evolution recebendo WhatsApp de verdade pelo n8n; ramo de e-mail da NaPista (`Extrai Dados NaPista` ainda tem a RM fixa).

**Achado lateral:** vendedores criados no mesmo instante (mesma transação) travam o rodízio, porque ele ordena por `criado_em`. Apareceu só no teste; na operação cada vendedor é cadastrado num momento (o comando `inserir` insere um por vez). Registrado, não corrigido — `distribuir_lead` não se mexe sem motivo (ADR 0001).

#### Resultado da revisão das 39 funções (2026-09-23)

**5 funções corrigidas.** Duas eram furo real, três eram armadilha latente:

| Função | Era | Virou |
|---|---|---|
| `editar_vendedor` | recebia só `vendedor_id`, `UPDATE ... WHERE id = ?` — **sem nenhuma amarra com a loja** | recebe `loja_id`, filtra por ele |
| `alterar_status_vendedor` | idem; chegava a **ler** o `loja_id` da linha, só não conferia | recebe `loja_id`, filtra na leitura e na escrita |
| `editar_gerente` | `loja_id: str = None`, filtro dentro de `if loja_id:` | `loja_id` obrigatório, filtro incondicional |
| `desativar_gerente` | idem (sem chamador hoje) | idem |
| `deletar_gerente` | idem — e é **DELETE de verdade**, o pior caso | idem |

As de gerente estavam seguras na prática (os dois chamadores vivos passavam o `loja_id`), mas a guarda era **opt-in**: bastava um chamador novo esquecer o último argumento para o filtro sumir em silêncio. Numa base com duas lojas, `deletar_gerente` sem `loja_id` apaga gerente de qualquer loja.

**4 funções aparecem como suspeitas em varredura automática e não são** — registrado aqui para não serem "corrigidas" de novo por engano: `atualizar_proximo_vendedor_da_loja`, `get_limite_leads` (filtram a tabela `lojas` por `.eq("id", loja_id)`, que é a PK da própria loja), `obter_proximo_vendedor` (a leitura sem filtro pega só o `ordem_fila` do ponteiro da própria loja, e o resultado é casado contra uma lista já filtrada) e `reordenar_vendedores` (valida a posse de cada vendedor e levanta exceção — **é o padrão a copiar**).

> **Regra para o front novo (Fase D)**: `loja_id` nunca é parâmetro opcional, e toda escrita por PK leva o filtro de loja junto. Os dois furos existiam exatamente porque a função atualizava por `id` e confiava em quem chamava.

**Critérios de aceite**
- [ ] A loja de teste não vê nenhum lead, vendedor, gerente, atividade ou mensagem da Renato Motors — e vice-versa
- [ ] Round-robin da loja de teste roda na fila dela, sem tocar no ponteiro da outra
- [ ] Nenhuma função de leitura sem filtro de `loja_id`
- [ ] A loja de teste é apagada ao final, ou fica marcada como `ativa = false`

### Fase C — autenticação e cadastro de loja (média)

Estas duas andam juntas: cadastrar sem autenticar direito não faz sentido.

**Decisão de produto pendente:** senha por loja (como hoje) ou login por pessoa? Login por pessoa resolve "quem fez o quê" e permite cortar o acesso de quem saiu, mas é mais para construir e para a loja administrar.

> **A Fase C mudou de forma em 2026-09-25.** Em vez de um painel de administração, a proposta passa a ser estender o fluxo de comandos que já existe no WhatsApp: [specs/tecnica/08-comandos-whatsapp.md](specs/tecnica/08-comandos-whatsapp.md). Nada implementado ainda.
>
> O que isso muda no escopo desta fase:
>
> - **A administração da loja** (vendedor, gerente) sai do painel e vai para comando por WhatsApp — canal que já é **melhor autenticado** que o Dashboard, porque o número é verificado pelo WhatsApp e o `loja_id` vem da instância, não de nada que o usuário digita.
> - **A administração do sistema** (criar loja, gerar `codigo_acesso`) vira **processo manual do dono**, por decisão dele. Não desaparece — vira trabalho manual com limite conhecido: sem rastro de auditoria e sem rotação de código.
> - **"Quem fez o quê"**, a dúvida de produto acima, fica resolvido de graça pelo canal de comando: o remetente é uma pessoa identificada, não um código de loja compartilhado.
>
> **Achado que vira tarefa desta fase:** `comando_leads` e `comando_status` recebem só `p_loja_id`, então não sabem quem perguntou — e `Não É Lead` deixa vendedor e gerente passarem igual. Na prática, **hoje um vendedor que digita `leads` vê os leads da loja inteira.** Correção é em SQL, ver o spec 08.

**Checklist**
- [ ] Sessão em cookie assinado, com expiração — o `loja_id` sai da URL
- [ ] Logout invalida de verdade
- [ ] Papel de admin (dono do sistema) separado de papel de loja
- [ ] Tela admin: criar loja, gerar `codigo_acesso`, ativar/desativar
- [ ] Geração de código com rotação ("esqueci meu código")
- [ ] Cadastro da instância Evolution da loja em `lojas.instancia_evolution` e `lojas.evolution_api_key`

**Critérios de aceite**
- [ ] Um link copiado de uma sessão logada **não** dá acesso depois do logout nem depois do prazo
- [ ] Rotacionar o código invalida o acesso anterior
- [ ] Cadastrar uma loja nova pela tela, sem SQL, e ela consegue entrar
- [ ] Um admin não consegue ver dados de loja pela tela de loja sem escolher a loja explicitamente

### Fase D — front novo (média-grande)

Só depois de A, B e C. O front herda o modelo de autenticação e de isolamento — construir antes é refazer depois.

Base de referência: [specs/tecnica/06-migracao-frontend-nextjs.md](specs/tecnica/06-migracao-frontend-nextjs.md), **atualizado em 2026-09-23** — cobre as 5 páginas, as 39 funções e os 3 pontos onde o próprio Dashboard chama RPC (`comando_status`, `promover_mensagem_para_lead`, `arquivar_mensagem`), o que a versão anterior do spec negava.

**Checklist**
- [x] Atualizar o spec 06 com a Triagem e as RPCs que o Dashboard chama
- [ ] `service_role` só no servidor, nunca no navegador — igual hoje
- [ ] Migrar tela por tela, rodando ao lado do Streamlit
- [ ] Ordem sugerida: Gerentes → Vendedores → Triagem → Leads → Dashboard (o Dashboard tem gráficos e drag-and-drop, deixa por último)

**Critérios de aceite**
- [ ] Cada tela migrada tem paridade funcional com a do Streamlit antes da próxima começar
- [ ] Nenhuma chamada ao Supabase a partir do navegador
- [ ] O Streamlit continua funcionando durante toda a migração

### Fase E — monitoramento por origem (pequena, alto retorno)

É a Fase 7 do plano de remediação. Independente de todo o resto e pode entrar a qualquer momento.

**Checklist**
- [ ] Workflow diário que compara, por origem, mensagens recebidas contra leads criados
- [ ] Alarme quando uma origem chega e não vira lead (>50% em 24h)
- [ ] Alarme quando uma origem fica calada além do esperado para ela
- [ ] Tabela "Saúde das origens" no painel
- [ ] Alarme + desativação automática de vendedor ativo sem `numero_whatsapp` (ver abaixo)

**Critério de aceite**
- [ ] Simular o incidente NaPista e confirmar que o alarme dispara em ≤24h

**Pendente (2026-10-01): vendedor ativo sem WhatsApp — detectar, avisar, desativar**

`distribuir_lead` (SQL) só filtra por `status = 'ativo'`, não checa `numero_whatsapp IS NOT NULL` ([FIX_distribuir_lead.sql](historico/incidentes/2026-08-31-race-condition/FIX_distribuir_lead.sql)). Um vendedor ativo sem número entra no rodízio normalmente, o lead é criado, e o encaminhamento no n8n falha calado — mesmo padrão silencioso do incidente NaPista, só que por cadastro incompleto em vez de mudança de infra externa.

- [x] Detecção manual: `auditoria_producao.py` já alerta na seção [2] quando algum ativo não tem `numero_whatsapp` (adicionado 2026-10-01, achado ao checar o vendedor André).
- [ ] Aviso automático ao gerente por WhatsApp quando isso acontecer.
- [ ] Desativação automática do vendedor nesse caso (a função `alterar_status_vendedor` já faz a parte de desativar; falta o gatilho automático).

**Por que não foi além do script manual**: não existe hoje nenhum envio de WhatsApp saindo deste repo — isso é todo feito pelo n8n. Para automatizar o aviso + desativação seria necessário mexer no workflow n8n (exige a chave de API pública do n8n, que só o dono tem — ver seção de Credenciais no [CLAUDE.md](../CLAUDE.md)) ou criar um script que roda via cron e grava direto no Supabase. Decisão de arquitetura (cron fora do repo vs. nó novo no n8n) fica para quando essa fase for priorizada.

### Fase F — plano e cobrança (adiável)

Só quando houver o terceiro cliente. Antes disso, fatura manual resolve e custa zero de engenharia.

- [ ] `lojas.limite_leads` passa a ser lido e aplicado
- [ ] Aviso à loja ao se aproximar do limite

---

## Ordem recomendada e por quê

1. **A** e **B** primeiro. São pequenas, e são o que transforma "tecnicamente multi-loja" em "seguro para vender". Podem ser feitas antes de qualquer decisão sobre o front.
2. **E** em paralelo — barata e evita repetir o incidente.
3. **C** quando houver perspectiva concreta de segunda loja.
4. **D** por último, herdando o que C definiu.
5. **F** só com o terceiro cliente.

## Decisões e achados de 2026-10-09

### Decisão: manter a Evolution por enquanto

Avaliada a troca para a API oficial da Meta ou para o Twilio. **Decisão do dono: manter a Evolution e só migrar se a dor realmente aparecer.** Registrado o que foi levantado, para não refazer:

- **Custo não decide.** Volume real: 113 a 310 leads/mês (set/2026: 113). Estimativa por loja/mês, com premissas minhas (150 leads, ~400 mensagens recebidas, ~60 alertas/respostas, câmbio ~R$ 5,5): Twilio ≈ US$ 5–7 se o template for classificado como utilidade, ≈ US$ 13 se for marketing; Meta direto ≈ US$ 1,5–4. O volume de mensagens recebidas é palpite — `mensagens_recebidas` só existe desde 23/09.
- **Preços confirmados:** Twilio cobra US$ 0,005 por mensagem recebida ou enviada, além da tarifa da Meta. **Não confirmado:** a tarifa da Meta para o Brasil; fontes de terceiros divergem (utilidade ≈ US$ 0,008–0,022; marketing ≈ US$ 0,0625).
- **O que pesa é onboarding**, não preço: verificação da empresa e revisão do app na Meta antes de usar o Embedded Signup; templates aprovados para avisar vendedor que nunca escreveu ao número; o número da loja sai do aplicativo, a menos que a coexistência (listada como disponível no Brasil por fontes de terceiros, elegibilidade caso a caso) se aplique.
- **Ponto de encaixe para a troca futura:** o nó `Normaliza Dados` converte o payload da Evolution em campos padrão. Um webhook novo com normalizador próprio que produza os mesmos campos, mais a troca dos envios `sendText`, permitiria uma loja no canal oficial sem mexer na Renato Motors. Guardar o canal por loja em `lojas`.
- **Gatilho para reabrir a decisão:** `placeholderMessage` ou queda de conexão passarem a custar leads, ou a segunda loja entrar.

### Achados da auditoria de 2026-10-09

Ainda **não corrigidos**. Ordem de urgência:

1. **CONFIRMADO em 2026-10-09: a Evolution está desconectada.** A última execução do n8n é a `9136` (07/10 22:29 UTC = 19:29 BRT), um `connection.update` com `state: close` e `statusReason: 401` (sessão desligada do aparelho). Depois disso não entrou nenhum webhook; `connectionState` da instância `renato-motors` devolve `close`. Leads entre 07/10 19:29 BRT e a reconexão não chegaram ao sistema. O alerta de desconexão **nem foi enviado**: `Montar Alerta` rodou e montou o texto, mas no workflow ao vivo ele **não tem nenhuma conexão de saída** (`main: [[]]`) — o 'Passo 0' do RUNBOOK não está aplicado. Mesmo ligado, sairia pela instância que caiu (ver [fase-a-tirar-hardcodes-n8n.md](dev/fase-a-tirar-hardcodes-n8n.md)). **Reconectado no mesmo dia (09/10 ~20:45 UTC); distribuição voltou a funcionar (teste, execução `9140`).** Leads do período parado ainda não recuperados. Detalhes no [RUNBOOK](historico/incidentes/2026-09-23-napista-leads-perdidos/RUNBOOK.md).
2. **Chave `service_role` do Supabase escrita no nó `Normaliza Dados`** (campo `supabaseKey`). Qualquer pessoa com acesso ao editor, a uma exportação ou a um backup do workflow tem acesso total ao banco de todas as lojas. Não estava na lista da Fase A. Entra como item da Fase A: mover para credencial do n8n.
3. **Segundo caminho de comando não documentado:** o nó `Switch` reage a clique no botão "Acessar leads" dos templates (lendo `quickReplyButton.displayText`) e responde pelo nó `Acessar Leads`. Não consta no spec 08. Mapear o que o alimenta antes de separar gerente de vendedor no roteamento.
4. **Lead possivelmente enviado em duplicidade:** em 06/10 15:57 há duas atividades "Lead de F. L. B. (cliente) encaminhado para Felipe". Não foi verificado se o vendedor recebeu duas mensagens.
5. **Só há 1 gerente ativo**, e o número que recebe os alertas (o do dono) provavelmente não é gerente cadastrado, então uma mensagem dele para a loja seria tratada como cliente. Relevante para a regra "não remover o último gerente" e para decidir se o dono administra por comando.
6. **`identificar_remetente` é executável por `anon`** (spec 02). As RPCs novas de comando devem nascer sem permissão para `anon`.
7. **96 mensagens pendentes de revisão** na Triagem, sem ninguém tratando.
8. **Testes cobrem só o isolamento de `utils/queries.py`** (28, passando). RPCs do banco e n8n não têm teste; a RPC de comandos exige a loja de teste da Fase B para ter algum.

Operação de 2026-10-08/09 (fora de código): vendedor Felipe removido da fila e Japa reativado, via `alterar_status_vendedor`; o registro está em `atividades`.

### Ordem ajustada

1. Confirmar que o sistema está recebendo mensagens (achado 1).
2. Corrigir o vazamento do vendedor (`comando_leads`/`comando_status` sem escopo por remetente) e construir os comandos por WhatsApp, em branch própria — ver [spec 08](specs/tecnica/08-comandos-whatsapp.md).
3. Fase A, agora incluindo a chave fixa (achado 2); Fase B antes de qualquer segunda loja.

## Decisões e estado de 2026-10-10

- **Streamlit fora do plano.** Decisão do dono: não será mais usado e talvez seja excluído. Não investir nele (nem na Fase D como "migrar o Streamlit"). O canal de gestão da loja passa a ser o **WhatsApp**; um painel web, se voltar, nasce depois e consome as mesmas funções do banco.
- **Fase A1 feita:** a chave `service_role` saiu do workflow n8n para uma credencial (ver RUNBOOK). **Falta rotacionar a chave** — agora só exige trocar a credencial no n8n.
- **Alerta "Lead NaPista sem telefone" desligado** por decisão do dono; a mensagem segue para a Triagem.
- **Histórico git limpo** de UUID da loja, chave da Evolution e dados pessoais antes do primeiro push. Repositório no GitHub **ainda público** (conta dona é outra; o dono decidiu deixar assim por ora).

- **Foco definido pelo dono (2026-10-10): só o core — multi-loja, comandos por WhatsApp e distribuição.** KPIs por vendedor ficam fora: não há como saber se o lead foi vendido e os vendedores não vão registrar.
- **Cliente que escreve de novo vira lead novo (~9% dos leads): decidido não mexer** (dono, 2026-10-10). Medição e causa em [05-deduplicacao](specs/regras-de-negocio/05-deduplicacao.md).

- **Comandos por WhatsApp em produção (10/10, noite)**, com confirmação por "sim" e IA (Haiku 5.5 via OpenRouter, travas no Postgres, 30 chamadas/pessoa/dia). Ver spec 08 e RUNBOOK.

- **Decisões do dono (10/10, noite) — não reabrir:** (1) **não rotacionar** a chave `service_role` do Supabase, apesar de ter passado pelo histórico de execuções do n8n e pela conversa; (2) **não recuperar** os leads do período em que a Evolution ficou fora (07–09/10) nem os dois `placeholderMessage` da NaPista; (3) alerta de desconexão da Evolution **por e-mail** para o dono; (4) seguir com Fase A e Fase B.

- **Portaria (IA na entrada) em modo sombra desde 10/10 à noite** — só número novo; não-lead seria ignorado, dúvida distribui. **Revisar em 17/10** com `portaria/relatorio_sombra.py` e decidir se liga. Boas-vindas automáticas: depois. Pendente separado: alerta de "lead não entregue ao vendedor".

**Achado que muda os KPIs por vendedor:** todos os 447 leads desde julho estão com `status_lead = negociando` e nenhum foi atualizado depois de distribuído. **Conversão e funil não têm dado** — ninguém marca venda. Dá para medir hoje: leads recebidos por vendedor, por período e por origem, e tempo desde o último lead. Tempo de resposta também não é registrado. Conversão só passa a existir se o vendedor puder marcar o status — candidato natural a comando de WhatsApp.

**Achado para "quem fez o quê":** `atividades` não tem coluna de autor nem de vendedor (só `tipo` e `descricao`). Registrar autor de comando exige coluna nova.

## O passo que não é código

**Conseguir a segunda loja.** Uma loja real, pagando ou em teste. Sem ela, cadastro, planos e isolamento são construídos no escuro, adivinhando o que o cliente precisa.

E vale lembrar o atrito operacional por cliente, que não é software: cada loja precisa da própria instância Evolution, com leitura de QR code e webhook apontado para o n8n. Isso não escala sozinho e é o que mais vai consumir tempo no onboarding.

## O que NÃO fazer

- **Não reconstruir do zero.** A parte difícil já funciona e está provada em produção
- **Não mexer em `distribuir_lead`** para acomodar multi-loja — ela já recebe `loja_id` e está correta
- **Não começar pelo front.** Ele herda auth e isolamento; construir antes é refazer
- **Não confiar no RLS como está.** As políticas negam tudo e o sistema usa `service_role`. O isolamento é responsabilidade do código até que isso mude
