# Comandos via WhatsApp

> Verificado contra o código real de `comando_status()` e `comando_leads()` no Supabase, e o nó "Identificar Comando" do workflow n8n (2026-09-11).

## Comandos disponíveis

Apenas dois, texto exato (case-insensitive — a comparação faz `.toLowerCase()` antes de comparar), sem interpretação por IA:

- **`status`** → resumo da distribuição.
- **`leads`** → lista de leads recebidos.
- Qualquer outro texto de um gerente/vendedor conhecido → resposta fixa "Comando não reconhecido. Comandos disponíveis: status, leads". **Não** é tratado como lead.

Gerentes e vendedores têm exatamente os mesmos comandos disponíveis (não há diferenciação de permissão por papel).

## `status` — o que a função realmente retorna

> **Correção importante**: o nome do comando sugere "hoje", mas a função `comando_status()` sempre consulta uma **janela fixa dos últimos 3 dias corridos** (hoje + 2 dias anteriores, fuso `America/Sao_Paulo`). Isso não é um bug — a equipe já tentou mudar para "somente hoje" (migration `fix_comando_status_hoje_somente`) e reverteu de propósito no dia seguinte (migration `reverter_comando_status_volta_3_dias`), preferindo a janela de 3 dias para o comando de WhatsApp. **O Dashboard Web é que calcula "hoje" de verdade**, separadamente, no client (ver [tecnica/05](../tecnica/05-dashboard-streamlit.md)) — os dois números (comando `status` vs. KPI do Dashboard) são **esperados serem diferentes**, por design.

Campos retornados: período consultado, total de leads no período, horário do último lead recebido, nome do próximo vendedor na fila, e uma lista "• Vendedor: quantidade" por vendedor ativo.

## `leads` — o que a função realmente retorna

Mesma janela de 3 dias. Lista até **150 leads** (não 50, como documentação antiga afirmava), ordenados do mais antigo para o mais recente, com horário, nome do cliente, anúncio, origem e vendedor responsável (ou "Não atribuído").

## Legado no banco

Existem funções `fn_status(p_loja_id)` e `fn_relatorio(p_loja_id)` no schema, com formato de retorno mais simples e diferente de `comando_status`/`comando_leads`. Não são chamadas por nenhum nó do workflow de produção nem pelo Dashboard — parecem ser versões anteriores mantidas no banco sem uso. Candidatas a limpeza (não removidas nesta reescrita, que é só documentação).
