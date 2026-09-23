# Tratamento de Erros

> Este documento descreve o comportamento **real observado**, não um comportamento desejado. Verificado parcialmente ao vivo em 2026-09-11 (13 dos 62 nós do workflow foram inspecionados em detalhe); onde não há confirmação direta, está marcado como "não verificado".

## Comportamentos confirmados

| Situação | Comportamento real |
|---|---|
| Loja não encontrada (instância desconhecida) | Mensagem descartada silenciosamente, sem log de erro nem alerta |
| Remetente não é gerente/vendedor/vendedor-removido | Tratado como lead |
| Nenhum vendedor ativo na loja no momento da distribuição | `distribuir_lead()` levanta exceção SQL; a chamada HTTP do n8n falha; **o lead não é persistido** (diferente do que documentação antiga afirmava — não há gravação com `vendedor_id = NULL`) |
| Mensagem duplicada de cliente já atendido | Ver [regras-de-negocio/05](../regras-de-negocio/05-deduplicacao.md) |
| Mensagens concorrentes do mesmo cliente | Serializadas por lock desde 31/08/2026 (ver [ADR 0002](../../adr/0002-lock-advisory-race-condition.md)) |
| Evolution API muda de estado (conecta/desconecta) | **Não gera alerta nenhum.** O nó `Montar Alerta` monta a mensagem e sua saída não vai a lugar nenhum; `Enviar Alerta Conexão` é nó órfão, sem entrada. Verificado no grafo ao vivo em 2026-09-23. Ocorre ~4×/dia (62 quedas + 62 reconexões em 14 dias) |
| Falha ao enviar o alerta de conexão em si | Irrelevante hoje: o nó nunca é alcançado (ver linha acima). Ele tem `onError: continueRegularOutput`, então quando for ligado não derrubará a execução |
| Falha ao parsear e-mail da NaPista (regex) | O nó de extração tem `onError: continueRegularOutput` — segue sem quebrar o workflow, mas não há alerta específico se a extração falhar/vier vazia |

## Gaps ainda não resolvidos (herdados de auditorias anteriores, não corrigidos nesta rodada — só documentação)

- **Retry existe, ao contrário do que este documento afirmava.** Verificado no grafo ao vivo em 2026-09-23: **8 nós têm `retryOnFail`** — `Identificar Loja`, `Distribuir Lead`, `Buscar Status`, `Buscar Leads`, `Enviar Resp Comando`, `Cmd Não Reconhecido`, `Acessar Leads` e `Encaminhar ao Vendedor`, ou seja, todo o caminho crítico de distribuição. **Sem retry**: `Identificar Remetente`, `Buscar Mensagens Prontas`, `Buscar Loja Mobiauto` e `Buscar Loja Webmotors` — destes, `Identificar Remetente` é o único no caminho crítico.
- **Não há `errorWorkflow` configurado** nas settings do workflow. Uma falha definitiva (depois dos retries) encerra a execução sem avisar ninguém.
- **Cinco caminhos de perda silenciosa**, todos verificados no grafo: `Duplicado de Plataforma?` saída 0 e `Vendedor Encontrado?` saída 1 voltam ao `Loop Over Items` sem alerta; `Loja Encontrada?` saída 1 não tem conexão nenhuma; `Separar Leads icarros` faz `return []` quando o regex não casa; e `Separar Leads NaPista` estoura em `placeholderMessage` e, por ter `onError: continueRegularOutput`, emite o **objeto de erro como dado** para o resto do fluxo.
- **Falha ao encaminhar a mensagem para o vendedor não é detectada**: se `Encaminhar ao Vendedor` falhar depois que o lead já foi gravado como distribuído, o lead fica "atribuído" no banco mas o vendedor nunca recebe a notificação, e ninguém é avisado.
- **Sem `onError` global no Webhook principal**: um erro não tratado no meio do fluxo pode fazer a Evolution API reenviar o evento, arriscando duplicar o processamento da mesma mensagem.
- **Comparação `vendedor_id !== "null"` como string**, não como valor nulo real, no nó "Vendedor Encontrado?" — funciona hoje porque o retorno HTTP serializa `null` como string `"null"`, mas é frágil a qualquer mudança de serialização.
- **Reatribuição manual de lead não é logada** (`atividades.tipo` não tem valor para isso — ver [regras-de-negocio/02](../regras-de-negocio/02-ciclo-de-vida-do-lead.md)).

## Onde estava documentado antes

O vault antigo já reconhecia boa parte desses gaps como "esperado, mas não necessariamente implementado" (nota que citava um arquivo `AUDITORIA_TECNICA_2026-02-19.md`, movido depois para `docs/historico/` sem atualizar a referência — outro exemplo do tipo de link quebrado que esta reescrita eliminou). O status desses itens não mudou desde então; seguem como débito técnico real, a ser tratado quando o usuário decidir revisar regras/robustez do sistema (fora do escopo desta rodada, que é só documentação).
