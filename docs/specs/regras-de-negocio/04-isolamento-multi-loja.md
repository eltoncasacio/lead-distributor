# Isolamento Multi-Loja

> Verificado contra o schema real (`lojas`, `vendedores`, `gerentes`) e as policies de RLS ativas no Supabase (2026-09-11).

## Identidade da loja

Cada mensagem chega associada a uma **instância Evolution API** (`instancia_evolution`, coluna `UNIQUE` em `lojas`), não a um número de telefone — é assim que o sistema sabe de qual loja veio a mensagem (`identificar_remetente(p_instancia, p_numero_remetente)`). Isso está correto e implementado; não há regra documentada para o caso de duas lojas apontarem (por erro de configuração) para a mesma instância — o `UNIQUE` do banco previne isso de forma física.

## Regras de exclusividade

- `vendedores.numero_whatsapp` e `gerentes.numero_whatsapp` têm constraint `UNIQUE` (confirmado no schema real) — um número não pode ser vendedor/gerente de duas lojas ao mesmo tempo, nem ser gerente e vendedor simultaneamente.
- Um gerente pertence a exatamente uma loja (`loja_id` não nulo, sem tabela de associação N:N) — múltiplas lojas por gerente é uma ideia de roadmap, não implementada.

## Como o isolamento é aplicado nas queries

Toda leitura/escrita do Dashboard passa por `SUPABASE_SERVICE_KEY` (chave de serviço, que **contorna RLS**) e filtra manualmente por `loja_id` em cada query (`utils/queries.py`). As tabelas têm RLS habilitado no Postgres, mas as policies reais (verificadas ao vivo) são `Deny all for anon` na maioria das tabelas — ou seja, RLS aqui funciona como uma **segunda barreira contra o cliente anônimo público**, não como o mecanismo de isolamento entre lojas. O isolamento entre lojas depende, na prática, inteiramente da aplicação sempre filtrar por `loja_id` corretamente — não há defesa em profundidade no banco para esse caso específico. Ver débito técnico em [historico/AUDITORIA_2026-09-11.md](../../historico/AUDITORIA_2026-09-11.md).

Exceção: a tabela `mensagens_prontas` tem uma policy `Acesso por loja` com `qual: true` (permissiva para o role `public`) — na prática equivalente a "sem restrição de RLS", reforçando que o isolamento real dessa tabela também depende do filtro da aplicação.

## Produção real hoje

Apenas 1 loja ativa (`lojas` tem 1 linha). O isolamento multi-tenant nunca foi testado em produção com 2+ lojas simultâneas — vale validar antes de fazer onboarding de uma segunda loja.
