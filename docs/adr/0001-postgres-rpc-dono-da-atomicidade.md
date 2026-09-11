# ADR 0001 — Atomicidade da distribuição vive no Postgres, não no n8n

## Status
Aceito (implementado)

## Contexto
A distribuição de um lead envolve decisões que precisam ser atômicas: checar duplicata, escolher o próximo vendedor, avançar o ponteiro da fila, gravar o lead. O n8n orquestra o fluxo, mas não tem primitivas nativas de lock/transação entre chamadas de nós.

## Decisão
Toda a lógica de decisão (dedup, amarração de cliente, round-robin, avanço de ponteiro, insert do lead, log de atividade) vive dentro de uma única função SQL, `distribuir_lead()`, executada como uma transação Postgres. O n8n só chama essa função via HTTP e reage ao resultado — não implementa lock nem decide nada sozinho.

## Consequências
- A atomicidade é garantida pelo banco (`SELECT ... FOR UPDATE`), independente de quantos nós/execuções do n8n rodem em paralelo.
- Mudar a regra de negócio exige alterar SQL, não o workflow visual — o que também significa que quem só olha o n8n não vê a regra real (ela está em [regras-de-negocio/](../specs/regras-de-negocio/), extraída diretamente do código da função).
- Historicamente essa atomicidade não foi suficiente sozinha — ver [ADR 0002](0002-lock-advisory-race-condition.md).
