# Arquitetura Geral

> Verificado ao vivo em 2026-09-11 via MCP (Supabase + n8n). Substitui `Técnica/01` do vault antigo.

## Componentes

```
Cliente (WhatsApp/e-mail/webhook de portal)
        │
        ▼
Evolution API  ──(webhook)──▶  n8n  ──(HTTP/RPC)──▶  Supabase (Postgres)
                                 │                         │
                                 └────(HTTP sendText)───────┘
                                          │
                                          ▼
                                  WhatsApp do vendedor/gerente

Dashboard Web (Streamlit) ──(service_role key)──▶ Supabase (Postgres)
```

- **Evolution API**: gateway de WhatsApp (QR code, envio/recebimento). Camada de transporte pura — nenhuma regra de negócio aqui.
- **n8n**: orquestração. Workflow ativo de produção: **"Renato Motors Amarrar Lead"** (id `Qj200sqS9544ao3d`), 62 nós, 45 conexões, atualizado pela última vez em 2026-06-23. Existem 3 outras versões do workflow arquivadas (histórico de iterações, não usadas em produção). **Este é o único workflow no ambiente n8n** — um segundo workflow, "Lembrete Leads Pendentes (Diário)", chegou a existir mas foi removido pelo dono do sistema (confirmado em 2026-09-22).
- **Supabase (Postgres)**: persistência **e** regra de negócio — as decisões de round-robin/deduplicação vivem em funções SQL (`distribuir_lead`, `identificar_remetente`, `comando_status`, `comando_leads`), não no n8n. RLS está habilitado nas tabelas, mas as policies reais são majoritariamente "negar tudo para `anon`" — o isolamento entre lojas depende da aplicação filtrar por `loja_id` (ver [regras-de-negocio/04](../regras-de-negocio/04-isolamento-multi-loja.md)).
- **Dashboard Web (Streamlit)**: interface de gestão para gerentes, acessa o Supabase com a chave de serviço (`service_role`, contorna RLS). Ver [05-dashboard-streamlit.md](05-dashboard-streamlit.md).

## Multi-tenant

O modelo de dados é multi-tenant (toda tabela relevante tem `loja_id`), mas a implementação real de automação (n8n) tem hoje valores hardcoded para uma única loja em alguns pontos (parsing de e-mail NaPista, nomes de webhook) — ver [03-workflow-n8n.md](03-workflow-n8n.md) e [operacao/04-onboarding-nova-loja.md](../operacao/04-onboarding-nova-loja.md). Em produção real: **1 loja ativa**.

## Por que este desenho (decisões arquiteturais)

Ver [ADRs](../../adr/) para o raciocínio por trás de cada escolha: atomicidade no Postgres em vez do n8n ([0001](../../adr/0001-postgres-rpc-dono-da-atomicidade.md)), lock por cliente para corrigir race condition ([0002](../../adr/0002-lock-advisory-race-condition.md)), identificação de loja por instância Evolution ([0003](../../adr/0003-identificacao-loja-por-instancia.md)), autenticação do Dashboard por token de loja ([0004](../../adr/0004-autenticacao-por-token-de-loja.md)), Streamlit como stack do Dashboard ([0005](../../adr/0005-streamlit-para-dashboard.md)), isolamento multi-tenant por filtro de aplicação ([0006](../../adr/0006-isolamento-por-filtro-de-aplicacao.md)), n8n como roteador multi-origem ([0007](../../adr/0007-n8n-roteador-multi-origem.md)).
