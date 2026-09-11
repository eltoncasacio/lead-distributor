# Modelo de Dados

> Extraído diretamente do schema real do Supabase (`list_tables`, verbose) em 2026-09-11. Volumetria de produção incluída para referência (não é meta, é o estado real na data da auditoria).

## Tabelas

### `lojas` (1 linha em produção)
| Coluna | Tipo | Notas |
|---|---|---|
| `id` | uuid, PK | |
| `nome` | varchar | |
| `numero_whatsapp` | varchar, nullable | |
| `instancia_evolution` | varchar, **unique**, nullable | chave real de identificação da loja numa mensagem recebida |
| `ativa` | boolean, default true | |
| `proximo_vendedor_id` | uuid, FK → vendedores, nullable | ponteiro do round-robin |
| `ultima_distribuicao_em` | timestamptz, nullable | |
| `limite_leads` | integer, nullable | **"Limite de leads do plano. NULL = ilimitado."** — coluna de billing/plano, não documentada em nenhum lugar antes desta reescrita, e sem lógica de enforcement encontrada no código auditado |
| `evolution_api_key` | text, nullable | chave da instância Evolution por loja (adicionada depois da versão inicial do schema) |
| `criado_em`, `atualizado_em` | timestamptz | |

### `vendedores` (6 linhas em produção)
`id` PK, `loja_id` FK, `nome`, `numero_whatsapp` (**unique global**, não só por loja), `status` (CHECK: `ativo`/`inativo`/`removido`), `ordem_fila` (int — **não usado pelo round-robin real**, só pela UI de drag-and-drop), `criado_em` (**esta** coluna é a ordem real do round-robin), `atualizado_em`.

### `gerentes` (1 linha em produção)
`id` PK, `loja_id` FK, `numero_whatsapp` (**unique global**), `nome`, `ativo` (boolean), `criado_em`.

### `leads` (1.205 linhas em produção)
`id` PK, `loja_id` FK, `vendedor_id` FK nullable, `numero_cliente`, `nome_cliente` nullable, `anuncio` nullable, `mensagem_original` text nullable, `recebido_em`, `distribuido_em` nullable, `status_lead` (CHECK: `negociando`/`sem_resposta`/`sem_interesse`/`vendido`, default `negociando`), `origem` (varchar, default `'WhatsApp Direto'`), `criado_em`, `atualizado_em`.

### `loja_acesso` (1 linha em produção)
`id` PK, `loja_id` FK **unique** (relação 1:1 com loja), `codigo_acesso` **unique** (o token `AUT-YYYYMMDD-XXXX` do login do Dashboard), `criado_em`, `ultimo_acesso_em` nullable.

### `atividades` (1.302 linhas em produção)
`id` PK, `loja_id` FK, `tipo` (CHECK, valores válidos: `novo_lead`, `status_lead_alterado`, `vendedor_adicionado`, `vendedor_removido`, `vendedor_inativado`, `vendedor_reativado`, `fila_reordenada`, `gerente_adicionado`, `gerente_desativado`, `gerente_removido` — **não existe** `lead_reatribuido`, ver [regras-de-negocio/02](../regras-de-negocio/02-ciclo-de-vida-do-lead.md)), `descricao` text, `criado_em`.

### `mensagens_prontas` (5 linhas em produção)
`id` PK, `loja_id` FK, `vendedor_id` FK nullable (`NULL` = template padrão da loja, preenchido = override por vendedor), `titulo`, `texto`, `ordem` int default 1, `ativo` boolean default true, `criado_em`.

## RLS (Row Level Security)

Habilitado em todas as tabelas acima. Policies reais (verificadas ao vivo):
- `lojas`, `vendedores`, `gerentes`, `leads`, `loja_acesso`, `atividades`: uma única policy `Deny all for anon` (`ALL`, `qual: false`) — bloqueia o role `anon`, mas isso é irrelevante para o Dashboard, que usa a `service_role` key (contorna RLS por completo).
- `mensagens_prontas`: policy `Acesso por loja`, mas com `qual: true` para o role `public` — na prática, sem restrição real.

**Conclusão prática**: RLS aqui não é a linha de defesa do isolamento multi-tenant. Isso é uma decisão implícita, não documentada antes — ver [ADR 0006](../../adr/0006-isolamento-por-filtro-de-aplicacao.md).

## Funções (RPCs) reais no schema `public`

| Função | Assinatura | Retorno | `SECURITY DEFINER`? | Usada em produção? |
|---|---|---|---|---|
| `distribuir_lead` | `(loja_id, numero_cliente, nome_cliente, anuncio, mensagem_original, recebido_em)` | `TABLE(lead_id, vendedor_id, vendedor_nome, vendedor_numero_whatsapp, duplicado)` | Não | **Overload legado**, sem `p_origem` — mantido no banco, não chamado pelo workflow atual (verificado: `distribuir_lead_dedup_por_anuncio`/`update_distribuir_lead_with_origem_and_activity` migraram para a versão de 7 args) |
| `distribuir_lead` | idem + `p_origem varchar default 'WhatsApp Direto'` | idem | Não | **Sim**, é a chamada real do nó "Distribuir Lead" |
| `identificar_remetente` | `(p_instancia, p_numero_remetente)` | `json` | **Sim** — e é executável pelos roles `anon` e `authenticated` sem autenticação adicional (accessible via `/rest/v1/rpc/identificar_remetente`) | Sim |
| `comando_status` | `(p_loja_id)` | `json` | Não | Sim |
| `comando_leads` | `(p_loja_id)` | `json` | Não | Sim |
| `comando_relatorio` | `(p_loja_id)` | não inspecionado em detalhe | Não | Não referenciado no workflow ativo — nome antigo do comando `leads` (ver [operacao/02](../operacao/02-comandos-whatsapp.md)) |
| `fn_status` | `(p_loja_id)` | `TABLE(total_leads_hoje, ultima_distribuicao, proximo_vendedor_nome)` | Não | Não referenciado — parece versão anterior de `comando_status` |
| `fn_relatorio` | `(p_loja_id)` | `TABLE(vendedor_nome, quantidade_leads)` | Não | Não referenciado — parece versão anterior de `comando_relatorio` |

Todas as 7 funções listadas nos *security advisors* do Supabase com `search_path` mutável (WARN de segurança — não corrigido nesta rodada, por instrução do usuário de não tratar segurança agora).

## Histórico de migrations relevante (32 migrations, 2026-02-07 a 2026-08-31)

Da criação do schema até o fix de race condition mais recente. Marcos: criação do schema e funções-base (07-08/02), correção de identificação/constraints únicas (08/02, 07/03), lógica de dedup e round-robin (17-28/02), tabelas de dashboard e `mensagens_prontas` (07-09/03), coluna `origem` em `leads` (08/03), idas e vindas na janela de tempo do `comando_status` (17-20/03, terminou revertendo para 3 dias de propósito), e o lock advisory anti-race (31/08). Ver [ADR 0002](../../adr/0002-lock-advisory-race-condition.md) para o incidente que motivou a última.
