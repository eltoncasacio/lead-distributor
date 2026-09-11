# Distribuição de Leads (Round-Robin)

> Verificado ao vivo em 2026-09-11 contra o código-fonte real da função `distribuir_lead()` no Supabase (migration `20260831201924_fix_race_condition_distribuir_lead_advisory_lock`, versão em produção). Este documento substitui `Regras de Negócio/01` do vault antigo, que descrevia a ordem da fila de forma ambígua ("ordem de cadastro **ou** ordem definida para a loja").

## Mecanismo real

A fila **não** é recalculada a cada mensagem. Cada loja (`lojas`) guarda um ponteiro `proximo_vendedor_id`, atualizado a cada distribuição. A ordem de rotação é `vendedores.criado_em ASC` (ordem de cadastro) — **não existe** hoje uma coluna de ordem customizável que afete o round-robin (a coluna `ordem_fila` existe e é usada só pela UI de drag-and-drop do Dashboard; ver nota de débito técnico abaixo).

Passo a passo (dentro da função `distribuir_lead`, que só executa este caminho quando não há duplicata exata nem cliente amarrado — ver [05-deduplicacao.md](05-deduplicacao.md)):

1. Lê `lojas.proximo_vendedor_id` com `SELECT ... FOR UPDATE` (trava a linha da loja até o fim da transação — garante atomicidade entre execuções concorrentes da mesma loja).
2. Se o ponteiro é `NULL` (nunca distribuiu, ou vendedor apontado foi removido do sistema): pega o primeiro vendedor `ativo` por `criado_em ASC`.
3. Se o ponteiro aponta para um vendedor que não está mais `ativo` (foi para `inativo` ou `removido`): busca o próximo `ativo` cadastrado depois dele; se não achar nenhum depois, **volta ao primeiro** da lista (wrap-around).
4. Vendedor escolhido = quem recebe o lead atual.
5. Calcula, separadamente, quem é o **próximo depois desse** (mesma lógica de wrap-around) e grava esse id em `lojas.proximo_vendedor_id` — ou seja, o ponteiro sempre aponta para "quem vem depois do último atendido", não para "quem atendeu por último".
6. Se não existe nenhum vendedor `ativo` na loja, a função levanta uma exceção (`RAISE EXCEPTION 'Nenhum vendedor ativo disponível na loja'`) — o lead **não é perdido silenciosamente** nesse caso específico, mas a chamada HTTP do n8n falha; ver [tratamento de erros](../operacao/03-tratamento-de-erros.md).

## Regras derivadas

- Só vendedores com `status = 'ativo'` entram na rotação (ver [03-estados-vendedor.md](03-estados-vendedor.md)).
- Um vendedor recém-cadastrado entra na fila na posição correspondente à sua data de criação — ou seja, **no fim da fila atual**, não necessariamente logo após o próximo a ser chamado.
- Não há peso, prioridade ou limite de leads por vendedor no algoritmo hoje (existe uma coluna `lojas.limite_leads`, mas é um limite de **plano/contrato da loja inteira**, não por vendedor — não documentado em nenhum lugar antes desta reescrita).
- Este passo (Passo 3 da função) só roda quando não há duplicata exata (Passo 1) nem cliente amarrado a um vendedor ainda ativo (Passo 2).

## Concorrência

Antes de 31/08/2026, duas mensagens quase simultâneas do mesmo cliente podiam gerar dois leads para dois vendedores diferentes (ver incidente completo em [`historico/incidentes/2026-08-31-race-condition/`](../../historico/incidentes/2026-08-31-race-condition/)). A correção foi um lock por `(loja_id, numero_cliente)` (`pg_advisory_xact_lock`) adquirido **antes** de tudo, inclusive antes do `FOR UPDATE` da tabela `lojas` — ele serializa apenas chamadas do mesmo cliente na mesma loja; clientes diferentes continuam sendo processados em paralelo, então não há gargalo de performance perceptível.

## Débito técnico conhecido

- **A coluna `vendedores.ordem_fila` e o drag-and-drop do Dashboard não têm efeito no round-robin real**, que segue estritamente `criado_em`. Isso é uma divergência entre o que o gerente vê/mexe no Dashboard e o que o sistema realmente faz — vale corrigir ou deixar explícito na UI (já está documentado como trade-off conhecido pela equipe, não é uma descoberta desta auditoria).
