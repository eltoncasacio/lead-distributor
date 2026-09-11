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
| Evolution API muda de estado (conecta/desconecta) | Gera um alerta de WhatsApp para um número fixo (não documentado antes desta reescrita) |
| Falha ao enviar o alerta de conexão em si | O nó tem `onError: continueRegularOutput` — não derruba a execução |
| Falha ao parsear e-mail da NaPista (regex) | O nó de extração tem `onError: continueRegularOutput` — segue sem quebrar o workflow, mas não há alerta específico se a extração falhar/vier vazia |

## Gaps ainda não resolvidos (herdados de auditorias anteriores, não corrigidos nesta rodada — só documentação)

- **Sem retry configurado nos nós HTTP** que chamam Supabase/Evolution API (não verificado node a node em todos os 62, mas nenhum dos nós inspeccionados tem política de retry; auditorias técnicas anteriores do projeto contaram 13+ nós HTTP sem retry). Uma falha temporária de rede/timeout do Supabase faz a mensagem se perder.
- **Falha ao encaminhar a mensagem para o vendedor não é detectada**: se `Encaminhar ao Vendedor` falhar depois que o lead já foi gravado como distribuído, o lead fica "atribuído" no banco mas o vendedor nunca recebe a notificação, e ninguém é avisado.
- **Sem `onError` global no Webhook principal**: um erro não tratado no meio do fluxo pode fazer a Evolution API reenviar o evento, arriscando duplicar o processamento da mesma mensagem.
- **Comparação `vendedor_id !== "null"` como string**, não como valor nulo real, no nó "Vendedor Encontrado?" — funciona hoje porque o retorno HTTP serializa `null` como string `"null"`, mas é frágil a qualquer mudança de serialização.
- **Reatribuição manual de lead não é logada** (`atividades.tipo` não tem valor para isso — ver [regras-de-negocio/02](../regras-de-negocio/02-ciclo-de-vida-do-lead.md)).

## Onde estava documentado antes

O vault antigo já reconhecia boa parte desses gaps como "esperado, mas não necessariamente implementado" (nota que citava um arquivo `AUDITORIA_TECNICA_2026-02-19.md`, movido depois para `docs/historico/` sem atualizar a referência — outro exemplo do tipo de link quebrado que esta reescrita eliminou). O status desses itens não mudou desde então; seguem como débito técnico real, a ser tratado quando o usuário decidir revisar regras/robustez do sistema (fora do escopo desta rodada, que é só documentação).
