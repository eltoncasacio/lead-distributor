# Ciclo de Vida do Lead

> Verificado contra o schema real da tabela `leads` (Supabase, 2026-09-11) e a função `distribuir_lead()`.

## Estados (`leads.status_lead`)

CHECK constraint real no banco: `negociando` (default) → `sem_resposta` | `sem_interesse` | `vendido`. Não há transições obrigatórias entre eles — o gerente/vendedor muda livremente pelo Dashboard (`pages/4_Leads.py`).

> **Nota de correção**: documentação antiga (`SISTEMA.md` do app e docs do vault) descrevia o fluxo como `novo → atendido → negociando → venda/desistiu`. Esses valores **nunca existiram** no banco — o schema atual (desde a migration `refatorar_status_lead`, 2026-03-18) é o único que já rodou em produção real. O texto antigo foi descartado nesta reescrita.

| Status | Significado | Definido por |
|---|---|---|
| `negociando` | Padrão ao criar o lead. Em atendimento. | Sistema (default) |
| `sem_resposta` | Cliente não respondeu ao vendedor. | Gerente/vendedor, manual |
| `sem_interesse` | Cliente não quer mais comprar. | Gerente/vendedor, manual |
| `vendido` | Venda concluída. | Gerente/vendedor, manual |

Não há SLA, prazo ou fechamento automático — um lead pode ficar `negociando` indefinidamente (isso motivou o workflow "Lembrete Leads Pendentes", que chegou a ser construído mas nunca foi ativado e hoje não existe mais no n8n — ver [PRD §7](../../PRD.md)).

## Entrada de um lead

1. Mensagem chega por qualquer origem (ver [tecnica/03-workflow-n8n.md](../tecnica/03-workflow-n8n.md)).
2. `identificar_remetente()` classifica o remetente. Só segue como lead se **não** for um `numero_whatsapp` cadastrado como gerente ou vendedor *ativo/inativo* daquela loja. Um vendedor com status `removido` que escreve pelo mesmo número **não é reconhecido** pela função (ela só verifica `status IN ('ativo','inativo')`) — na prática esse número passa a ser tratado como lead.
3. `distribuir_lead()` roda dedup (ver [05](05-deduplicacao.md)) e round-robin (ver [01](01-round-robin.md)), grava o registro em `leads` com `vendedor_id`, `origem`, `anuncio`, `mensagem_original`, `recebido_em`, `distribuido_em = NOW()`.
4. Uma linha é gravada em `atividades` (`tipo = 'novo_lead'`).
5. O vendedor recebe a mensagem encaminhada no seu WhatsApp (ver [operacao/01](../operacao/01-fluxo-principal.md)).

## Caso: nenhum vendedor ativo

A função levanta exceção SQL (`RAISE EXCEPTION`) — a chamada HTTP do n8n falha, **nenhum lead é persistido** nesse caso (diferente do que documentação antiga afirmava — "lead persistido com `vendedor_id = NULL`"). Isso é um ponto de risco real: sem vendedor ativo, o lead se perde e não há alerta automático. Ver [operacao/03-tratamento-de-erros.md](../operacao/03-tratamento-de-erros.md).

## Reatribuição manual

Não existe fluxo de produto para reatribuir um lead a outro vendedor. Já aconteceu manualmente via SQL direto (incidente de 31/08 — ver [historico](../../historico/incidentes/)), e nesse caso **não há tipo de atividade correspondente**: o CHECK constraint de `atividades.tipo` não inclui `'lead_reatribuido'`, então reatribuições manuais não deixam rastro no log de atividades. Débito técnico a resolver se esse fluxo virar uma operação recorrente.
