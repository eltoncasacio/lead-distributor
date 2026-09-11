# ADR 0002 — Lock advisory por (loja, cliente) para eliminar race condition de duplicidade

## Status
Aceito (implementado em 2026-08-31)

## Contexto
Em 31/08/2026, um cliente real (Levi S.) mandou uma mensagem que gerou **duas execuções paralelas do n8n** quase simultâneas (32ms de diferença). O `FOR UPDATE` existente na tabela `lojas` (ADR 0001) protegia o ponteiro do round-robin, mas **não** protegia os passos de deduplicação (Passo 1 e 2 de [regras-de-negocio/05](../specs/regras-de-negocio/05-deduplicacao.md)): as duas execuções liam o estado de `leads` antes de qualquer uma commitar seu INSERT, então nenhuma via a outra, e o mesmo cliente foi distribuído para **dois vendedores diferentes** (André e Japa). Detalhe completo em [historico/incidentes/2026-08-31-race-condition/](../historico/incidentes/2026-08-31-race-condition/).

## Decisão
Adicionar um "Passo 0" em `distribuir_lead()`: `pg_advisory_xact_lock(hashtextextended(loja_id || '|' || numero_cliente, 0))`, adquirido **antes** de qualquer leitura, inclusive antes do `FOR UPDATE` de `lojas`. O lock serializa apenas chamadas do **mesmo** par (loja, cliente); clientes diferentes continuam em paralelo — sem impacto de performance perceptível. Liberado automaticamente no fim da transação (`xact_lock`).

## Consequências
- Corrige a causa raiz (dedup não estava protegida, só o round-robin estava).
- Mudança via `CREATE OR REPLACE FUNCTION` — sem alterar assinatura, sem downtime, sem tocar em dados.
- A limpeza manual do lead duplicado gerado pelo incidente não deixou rastro em `atividades` (constraint não previa reatribuição manual) — gap que persiste, ver [regras-de-negocio/02](../specs/regras-de-negocio/02-ciclo-de-vida-do-lead.md).
- Rollback simples existe e está documentado (`ROLLBACK_distribuir_lead.sql`), caso o lock cause algum efeito colateral não previsto.
