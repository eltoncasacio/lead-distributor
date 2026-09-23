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

**Os 8 nós:** `Webhook`, `Webhook Webmotors`, `Montar Alerta`, `Enviar Alerta Conexão`, `Extrai Dados NaPista`, `Alerta Lead Nao Distribuido`, `Alerta Loja Nao Encontrada`, `Alerta NaPista Sem Telefone`.

> Três deles (`Alerta *`) foram criados em 2026-09-23 copiando o padrão hardcoded existente em vez de ler do banco como faz `Encaminhar ao Vendedor`. Foi decisão errada e é barata de corrigir.

**Checklist**
- [ ] Alertas usam `$('Normaliza Dados').item.json.evolutionServerUrl` e `.instancia`, como `Encaminhar ao Vendedor`
- [ ] Destino do alerta vem do gerente da loja, não de número fixo — exige buscar o gerente pelo `loja_id` (hoje nenhum nó faz isso)
- [ ] `Extrai Dados NaPista` deixa de ter `lojaId` fixo
- [ ] O nome do path do webhook (`renato-motors`) pode ficar — é só um nome; `Identificar Loja` resolve pela instância

**Critérios de aceite**
- [ ] Nenhum nó do workflow contém a string `renato-motors` fora do path do webhook
- [ ] Nenhum nó contém número de WhatsApp fixo
- [ ] Um lead da Renato Motors continua sendo distribuído normalmente depois da mudança
- [ ] Um alerta da Renato Motors continua chegando

### Fase B — provar o isolamento (pequena, obrigatória)

Existe roteiro pronto em [dev/roteiro-loja-fake-multitenant.md](dev/roteiro-loja-fake-multitenant.md).

**Checklist**
- [ ] Criar loja de teste e vendedores próprios
- [ ] Simular leads chamando `distribuir_lead` por SQL
- [ ] Entrar no Dashboard com o código da loja de teste
- [ ] Revisar as 39 funções de `utils/queries.py` conferindo `.eq("loja_id", loja_id)` em **todas**

**Critérios de aceite**
- [ ] A loja de teste não vê nenhum lead, vendedor, gerente, atividade ou mensagem da Renato Motors — e vice-versa
- [ ] Round-robin da loja de teste roda na fila dela, sem tocar no ponteiro da outra
- [ ] Nenhuma função de leitura sem filtro de `loja_id`
- [ ] A loja de teste é apagada ao final, ou fica marcada como `ativa = false`

### Fase C — autenticação e cadastro de loja (média)

Estas duas andam juntas: cadastrar sem autenticar direito não faz sentido.

**Decisão de produto pendente:** senha por loja (como hoje) ou login por pessoa? Login por pessoa resolve "quem fez o quê" e permite cortar o acesso de quem saiu, mas é mais para construir e para a loja administrar.

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

Base de referência já escrita: [specs/tecnica/06-migracao-frontend-nextjs.md](specs/tecnica/06-migracao-frontend-nextjs.md). **Está desatualizada**: descreve 4 páginas e ~30 funções; hoje são 5 páginas (Triagem entrou) e 39 funções.

**Checklist**
- [ ] Atualizar o spec 06 com a Triagem e as 4 RPCs novas
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

**Critério de aceite**
- [ ] Simular o incidente NaPista e confirmar que o alarme dispara em ≤24h

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

## O passo que não é código

**Conseguir a segunda loja.** Uma loja real, pagando ou em teste. Sem ela, cadastro, planos e isolamento são construídos no escuro, adivinhando o que o cliente precisa.

E vale lembrar o atrito operacional por cliente, que não é software: cada loja precisa da própria instância Evolution, com leitura de QR code e webhook apontado para o n8n. Isso não escala sozinho e é o que mais vai consumir tempo no onboarding.

## O que NÃO fazer

- **Não reconstruir do zero.** A parte difícil já funciona e está provada em produção
- **Não mexer em `distribuir_lead`** para acomodar multi-loja — ela já recebe `loja_id` e está correta
- **Não começar pelo front.** Ele herda auth e isolamento; construir antes é refazer
- **Não confiar no RLS como está.** As políticas negam tudo e o sistema usa `service_role`. O isolamento é responsabilidade do código até que isso mude
