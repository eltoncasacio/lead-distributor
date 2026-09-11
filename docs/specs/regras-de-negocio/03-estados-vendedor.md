# Estados do Vendedor

> Verificado contra o CHECK constraint real de `vendedores.status` no Supabase (2026-09-11).

## Estados válidos (únicos três que existem no banco)

| Estado | Participa do round-robin? | Histórico de leads preservado? | Pode reverter? |
|---|---|---|---|
| `ativo` | Sim | Sim | — |
| `inativo` | Não | Sim | Sim, volta a `ativo` |
| `removido` | Não | Sim | Não (é definitivo na UI atual) |

> **Correção**: `Regras de Negócio/05` do vault antigo mencionava um estado `'pausado'` num exemplo de caso extremo. Esse valor **não existe** no CHECK constraint do banco (`ANY (ARRAY['ativo','inativo','removido'])`) nem em nenhuma parte do código do Dashboard. Era um erro de terminologia do documento antigo — "pausar" é usado como *verbo* para a ação de tornar `inativo`, não como um quarto estado. Removido nesta reescrita.

## Quem gerencia

Exclusivamente o Dashboard Web (`pages/3_👤_Vendedores.py`), por um gerente autenticado. Não existe comando de WhatsApp para mudar status de vendedor.

Regra de negócio aplicada na UI (não replicada como constraint no banco — ver débito técnico): não é possível desativar/remover o último vendedor `ativo` de uma loja. Essa checagem hoje só existe na tela (`pode_remover = len(gerentes) > 1` e equivalente para vendedores) — uma chamada direta à função de deleção no backend não teria essa proteção.

## Efeito em `identificar_remetente()`

A função de classificação de remetente considera vendedor **`ativo` OU `inativo`** como "vendedor conhecido" (não trata como lead). Um vendedor `removido` deixa de ser reconhecido — se esse número voltar a escrever, o sistema o trata como um lead comum.
