# ADR 0006 — Isolamento multi-tenant por filtro de aplicação, não por RLS

## Status
Aceito (implícito) — verificado e explicitado nesta reescrita, nunca havia sido decidido/documentado formalmente

## Contexto
O sistema é multi-tenant (`loja_id` em toda tabela relevante). RLS está habilitado nas tabelas do Supabase, o que sugeriria que o isolamento é garantido pelo banco. Na prática, tanto o n8n (via RPCs `SECURITY INVOKER`, exceto `identificar_remetente`) quanto o Dashboard (via `service_role` key) acessam o banco com privilégios que **contornam** RLS, ou contra policies que são efetivamente permissivas (`mensagens_prontas`) ou irrelevantes para esse uso (`Deny all for anon` não afeta quem usa a chave de serviço).

## Decisão (implícita, agora explícita)
O isolamento entre lojas depende inteiramente de cada query no código (`utils/queries.py`, funções SQL) filtrar corretamente por `loja_id`. RLS existe apenas como barreira contra acesso anônimo direto à API REST do Supabase, não como mecanismo de isolamento entre tenants.

## Consequências
- Nenhuma query esquecida de filtrar `loja_id` teria uma segunda linha de defesa no banco — o erro vazaria dados entre lojas.
- Como hoje há **apenas 1 loja em produção**, esse risco nunca se manifestou de forma observável, mas se torna real assim que uma segunda loja for onboarded.
- Se o usuário decidir tratar isso no futuro, a alternativa seria policies de RLS reais baseadas em `loja_id` (exigindo repensar como o n8n e o Dashboard se autenticam — hoje ambos usam chaves com privilégio total). Fora do escopo desta rodada, que é só documentação.
