# ADR 0003 — Loja identificada pela instância Evolution, não pelo número de telefone

## Status
Aceito (implementado)

## Contexto
O sistema precisa saber, para cada mensagem recebida, a qual loja ela pertence, antes de decidir se é lead/vendedor/gerente.

## Decisão
Usar `lojas.instancia_evolution` (identificador da sessão/instância no Evolution API, `UNIQUE`) como chave de resolução, em vez do número de WhatsApp da loja. `identificar_remetente(p_instancia, p_numero_remetente)` recebe a instância como primeiro parâmetro.

## Consequências
- Robusto a trocas de número de telefone da loja, desde que a instância permaneça a mesma.
- Depende de configuração correta do webhook da Evolution API apontando para a instância certa — não há verificação automática de que o nome da instância cadastrado no Supabase bate com o nome real criado no Evolution API; erro de digitação nesse cadastro faz a loja parar de receber leads silenciosamente (mensagem cai em "loja não encontrada" e é descartada, ver [operacao/03](../specs/operacao/03-tratamento-de-erros.md)).
- Não há hoje um caso documentado de erro de configuração cruzada (duas lojas na mesma instância) em produção — o `UNIQUE` do banco previne fisicamente essa situação.
