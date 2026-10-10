# Comandos por WhatsApp — administração da loja pelo celular

> **STATUS (2026-10-10): EM PRODUÇÃO, com IA** — comandos, confirmação por "sim", IA (Claude Haiku 5.5 via OpenRouter) com travas no Postgres e limite de 30 chamadas/pessoa/dia. n8n `versionId 27980f06`. Fonte do prompt: `comandos_ia/prompt.py`; avaliação: `comandos_ia/avaliar.py`. (Era: 2026-09-25, proposta, nada implementado.) Nenhuma linha de código ou nó de n8n foi escrita a partir deste documento. É o registro de uma conversa de desenho; quando for construído, este aviso sai.
>
> A ideia: em vez de construir um painel de administração (parte da Fase C do [plano-multiloja](../../plano-multiloja.md)), estender o fluxo de comandos que **já existe** no WhatsApp para cobrir o cadastro de vendedores e gerentes.

## 1. O que existe hoje

Verificado no workflow real (`Renato Motors Amarrar Lead`, `Qj200sqS9544ao3d`) em 2026-09-25.

```
Webhook → Normaliza Dados → Filtro fromMe → Identificar Loja → Preparar Dados Loja
   → Identificar Remetente → Não É Lead → Identificar Comando → [status | leads | fallback]
```

| Peça | O que faz |
|---|---|
| `Identificar Remetente` | RPC `identificar_remetente(p_instancia, p_numero_remetente)` → devolve `papel` |
| `Não É Lead` | se `papel` é `vendedor` **ou** `gerente`, desvia para o roteador de comandos |
| `Identificar Comando` | `switch` com match **exato** de uma palavra: `status`, `leads`, senão cai no fallback |
| `Buscar Status` | RPC `comando_status(p_loja_id)` |
| `Buscar Leads` | RPC `comando_leads(p_loja_id)` |
| `Cmd Não Reconhecido` | responde com o menu, **escrito à mão dentro do nó** |

Duas consequências disso que valem registrar:

- Mensagem de gerente ou vendedor **nunca vira lead** — o `Não É Lead` a desvia antes. Ou seja, o canal de staff já é um canal exclusivo de comando, sem ambiguidade a resolver entre "isto é comando ou é cliente?".
- Os comandos existentes são **somente leitura** e de **uma palavra exata**. `leads` funciona; `ver leads` não.

## 2. Divergência encontrada: vendedor vê a loja inteira

**Isto não é funcionalidade nova, é defeito.**

`Buscar Leads` chama a RPC passando **um único parâmetro**:

```
p_loja_id: {{ $('Preparar Dados Loja').item.json.lojaId }}
```

Mesma coisa em `comando_status`. A RPC **não recebe quem perguntou** — não tem como escopar por pessoa nem se quisesse. E como `Não É Lead` deixa vendedor e gerente passarem pelo mesmo caminho, **hoje um vendedor que digita `leads` recebe os leads da loja inteira, inclusive os dos colegas.**

A regra pretendida é a oposta: vendedor vê só o que é dele, gerente vê tudo.

> A correção é **em SQL**, não em nó do n8n: a RPC precisa passar a receber o remetente e escopar por ele. O `identificar_remetente` já resolveu a pessoa alguns nós antes — a informação existe no fluxo e só não é repassada. Ver a regra em [CLAUDE.md](../../../CLAUDE.md): regra de negócio mora no Postgres.

## 3. Isolamento entre lojas — já é estrutural

O `loja_id` do comando **não vem de nada que o usuário digita**. Vem do `Identificar Loja`, que resolve pela instância da Evolution que recebeu a mensagem.

Um gerente não consegue pedir dado de outra loja porque não alcança a instância de outra loja — não existe campo para ele manipular.

Isso é uma garantia **mais forte** que a do Dashboard, onde o isolamento depende de o código lembrar de filtrar por `loja_id` em 39 funções (e em 2026-09-23 cinco delas não filtravam — ver `tests/test_isolamento_loja.py`). O canal de comando parte do terreno mais firme, não do mais frágil.

## 4. Modelo de autorização

Duas dimensões, e elas são independentes:

| | Vendedor | Gerente |
|---|---|---|
| **Leitura** | só os dados dele | tudo da loja |
| **Escrita** (cadastro) | nenhuma | tudo da loja |
| **Outra loja** | nunca | nunca |

A separação de escrita **não é preciosismo de segurança, é incentivo financeiro**. Com round-robin, tirar um colega da fila significa literalmente mais leads para quem tirou. Um vendedor com acesso a `excluir vendedor` tem motivo concreto para usá-lo.

Hoje `Não É Lead` manda vendedor e gerente pelo mesmo caminho. Separar os dois é pré-requisito de qualquer comando de escrita — e é mudança no roteamento, não só nós novos.

## 5. Endereçamento: nome **e** telefone

A forma proposta é `pausa joao 19997998975` — **os dois juntos**.

Isso não é redundância, é **checksum**. Se o telefone resolver para alguém que não se chama "joao", o sistema **recusa e mostra o que encontrou**, em vez de obedecer.

Pega dois erros diferentes:

1. dígito digitado errado que por azar casa com outra pessoa;
2. "eu achava que esse número era do João" — que, com só o número, passaria silencioso e pausaria a pessoa errada com total confiança do sistema.

### Telefone contra índice numerado

| | Telefone | Índice de uma lista |
|---|---|---|
| Estabilidade | **estável** | muda se alguém cadastrar entre o `listar` e o `pausar` |
| Esforço no celular | 11 dígitos | uma tecla |
| Contexto visível | de memória | a lista está logo acima |

Nenhum dos dois é seguro sozinho. **Quem torna seguro é o eco**, não o identificador — ver a seção seguinte. Com eco, dá para aceitar os dois: nome quando é óbvio, telefone como saída quando há dois João.

> ⚠️ A unicidade do telefone é garantida por `whatsapp_ja_existe()`, que a tela chama antes de inserir. É **convenção da aplicação, não constraint do Postgres** — linha inserida por SQL direto escapa. Não tratar como garantia do banco.

## 6. Quando confirmar

A regra **não** é "confirme toda escrita" nem "confirme todo pedido".

> **Confirme quando o sistema interpretou alguma coisa — não quando a ação é destrutiva.**

Por quê cada metade:

- **Confirmar leitura sem ambiguidade é atrito sem retorno.** "Quer mesmo ver os leads?" só ensina o usuário a responder "sim" no automático, que é como confirmação morre.
- **Confirmar só escrita está errado**, porque mostrar os dados do João errado já é vazamento — mesmo sendo leitura.

Se a pessoa digitou comando exato com argumento exato, não há o que confirmar. Se o sistema **resolveu** algo (casou um nome, interpretou um telefone, escolheu entre dois homônimos), ele ecoa o que entendeu e espera.

### O padrão eco-e-reenvio (sem estado)

O n8n é **sem estado entre execuções**: a resposta do gerente chega numa execução diferente, sem memória de que havia pergunta pendente. Perguntar "qual João?" e esperar "1" exige tabela de conversa pendente, com expiração e tratamento de quem responde outra coisa no meio.

O padrão que evita isso: **o sistema não pergunta, responde com o comando pronto.**

```
João Silva — 19 99799-8975

Para pausar, envie:
pausa joao 19997998975
```

Não é pergunta, é resposta copiável. E quando o gerente manda essa segunda mensagem, ele **já confirmou por construção** — viu o nome resolvido, viu o número, escolheu enviar.

**O comando completo É a confirmação.** Sem sim/não separado, sem estado, sem expiração.

## 7. `menu` e `info <comando>`

- `menu` → lista os comandos existentes
- `info leads` → descrição daquele comando

O valor óbvio é o usuário não precisar decorar. O valor que importa mais para este projeto é outro:

Hoje o texto do menu está **cravado dentro do nó `Cmd Não Reconhecido`**, listando `status` e `leads` na mão. Comando novo exige lembrar de editar esse texto também. É deriva doc-versus-sistema em miniatura, dentro de um nó — o mesmo problema que gerou a [auditoria de 2026-09-11](../../historico/AUDITORIA_2026-09-11.md).

Com um **registro de comandos** (tabela ou arquivo), o menu, o `info`, a mensagem de comando não reconhecido e a documentação saem todos da mesma fonte, e acrescentar comando vira **acrescentar uma linha**.

## 8. Comandos propostos

Nenhum está implementado. Agrupados por risco, não por assunto.

| Comando | Papel | Reversível? |
|---|---|---|
| `menu`, `info <cmd>` | ambos | leitura |
| `status` | ambos (escopado) | leitura |
| `leads`, `meus leads`, `leads hoje`, `leads semana` | ambos (escopado) | leitura |
| `listar vendedores`, `listar gerentes` | gerente | leitura |
| `inserir vendedor <nome> <telefone>` | gerente | aditivo |
| `pausar <nome> <telefone>` / `despausar` | gerente | **sim** |
| `inserir gerente <nome> <telefone>` | gerente | aditivo |
| `excluir vendedor <nome> <telefone>` | gerente | soft-delete no banco, **efeito imediato na fila** |

**Sugestão de ordem:** começar pelo que é aditivo ou reversível (`inserir`, `pausar`, `despausar`) e deixar `excluir` para depois — apesar de ser soft-delete (`status = 'removido'`), o efeito na fila é instantâneo.

**Sobre filtro:** manter um punhado de filtros prontos e parar aí. Quem precisa de filtro de verdade tem o Dashboard, com data, origem, vendedor, status e busca por texto. O canal de comando **substitui o painel de administração, não o Dashboard** — ele é para a ação rápida de quem está no pátio com o celular na mão.

## 9. Com IA ou sem IA

A IA resolve **um** dos dois problemas, e é importante não confundi-los:

| Problema | IA resolve? |
|---|---|
| Lembrar o formato (`pausa nome numero` ou `pausar numero nome`?) | **sim** |
| Ambiguidade (dois João) | **não** — "pausa o joão" continua tendo dois João |

Ou seja: a máquina de desambiguação precisa existir nos dois cenários. A IA é conveniência em cima de um mecanismo que será construído de qualquer jeito.

### O custo real da IA aqui não é a chamada da API

É que **ela quebra o padrão eco-e-reenvio**. Com IA, a pessoa não vai reenviar o comando formatado — vai responder "isso", "pode", "sim". E aí o sistema precisa lembrar o que estava pendente, com expiração e tratamento de quem responde outra coisa no meio.

**A IA custa exatamente a tabela de estado que o desenho sem IA consegue evitar.** Isso não é argumento contra usar IA — é que ela decide a arquitetura, em vez de ser um enfeite barato adicionado no fim.

### Onde o risco é oposto ao da [Portaria](07-portaria-classificacao.md)

Na Portaria, o pior caso é rotular mal um lead que entra, e o desenho inteiro se apoia em **falhar aberto** — na dúvida, distribui. É seguro porque o custo é trinta segundos de atenção de um vendedor.

Aqui o pior caso é **executar escrita destrutiva na pessoa errada**, e falhar aberto não está disponível. Precisa ser o contrário: **falhar fechado**, com eco e confirmação antes de executar.

O mesmo princípio já está escrito no docstring de [`pages/5_Triagem.py`](../../../pages/5_Triagem.py): cards e não `data_editor`, porque cada ação ali dispara efeito real e o auto-save promoveria lead numa edição acidental.

### Uma simplificação a favor da IA

Como o papel já foi resolvido pelo `identificar_remetente` antes do roteador, **a IA nunca veria mensagem de cliente**. O problema difícil — "isto é comando ou é um cliente falando?" — já está resolvido pelo roteamento. O escopo da IA aqui é muito mais estreito e mais seguro que o da Portaria.

### Recomendação

Construir **sem IA primeiro**: comandos com eco-e-reenvio, só gerente para escrita, só aditivo e reversível no começo.

A IA entra depois **como camada na frente das mesmas ferramentas**, traduzindo linguagem natural para um vocabulário que já funciona. A propriedade que isso dá: **se a IA cair, os comandos digitados continuam funcionando.** É o mesmo padrão sombra-antes-do-corte da Portaria.

Para a Renato Motors — quatro vendedores e um gerente usando todo dia — `menu` mais comando curto ganha da IA em tudo que importa: mais rápido, de graça, determinístico, e funciona com a API fora. A IA passa a pagar na loja nº 10, onde há gente usando de vez em quando que não vai ler menu nenhum, e o custo de onboarding vira o problema.

## 10. O que isto resolve da Fase C, e o que não resolve

**Resolve** a administração **da loja**: vendedor e gerente. É o que o lojista usa toda semana.

**Não resolve** a administração **do sistema**:

- criar loja nova — e há um ovo-e-galinha: loja nova não tem gerente cadastrado, logo não existe número autorizado para mandar o comando;
- gerar e rotacionar `codigo_acesso` — o plano registra que hoje ele é só lido, nunca escrito, e isto não muda;
- papel de dono do produto, separado do papel de loja.

**Decisão do dono (2026-09-25):** criar loja nova será feito manualmente, por ele, em sessão com IA usando a `service_role`.

Isso funciona bem em 1 a 3 lojas e é imbatível em velocidade. Duas consequências, registradas sem enfeite:

1. não sobra rastro de auditoria da criação da loja além do histórico de conversa;
2. o `codigo_acesso` continua sem mecanismo de geração ou rotação.

Ou seja: **a Fase C não acabou — ela virou processo manual**, que é escolha legítima com limite conhecido. O que sobra dela é justamente a parte que é sobre *vender* o sistema.

## 11. Decisões pendentes

- [ ] Separar `vendedor` de `gerente` no roteamento — onde exatamente, `Não É Lead` ou um nó novo depois dele?
- [ ] Assinatura nova de `comando_leads` / `comando_status` para escopar por pessoa (migration)
- [ ] Onde vive o registro de comandos: tabela no Supabase ou arquivo no repo?
- [ ] `excluir` entra na primeira leva ou fica para depois?
- [ ] Toda escrita por comando grava em `atividades`? (`registrar_atividade` já existe e daria o "quem fez o quê" de graça)
- [ ] Confirmação expira? No padrão eco-e-reenvio não precisa — mas se a IA entrar, precisa.

## Histórico

- **2026-10-10 (noite, depois)** — **Regra do dono: só gerente ativo ou vendedor ativo fala com o sistema.** Quem não é (vendedor pausado/removido, gerente desativado) não recebe nada — nem menu, nem erro, nem pergunta da IA — e não gasta IA. Gerente que também é vendedor pausado continua gerente.
- **2026-10-10 (noite)** — **IA em produção.** A seção 9 ("construir sem IA primeiro; IA como camada na frente") foi seguida: a IA devolve `{acao, nome, telefone, pergunta}` (lista fechada, ideia de "ferramentas com schema"), `executar_comando_ia` aplica as travas, `esclarecer` pergunta quando falta algo, confirmação por "sim" com pendência de 5 min (`comandos_pendentes`) resolve o problema do eco-e-reenvio apontado na seção 9. Avaliação: 48/48 duas vezes, zero erro perigoso. Limite de custo: `reservar_ia` + `ia_uso`. Ver RUNBOOK.
- **2026-10-10 (fim da tarde)** — **n8n ligado** (`5b786a18` → `7bffe0f1`, ver RUNBOOK). Testado do celular: `menu` e `listar vendedores` pela função nova, `status` pelo legado. Escrita (`inserir`/`pausar`/`excluir` com confirmação) ainda não testada pelo WhatsApp. Próximo passo pedido pelo dono: **IA na frente** (traduz frase livre para o comando) e confirmação por "sim" com ação pendente no banco — ver seção 9.
- **2026-10-10 (tarde)** — **`FIX` APLICADO EM PRODUÇÃO** com `sql/comandos_whatsapp/aplicar_producao.py` (uma transação, API de gestão do Supabase). Conferido: 7/7 funções, 2/2 índices, `executar_comando` executável só por `service_role` (`anon`/`authenticated` negados). Testes de leitura em produção: `menu` e `listar vendedores` pelo gerente Elton responderam certo; `meus leads` pelo vendedor Giu trouxe só os leads dela; vendedor tentando `inserir` recebeu `negado`. **O n8n ainda não chama a função** — nada mudou no fluxo de leads. Desfazer: `aplicar_producao.py --reverter`.
- **2026-10-10** — testes refeitos sobre o **schema real de produção** (gerado do catálogo, `teste_schema_producao.sql`): todos passam, `FIX` idempotente, `ROLLBACK` remove funções e índices sem tocar dados. Achado: produção já tem `uk_vendedores_loja_whatsapp` (loja + telefone exato) **incluindo removidos** — o telefone de quem saiu continua ocupado. O `inserir` agora recusa já no eco e sugere `reativar`. Nenhuma das 7 funções do `FIX` existe hoje em produção (nada é sobrescrito). Ainda não aplicado.
- **2026-10-09 (noite)** — **SQL escrito e testado localmente; NÃO aplicado em produção, n8n NÃO alterado.** Arquivos em [`sql/comandos_whatsapp/`](../../../sql/comandos_whatsapp/): `FIX_comandos_whatsapp.sql`, `ROLLBACK_comandos_whatsapp.sql`, e os testes (`teste_schema_minimo.sql`, `teste_comandos_whatsapp.sql`). Testado em Postgres 17 descartável (Docker) sobre um **schema reconstruído** das colunas observadas; o DDL real de produção não foi lido, então CHECKs e triggers reais não foram exercitados. O que a função faz: `executar_comando(loja_id, remetente, texto)` devolve `{papel, acao, resposta}`; gerente tem `listar vendedores`, `inserir vendedor`, `pausar`, `reativar` (alias `despausar`) e `excluir`; vendedor tem `meus leads`/`leads` e `status` pessoais; gerente digitando `status`/`leads` recebe `acao: legado` (o n8n continua no caminho antigo). Escrita só com eco-e-reenvio (`confirmar ...` + telefone completo). Nome único por loja sem regex (`normalizar_nome` via `translate`), telefone único entre vendedores não removidos, último vendedor ativo protegido, `reativar` aceita também vendedor `removido` (diverge do que a UI trata como definitivo). `executar_comando` revoga `anon` e `authenticated`. Cadastrado em produção o gerente Elton (`5519999746219`; trocado em 10/10 para `5519996977453`, o mesmo número que recebe os alertas).

- **2026-10-09** — decisões do dono para a primeira versão: **gerente tem acesso total; vendedor vê somente o que é referente a ele** (por exemplo, seus leads). Ainda nada implementado. Proposta de desenho para a implementação: a lógica fica numa RPC do Postgres (`loja_id`, remetente e texto entram; a resposta sai pronta) e o n8n só repassa e responde, para reduzir a mudança no workflow de produção. Achados da auditoria que afetam este spec: (1) há um **segundo caminho de comando** no n8n, o nó `Switch` por clique no botão "Acessar leads", que este documento não descreve; (2) só há **1 gerente ativo**, então "não remover o último gerente" é regra necessária; (3) o número do dono provavelmente **não** está cadastrado como gerente; (4) `identificar_remetente` é executável por `anon`, e as RPCs novas devem revogar `anon`; (5) um mesmo número nas tabelas de gerente e vendedor devolve um único papel em `identificar_remetente` — comportamento ainda não verificado. Ver [plano-multiloja](../../plano-multiloja.md), seção de 2026-10-09.
- **2026-09-25** — versão inicial, a partir de conversa de desenho. Nada implementado. Levantado que `comando_leads`/`comando_status` não recebem o remetente, e que por isso vendedor hoje vê os leads da loja inteira.
