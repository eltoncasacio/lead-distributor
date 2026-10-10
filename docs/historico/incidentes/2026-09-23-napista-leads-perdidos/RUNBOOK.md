# Runbook — leads perdidos em silêncio (Renato Motors)

> Incidente do lado **n8n**, não SQL. Nenhuma função do Postgres é alterada. `distribuir_lead` e a tabela `leads` ficam intocados.

## Sintoma

14 de 15 mensagens do NaPista por WhatsApp não viraram lead entre 2026-09-09 e 2026-09-23, sem erro e sem alerta. Execuções marcadas como `success`. Descoberto em 2026-09-22 a partir de um vídeo do lojista mostrando a mensagem chegando no aparelho.

## Causa raiz

Três defeitos somados, todos na camada de entrada:

1. **`Prepara Dados NaPista` descarta o telefone que o próprio parser extraiu.** Usa `{{ $('Normaliza Dados').item.json.remetenteNumero }}`, que numa mensagem repassada pela plataforma é o número da NaPista (`551131361712`), não do cliente. Com `anuncio` também vazio, a chave de dedup `(numero_cliente, loja_id, anuncio)` fica constante e tudo depois do primeiro lead vira duplicata. O nó irmão `Prepara Dados icarros` já faz certo (`{{ $json.telefone }}`) — é uma divergência de um campo.
2. **`Duplicado de Plataforma?` e `Vendedor Encontrado?` voltam ao `Loop Over Items` sem avisar ninguém.** O lead some e a execução segue `success`.
3. **`Separar Leads NaPista` lê `templateMessage.hydratedTemplate.hydratedContentText`**, caminho `undefined` em `placeholderMessage` (9 de 14 mensagens, efeito de 62 quedas de sessão da Evolution em 14 dias). O nó tem `onError: continueRegularOutput`, então emite o **objeto de erro como dado** para o resto do fluxo.

Agravante independente, **no template de WhatsApp**: a NaPista trocou o template repassado por WhatsApp por um sem telefone do cliente, só com link para o portal. Por esse canal, sem telefone não há para quem distribuir.

> ⚠️ **Correção de diagnóstico (2026-09-23, noite).** A versão anterior deste runbook afirmava que a NaPista *"cortou o canal de e-mail em 2026-08-14"* e que nenhum canal automatizado trazia mais o telefone. **As duas afirmações estão erradas.** Ver [Canal de e-mail: caixa errada, não canal cortado](#canal-de-e-mail-caixa-errada-não-canal-cortado).

## Canal de e-mail: caixa errada, não canal cortado

Descoberto em **2026-09-23 à noite**, por vídeo do gerente mostrando a caixa de entrada ao vivo.

**O e-mail da NaPista nunca parou.** Ele passou a ser entregue em **`comercialrenatomotors@hotmail.com`** (Outlook/Hotmail), enquanto o `Gmail Trigger` do n8n lê uma caixa **Gmail** com o filtro `from:@napista.com.br`. Um Gmail Trigger não alcança uma caixa Hotmail — por isso o n8n não vê nenhum e-mail desde 14/08. **Não era spam.**

Evidência no vídeo (busca por "napista" em todas as pastas da conta Hotmail):

- vários leads na **Caixa de Entrada**, nenhum no Lixo Eletrônico — o mais recente em **23/09 às 18:11** (Ezequiel Batista dos Santos);
- um e-mail *"Redefina sua senha | NaPista"* de **17/08/2026** já nessa caixa. Como o fluxo para o Gmail secou em **14/08**, a janela 14–17/08 é quando o e-mail de notificação da conta NaPista passou a ser o Hotmail.

**O telefone do cliente continua vindo por e-mail.** O corpo do e-mail aberto no vídeo traz `Dados do cliente` com nome, telefone, e-mail, CPF, botão "Conversar via whatsapp", `Mensagem` e `Veículo de interesse` — exatamente o formato que o nó `Extrai Dados NaPista` em produção já parseia. **Nenhuma mudança de código é necessária** para voltar a receber esses leads com telefone.

### Verificação na tela do n8n (2026-09-23, noite)

Confirmado pela UI, com `Fetch Test Event` no nó `Gmail Trigger` (executa **só o nó**, não o workflow):

- **A conta é `leadsrenatomotors@gmail.com`** — `"to": "To: leadsrenatomotors@gmail.com"` e `"delivered-to": "leadsrenatomotors@gmail.com"` no cabeçalho do item retornado.
- **O último e-mail da NaPista nessa caixa é de 14/08/2026**, `Fri, 14 Aug 2026 13:09:52 +0000` (10:09 BRT). Assunto: *"F. R. (cliente) está interessado na sua oferta."*, de `NaPista <noreply@napista.com.br>` via `mandrillapp.com`. Ou seja: o corte no Gmail é exatamente 14/08, e desde então **zero**.
- O item ainda está com labels `INBOX`, `UNREAD`, `CATEGORY_PROMOTIONS`. A aba Promoções **não** atrapalha o trigger (ele busca por query, não por aba) — registrado só para não virar suspeita falsa depois.
- Configuração do nó: `Search: from:@napista.com.br`, `Every Minute`, `Message Received`, `Simplify` desligado.

A credencial (`Gmail account`, Gmail OAuth2) **não exibe o endereço em nenhuma aba da UI** — só "Account connected". O único jeito de ler a conta é pelo cabeçalho de um item retornado pelo trigger.

⚠️ A retenção de execuções desta instância cobre poucos dias (em 23/09 a lista mais antiga era de **21/09**). Não adianta procurar execução de agosto.

### Opções de correção

| | O que fazer | Custo | Risco |
|---|---|---|---|
| **A** (recomendada) | Na Área do lojista da NaPista, apontar o e-mail de notificação de volta para o Gmail que o n8n lê | nenhum código | baixo |
| **B** | Regra de encaminhamento automático Hotmail → Gmail | nenhum código | o encaminhamento do Outlook costuma reescrever o `From`, quebrando o filtro `from:@napista.com.br` |
| **C** | Trocar o `Gmail Trigger` por um trigger Microsoft Outlook na conta Hotmail | OAuth novo + religar o ramo | médio |

**Decisão do dono (2026-09-23, noite): tentar a A primeiro.**

Levantamento feito para a C, caso a A não seja poss­vel:
- A instância tem **8 credenciais, nenhuma da Microsoft** — começaria do zero.
- É **self-hosted**, então OAuth exige app registrado pelo dono (a credencial Gmail já usa Client ID próprio `463630093033-...`). Para Outlook: registro no Azure/Entra ID, redirect `https://n8n.yavoh.cloud/rest/oauth2-credential/callback`, escopos `Mail.Read` + `offline_access`.
- **Dois nós quebram** com o formato do Outlook: `Origem NaPista` compara `$json.from.value[0].name` (no Outlook é `from.emailAddress.name`), e `Extrai Dados NaPista` lê `body` como string (no Outlook é objeto `{contentType, content}` — precisa `body.content`).
- O nó IMAP genérico dispensaria o Azure, mas a Microsoft desligou autenticação básica (senha) para IMAP em contas pessoais Outlook.com — **não verificado nesta conta**, e testar custa ~5 min.

### Recuperação manual

Os leads que caíram no Hotmail desde 14/08 **nunca viraram lead** no sistema. Cada e-mail contém nome e telefone, então são recuperáveis à mão. Volume ainda não contado.


## Estado da aplicação

| Passo | Estado | Quando | versionId |
|---|---|---|---|
| 0 · ligar alerta de conexão | **aplicado** | 2026-09-23 16:27 BRT | `e14f1ff7-aa49-4989-aaa7-b870a49f0ae8` → `e43645a3-2cda-4db7-9f40-6b6b969c1cdb` |
| 1 · alerta de lead não distribuído | **aplicado** | 2026-09-23 17:10 BRT | `e43645a3-2cda-4db7-9f40-6b6b969c1cdb` → `9c1f603f-7e23-4d36-84dc-3da803c8c597` |
| 2A · reescrever o parser | **aplicado** | 2026-09-23 17:23 BRT | `9c1f603f-7e23-4d36-84dc-3da803c8c597` → `07f90179-48bd-464b-bd71-9aeeff4ac4ac` |
| 2B · campos + guarda | **aplicado** | 2026-09-23 17:30 BRT | `07f90179-48bd-464b-bd71-9aeeff4ac4ac` → `f4119765-69bd-40a1-8dd8-68dc5bce70b2` |
| 3 · migration `mensagens_recebidas` | **aplicada pelo dono** | 2026-09-23 ~17:55 BRT | SQL Editor do Supabase |
| 3 · nó `Registrar Mensagem` | **aplicado** | 2026-09-23 18:01 BRT | `f4119765-69bd-40a1-8dd8-68dc5bce70b2` → `ff4a9650-31ff-495c-a936-02f83a8a9949` |
| 3B · registrar o que a guarda barra | **aplicado** | 2026-09-23 18:22 BRT | `ff4a9650-31ff-495c-a936-02f83a8a9949` → `1570febe-d773-44ff-94be-0297477541a1` |
| 5 · tela de triagem | **aplicada e aprovada** | 2026-09-23 18:18 BRT | commit `f585f89` |
| 2C · link da oportunidade no alerta | **aplicado** | 2026-09-23 18:38 BRT | `1570febe` → `a5ea58b9-9462-44a4-ae4c-87fefdfc5906` |
| 2C' · destino de volta ao dono, para teste | **aplicado** | 2026-09-23 18:44 BRT | `a5ea58b9` → `7ac9a10d-46e4-4563-98a1-512477493a6f` |

### Destino dos alertas (2C)

Decisão do dono: o alerta de lead do NaPista vai para o **gerente**, que abre o link e se vira.

**Estado atual: todos os alertas vão para o dono (`5519996977453`)**, por escolha dele, para observar o comportamento antes de repassar ao gerente.

| Alerta | Destino hoje | Destino pretendido |
|---|---|---|
| `Alerta Lead Nao Distribuido` | dono `5519996977453` | gerente `5519XXXXXXXXX` |
| `Alerta NaPista Sem Telefone` | dono `5519996977453` | gerente `5519XXXXXXXXX` |
| `Enviar Alerta Conexão` | dono | dono — falha de infraestrutura |
| `Alerta Loja Nao Encontrada` | dono | dono — erro de configuração |

Para repassar os dois primeiros ao gerente, trocar `number: '5519996977453'` por `number: '5519XXXXXXXXX'` no `jsonBody` desses dois nós. O link e o rótulo do telefone são independentes do destino e já estão no lugar.

O link da oportunidade **não está no texto da mensagem** — fica em `hydratedButtons[0].urlButton.url`. Sem ele, o gerente receberia nome e veículo e teria de caçar a oportunidade no portal. Foi acrescentado ao alerta.

O rótulo do telefone foi escrito para não induzir erro: quando o número é o da plataforma, a mensagem diz `Telefone do cliente: NAO VEIO (o numero acima e da plataforma)` em vez de mostrá-lo como se fosse do cliente — senão o gerente liga para a central do NaPista.

> **Débito conhecido:** os números de destino são fixos no nó, como já era o caso do alerta de conexão. Com mais de uma loja isso não escala — é o mesmo débito de onboarding manual já registrado na auditoria comercial de 2026-09-11.

### Por que não virou lead

O dono considerou criar o lead mesmo sem telefone, para o vendedor abrir o link. A investigação mostrou que isso exigiria usar o número da plataforma como identidade do cliente, com dois efeitos: o campo `numero_cliente` passaria a mentir, e o Passo 2 do `distribuir_lead` poderia grudar todos os leads do NaPista num vendedor só.

Evidência medida: os 2 leads históricos gravados com o número do NaPista foram para vendedores **diferentes** (Giu em 06/04, André em 24/06, ambos ativos), e 16 de 82 clientes com mais de um lead trocaram de vendedor. Ou seja, a amarração é mais fraca do que a spec afirma — mas a regra exata está no Postgres e não foi possível ler o código-fonte da função. Sem essa certeza, o dono optou por manter alerta em vez de lead.

### Furo encontrado ao responder uma pergunta do dono (3B)

Ao traçar o caminho de uma mensagem NaPista para explicar quando o alerta dispara, ficou visível que `Registrar Mensagem` pende de `Normalizar Saída Lead`, **mas a guarda `Telefone do Cliente?` barra antes disso**. A mensagem sem telefone do cliente — exatamente a que precisa de triagem — gerava alerta e **não** ficava registrada. A tela de triagem ficaria vazia para sempre para o caso que a motivou.

Correção: a saída falsa da guarda passou a alimentar `Registrar Mensagem` além do alerta. Uma conexão.

Lição registrada: um ramo lateral pendurado no caminho feliz não cobre o caminho infeliz. Ao inserir uma guarda **antes** de um ponto de registro, o registro precisa ser reconectado nos dois lados.

### Por que o registro é ramo lateral, e não um passo do caminho

Um nó HTTP Request **substitui o item pela resposta da chamada**. Inserido entre `Normalizar Saída Lead` e `Loop Over Items`, ele entregaria ao `Distribuir Lead` o uuid devolvido pela RPC em vez do item com `telefone`, `anuncio` e `lojaId` — quebraria a distribuição inteira, de todas as origens.

A solução é uma segunda conexão da mesma saída: os dois ramos recebem o mesmo item, rodam em paralelo, e o de registro é terminal. O caminho de distribuição fica byte a byte igual.

Consequência aceita: o n8n registra a chegada, mas **não carimba o desfecho** (`decisao`, `lead_id`), porque carimbar depois exigiria outro nó HTTP no caminho, com o mesmo problema. O alarme "chegou e não virou nada" da Fase 7 não precisa disso: compara contagem de `mensagens_recebidas` contra `leads` por origem.

### Limitações conhecidas declaradas

- O parser do NaPista devolve **um** item por mensagem. Hoje está certo, mas o iCarros prova que uma mensagem pode trazer **N leads** numa lista numerada. Se a NaPista adotar esse formato, o parser pega só o primeiro.
- O `mensagem_externa_id` do registro já leva o índice do item justamente para suportar N leads por mensagem sem que o índice único os colapse.

### Regressão evitada na simulação da 2B

O plano original trocava `telefone` por `{{ $json.telefone }}` puro. **Isso quebraria o único caminho NaPista que ainda funciona**: quando o cliente manda o link do anúncio (23 leads no banco, o caso da Rosana), o parser não acha telefone no texto — mas o remetente **é** o cliente. O valor viraria `null` e a guarda barraria um lead bom.

O valor aplicado é `{{ $json.telefone || $('Normaliza Dados').item.json.remetenteNumero }}`. O par fallback + guarda cobre os dois casos:

| Caso | Parser | Remetente | Telefone final | Decisão |
|---|---|---|---|---|
| cliente manda o link | — | cliente | cliente | **distribui** |
| template novo (Marcio) | — | NaPista | NaPista | alerta |
| template antigo `wa.me` | cliente | NaPista | **cliente** | **distribui** |
| `placeholderMessage` | — | NaPista | NaPista | alerta |

**Bloqueio de `comando_leads` resolvido em 2026-09-23**, sem precisar de acesso SQL: a RPC foi chamada em modo leitura e devolve `anuncio, horario, nome_cliente, origem, vendedor` — **não devolve `mensagem_original`**. Trocar `p_mensagem_original` não afeta o que vendedor ou gerente leem pelo WhatsApp. Efeito colateral positivo: a RPC **devolve `anuncio`**, hoje vazio no NaPista, que passará a mostrar o veículo no comando `leads`.

A Fase 2 foi dividida porque as partes não podem ir juntas nem sozinhas na ordem errada: trocar `telefone` para o valor parseado **sem** a guarda mandaria `null` ao `distribuir_lead` no template atual da NaPista, que não traz telefone. E a guarda depende de um parser confiável. Logo: 2A (parser) primeiro, sozinho e sem mudança de comportamento; 2B (campos + guarda) depois, obrigatoriamente juntos.

Os Passos 0 e 1 foram aplicados **fora da janela 03h–05h**, por decisão do dono. Exposição medida: ~0,35 lead/hora às 16h, o que põe a chance de perda na janela de 1s do save em ~0,01%. Conferido depois das duas aplicações: nenhuma execução entre a última anterior (id 8863, 15:17 BRT) e as mudanças — nada se perdeu. Grafo íntegro: 64 nós, `active: true`, os três caminhos bons (`Duplicado[não duplicado]`, `Vendedor[encontrado]`, `Loja[encontrada]`) apontando para os mesmos destinos de antes.

O Passo 1 criou **dois** nós, não um: `Alerta Lead Nao Distribuido` (devolve ao `Loop Over Items`, continuando a iteração) e `Alerta Loja Nao Encontrada` (terminal). Ligar a saída de `Loja Encontrada?` no mesmo nó empurraria um item para dentro do `splitInBatches` e poderia acabar distribuído — seria um bug pior que o original.

Critérios de aceite e checklist de cada passo: [ACEITE.md](ACEITE.md).

## Complemento de 2026-10-05: o alerta "sem telefone" que chegou vazio

Às 18:11 BRT chegou o alerta `Lead NaPista sem telefone do cliente` com cliente, veículo e mensagem em branco, e sem link. Investigado lendo a execução `9083` pela API pública do n8n (somente leitura).

**Causa:** o evento que chegou ao webhook não era o template da NaPista. Era `messageType: placeholderMessage` (`placeholderMessage.type: 0`) — o aviso do WhatsApp de que há uma mensagem, mas o aparelho conectado não conseguiu abrir o conteúdo. Não há texto, nome, veículo nem botão em nenhum campo do payload. O conteúdo, com o botão "Ver detalhes", só existiu no celular.

**Evidência:**

| Execução | Horário (BRT) | Tipo |
|---|---|---|
| `9076` | 13:24 | `templateMessage` — conteúdo completo (lead com telefone) |
| `9077` | 14:36 | `placeholderMessage` |
| `9082` | 18:09 | `placeholderMessage` |
| `9083` | 18:11 | `placeholderMessage` |

Nas execuções `9078` a `9087` não houve segunda entrega do mesmo `key.id` com o conteúdo real. Houve 4 eventos `connection.update` no dia (15:50, 17:06, 18:21 e 19:24 BRT).

**O que isto corrige no entendimento anterior:** o alerta do 2C lê o link em `hydratedButtons[0].urlButton.url`. Isso continua certo para `templateMessage`. Para `placeholderMessage` **não existe link a ler**, então não é falha do nó do alerta nem do formato do botão. É perda na camada Evolution/WhatsApp.

**Não confirmado:** a relação entre as quedas de conexão e os placeholders é hipótese (coincidem no dia, mas não foi medida a correlação). Também não foi apurado se o conteúdo chega depois por outro evento.

**Efeito prático:** o lead só pode ser recuperado abrindo o botão no celular. A linha de `mensagens_recebidas` é gravada com `texto` e `payload_bruto` vazios e `telefone_extraido` igual ao número da plataforma, por isso aparece na Triagem sem nenhuma informação útil.

## Complemento de 2026-10-09: sessão da Evolution derrubada por ~48 h

**Sintoma:** nenhum lead nem mensagem entrou depois de 06/10 (último lead 19:19 UTC) e 07/10 (última mensagem 15:28 UTC). Detectado pela auditoria (`auditoria_producao.py`), não por alerta.

**Linha do tempo (UTC):**

| Quando | O quê |
|---|---|
| 07/10 22:18 | Última mensagem processada (`9135`) |
| 07/10 22:29 | Execução `9136`: `connection.update` com `state: close` e `statusReason: 401` — sessão desligada do aparelho. Última execução até a reconexão |
| 09/10 ~20:45 | Reconexão: código de pareamento gerado com a chave **da instância** (`lojas.evolution_api_key`), digitado no iPhone da loja. Estado passou para `open`; webhook (`MESSAGES_UPSERT`, `CONNECTION_UPDATE`) continuava configurado |
| 09/10 20:50 | Mensagem de teste: execução `9140`, registrada em `mensagens_recebidas` e **distribuída** (lead criado no mesmo segundo) |

**Causa: troca de celular do dono da loja (mesmo número, agora iPhone), confirmada pelo dono em 2026-10-09.** Registrar o número num aparelho novo desvincula os aparelhos conectados, e a Evolution é um deles; isso casa com o erro 401 e com a ausência de tentativa de reconexão. A causa **não tem relação com o NaPista nem com qualquer portal de leads**. Falta apenas a **data exata** da troca, para casar com 07/10 19:29 (Brasília). Os eventos de 05/10 mostram a conexão oscilando (`connecting`/`open`/`close` várias vezes no dia), então pode ter havido instabilidade anterior.

**Por que ninguém foi avisado:** o nó `Montar Alerta` rodou na execução `9136` e montou o texto "DESCONECTADO", mas no workflow ao vivo ele **não tem conexão de saída** (`main: [[]]`) — o Passo 0 deste runbook não está aplicado. Mesmo ligado, o envio sairia pela própria instância que caiu e não seria entregue (limitação já registrada em [fase-a-tirar-hardcodes-n8n.md](../../../dev/fase-a-tirar-hardcodes-n8n.md)).

**Impacto:** leads dos portais e clientes que escreveram entre 07/10 22:29 UTC e 09/10 ~20:45 UTC **não chegaram ao sistema**. As mensagens devem estar no celular da loja. **Recuperação ainda não feita.**

**Efeito colateral do teste:** a mensagem de teste gerou um lead real, distribuído a um vendedor, com `status_lead = negociando`. Deve ser marcado como "sem interesse" no Dashboard.

**Aprendizados:**
- A chave global da Evolution não é necessária para reconectar: a chave da instância, guardada em `lojas`, aceita `/instance/connect/{instância}?number=...` e devolve o `pairingCode`.
- O sistema depende de o celular do dono continuar vinculado. Com mais lojas, cada troca de aparelho vira parada silenciosa. Ver "A Evolution vira o maior custo de suporte" no [plano-multiloja](../../../plano-multiloja.md).

## Fase A1 (2026-10-10): chave do Supabase sai do workflow

Aplicado em 2026-10-10 10:58 BRT, fora da janela 03h–05h, **por decisão explícita do dono** (a trava de horário foi retirada do script a pedido dele). Script: [`docs/dev/fase-a/aplicar_a1_credencial_supabase.py`](../../../dev/fase-a/aplicar_a1_credencial_supabase.py).

| | `versionId` |
|---|---|
| antes | `baa01c3e-ac06-42a8-b768-bf7ed62179ea` |
| depois | `81c399b7-0bbe-4055-bae6-84983af6b00e` |

**O que mudou:** criada a credencial n8n `Supabase Leads service_role` (tipo Custom Auth, id `4jtWugcIUkX179st`), que injeta `apikey` e `Authorization`. Os 9 nós HTTP que falam com o Supabase passaram a usá-la. O campo `supabaseKey` saiu de 10 nós Set e de 2 nós Code (`Normaliza Dados Mobiauto`/`Webmotors`). `supabaseUrl` ficou. A chave **não foi trocada** — continua a mesma do `.env` do Dashboard.

**Como foi verificado antes:** workflow descartável criado pela API leu `lojas` e chamou `comando_status` usando a credencial (execução `9152`, sucesso, chave ausente dos dados da execução) e foi apagado. Travas do script: a chave não aparece em nenhum nó, não sobra `supabaseKey`, nenhum nó com URL do Supabase sem a credencial — conferidas na simulação e de novo no que ficou gravado.

**Verificado depois:** execução `9155` (10:59 BRT, comando `leads` de gerente) passou por `Identificar Loja`, `Identificar Remetente` e `Buscar Leads` com a credencial, sucesso, chave ausente dos dados. **Ainda não exercitados:** `Distribuir Lead`, `Registrar Mensagem`, `Buscar Mensagens Prontas` e os ramos Mobiauto/Webmotors — mesma configuração, conferir no primeiro lead real (ver ACEITE).

**Confirmado com leads reais:** execuções `9162`–`9164`, `9168` e `9169` (10/10, 11:27–11:40 BRT) passaram por `Distribuir Lead` e `Registrar Mensagem` com a credencial, sucesso, chave ausente dos dados.

**Rollback:** `python3 aplicar_a1_credencial_supabase.py --reverter` regrava o snapshot salvo em `.n8n_backups/` (fora do git, contém a chave). Só funciona enquanto a chave antiga não for revogada. **Desatualizado desde 10/10 11:40:** o workflow foi editado depois pela tela (`81c399b7` → `80947913`, autor não registrado) e de novo para desligar o alerta abaixo — reverter para o snapshot da A1 desfaria essas edições. Para voltar, usar o snapshot mais recente em `.n8n_backups/`.

**Ainda falta:** (1) rotacionar a chave — atualizar a credencial no n8n e o `.env` do Dashboard, depois revogar a antiga; (2) as execuções anteriores a esta versão continuam com a chave gravada nos dados — perde o valor com a rotação.

## Alerta "Lead NaPista sem telefone" desligado (2026-10-10)

**Decisão do dono, 2026-10-10:** esse alerta não vai mais para ninguém. Nó `Alerta NaPista Sem Telefone` marcado como desativado (`disabled: true`), não apagado — religar é desmarcar.

| | `versionId` |
|---|---|
| antes | `80947913-aedf-421c-86f7-e12a2f990046` |
| depois | `5b786a18-b4e0-4f9b-821e-2efa106a7306` |

**O que continua acontecendo:** o mesmo ramo também leva a `Registrar Mensagem`, que segue ligado. A mensagem do NaPista sem telefone continua gravada em `mensagens_recebidas` e aparece na **Triagem** — só deixa de haver aviso por WhatsApp. Na prática esse alerta disparava sobretudo com `placeholderMessage` (sem conteúdo, ver complemento de 05/10), em que não havia nada útil para mandar.

**Consequência a saber:** sem o alerta, um lead do NaPista sem telefone só é visto por quem abrir a Triagem. O alerta `Lead nao distribuido` não foi alterado.

Snapshot anterior: `.n8n_backups/workflow_Qj200sqS9544ao3d_80947913-…_20261010-114042.json`.

## Arquivos

- `FIX_mensagens_recebidas.sql` / `ROLLBACK_mensagens_recebidas.sql` — Fase 3. **Não aplicados**: DDL não passa pela PostgREST, tem de ser rodado no SQL Editor do Supabase. Não tocam `leads` nem `distribuir_lead`.
- `aplicar_fase0.py`, `aplicar_fase1.py`, `aplicar_fase2a.py`, `aplicar_fase2b.py` — todos com simulação por padrão, `--aplicar`, `--reverter` e recusa fora da janela sem `--fora-da-janela`.
- `ROLLBACK_workflow_n8n.json` — export do workflow em `versionId e14f1ff7-aa49-4989-aaa7-b870a49f0ae8` (62 nós, `updatedAt 2026-09-22T22:46:46Z`). **Segredos redigidos** (14 ocorrências): serve como registro do estado anterior, **não** para restaurar. Restaurar este arquivo apagaria as credenciais embutidas nos nós. **Removido do git em 2026-10-10**: a redação de 23/09 deixou passar a chave da Evolution da loja, e o `pinData` tinha nome e dados de clientes reais. A cópia fica fora do git, em `.n8n_backups/ROLLBACK_workflow_n8n_e14f1ff7_2026-09-23.json`, só na máquina do dono.

O rollback de verdade é a **version history do próprio n8n**: restaurar `e14f1ff7-aa49-4989-aaa7-b870a49f0ae8`, que preserva as credenciais.

## Aplicar

**Janela obrigatória: 03h–05h BRT.** Distribuição real por hora põe 04h com 1 lead em sete meses, contra 127 às 23h. Salvar um workflow ativo re-registra o webhook e abre uma janela de <1s em que uma mensagem receberia erro **sem criar execução** — é o único ponto sem rastro em todo o sistema.

Uma mudança por vez. Entre uma e a seguinte, esperar ~20 mensagens limpas.

### Passo 0 — ligar o alerta de conexão (2 minutos)

`Montar Alerta` tem saída vazia e `Enviar Alerta Conexão` não recebe de ninguém: o alerta de queda do WhatsApp **nunca disparou**, ao contrário do que `docs/specs/tecnica/03-workflow-n8n.md` afirmava.

Conectar `Montar Alerta [saída 0]` → `Enviar Alerta Conexão`.

Efeito esperado: ~4 mensagens por dia para o número do operador (62 quedas + 62 reconexões em 14 dias). O ruído é o dado — mede a instabilidade da Evolution.

Blast radius: nenhum. O ramo `É Mensagem? = não` é paralelo ao caminho de distribuição.

### Passo 1 — alertar quando um lead não é distribuído

Nó novo `Alerta Lead Nao Distribuido`, HTTP Request clonado de `Enviar Alerta Conexão` (mesmo endpoint `sendText` da Evolution, mesmo destino), **obrigatoriamente com `onError: continueRegularOutput`**.

> Sem esse `onError`, uma falha de alerta derruba a execução e passa a perder leads que hoje funcionam. Seria trocar um bug silencioso por uma queda geral.

Inserir **entre** o nó e seu destino atual, preservando a semântica do loop:

| Inserir em | Destino hoje | Passa a ser |
|---|---|---|
| `Duplicado de Plataforma?` saída 0 (true) | `Loop Over Items` | alerta → `Loop Over Items` |
| `Vendedor Encontrado?` saída 1 (false) | `Loop Over Items` | alerta → `Loop Over Items` |
| `Loja Encontrada?` saída 1 (false) | *nada* | alerta |

Corpo: origem, número do remetente, 200 primeiros caracteres de `mensagemTexto`, `duplicado`, `lead_id`, timestamp, URL da execução.

Esperar 1–2 semanas de ruído: a saída 0 de `Duplicado de Plataforma?` também dispara em repetição legítima de cliente. Esse volume é a medição da taxa real de duplicata, que hoje não existe.

### Passo 2 — causa raiz

Antes de aplicar, resolver a pendência: **`comando_leads` usa `mensagem_original`?** (`SELECT prosrc FROM pg_proc WHERE proname='comando_leads'`). Se usar, o terceiro item abaixo muda o que o vendedor lê pelo WhatsApp.

| Nó | Campo | Hoje | Vira |
|---|---|---|---|
| `Prepara Dados NaPista` | `telefone` | `{{ $('Normaliza Dados').item.json.remetenteNumero }}` | `{{ $json.telefone }}` |
| `Prepara Dados NaPista` | `anuncio` | `{{ $('Normaliza Dados').item.json.anuncio }}` | `{{ $json.anuncio \|\| $('Normaliza Dados').item.json.mensagemTexto }}` |
| `Distribuir Lead` | `p_mensagem_original` | `{{ $input.item.json.anuncio \|\| $input.item.json.mensagemTexto }}` | `{{ $input.item.json.mensagemTexto }}` |

Mais uma guarda antes de distribuir: telefone vazio **ou** com dígitos iguais a um número de plataforma conhecido (`551131361712` NaPista, `551130044558` iCarros) → não chamar `distribuir_lead`, alertar.

E reescrever `Separar Leads NaPista` para ler `$('Normaliza Dados').item.json.mensagemTexto` (que já tem cadeia de fallback) dentro de try/catch, devolvendo `{ parse_ok: true|false }` — nunca `[]`, nunca objeto de erro, e **sem** `onError: continueRegularOutput`.

> Efeito colateral a comunicar à loja: hoje todo lead NaPista entra com `anuncio = ""`, então o Passo 1 do `distribuir_lead` colapsa tudo num só. Depois da correção, anúncios diferentes do mesmo cliente viram leads separados — está correto, mas o volume aparente de NaPista vai subir.

## Verificar (logo após aplicar)

Conferência por execução, sem depender de ninguém olhar o celular:

```bash
curl -s -H "X-N8N-API-KEY: $N8N_KEY" \
  "https://n8n.yavoh.cloud/api/v1/executions?limit=50" 
```

Para cada execução desde a mudança, abrir com `?includeData=true` e confirmar que `Encaminhar ao Vendedor` aparece em `resultData.runData`. As que não aparecerem: extrair nome, telefone e mensagem do nó `Webhook` e entregar para trabalho manual.

Passo 0: provocar uma queda de conexão da Evolution e confirmar que a mensagem de alerta chega.

Passo 1: reenviar mensagem de um cliente existente para o mesmo anúncio (dispara `Duplicado de Plataforma?` saída 0) e confirmar o alerta.

Passo 2: na próxima mensagem NaPista com template, confirmar `parse_ok: true` com telefone, `lead_id` não-nulo e `Encaminhar ao Vendedor` executado. Numa `placeholderMessage`, confirmar `parse_ok: false` + alerta, sem objeto de erro descendo o fluxo.

## Monitorar (próximos dias)

- Execuções `mode: webhook` que passam por `Separar Leads NaPista` e **não** chegam em `Encaminhar ao Vendedor` — deve tender a zero para mensagens com telefone
- Volume de `connection.update`: 62 em 14 dias é o baseline. Se não cair, a instabilidade da Evolution continua e `placeholderMessage` continua chegando
- Leads com `numero_cliente = 551131361712` ou `551130044558`: deve ser **zero** após o Passo 2

## Rollback

Restaurar o `versionId e14f1ff7-aa49-4989-aaa7-b870a49f0ae8` pela version history do n8n (preserva credenciais). Por passo:

| Passo | Como voltar |
|---|---|
| 0 | apagar a conexão `Montar Alerta` → `Enviar Alerta Conexão` |
| 1 | apagar o nó `Alerta Lead Nao Distribuido` e restaurar as 3 conexões originais |
| 2 | reverter os 3 campos da tabela acima |

**Gatilhos para reverter:**

- Qualquer execução com `status: error` após a mudança (hoje são 0 em 373)
- Queda no volume diário de leads distribuídos comparado à média das duas semanas anteriores
- Alerta disparando em volume que impeça o operador de trabalhar

Leads criados entre a aplicação e o rollback ficam com o formato novo de `mensagem_original` — isso não é revertido nos dados, e não afeta nenhuma tela (verificado: `mensagem_original` não é lido em `pages/` nem `utils/`).
