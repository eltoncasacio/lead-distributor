# ADR 0004 — Dashboard autenticado por código único por loja, sem contas individuais

## Status
Aceito (implementado) — trade-off conhecido, não revisado nesta rodada

## Contexto
O Dashboard Web precisa de algum controle de acesso para gerentes, mas o produto prioriza simplicidade de operação (poucos usuários por loja, sem necessidade de granularidade de permissão por pessoa).

## Decisão
Um único código de acesso por loja (`AUT-YYYYMMDD-XXXX`, tabela `loja_acesso`), compartilhado entre todos os gerentes daquela loja. Sem cadastro de usuário, sem senha individual, sem papéis diferenciados dentro do Dashboard.

## Consequências
- Onboarding simples: um código, sem gestão de múltiplas contas.
- Não há como saber **qual** gerente fez uma ação específica (o log de `atividades` não referencia usuário, só loja).
- A sessão do navegador é mantida via o UUID da loja na URL, sem expiração — na prática funciona como uma credencial permanente e única por loja (ver débito técnico em [tecnica/05-dashboard-streamlit.md](../specs/tecnica/05-dashboard-streamlit.md)). Revisão desse mecanismo fica para quando o usuário decidir tratar pendências de segurança/robustez — não faz parte desta rodada de documentação.
