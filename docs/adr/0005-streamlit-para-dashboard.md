# ADR 0005 — Streamlit como stack do Dashboard Web

## Status
Aceito (implementado)

## Contexto
O produto originalmente era só WhatsApp (vendedores/gerentes usando comandos de texto). Precisou de uma interface de gestão mais rica para gerentes (CRUD de vendedores, visualização de métricas) sem exigir uma equipe de frontend dedicada.

## Decisão
Streamlit, hospedado no Streamlit Cloud, consumindo Supabase diretamente com a chave de serviço.

## Consequências
- Desenvolvimento rápido de telas de CRUD e gráficos (Plotly) sem construir uma API própria — o app fala direto com o banco.
- Uso da `service_role` key no cliente Streamlit contorna RLS por completo; a segurança de tenant depende inteiramente de todo query filtrar `loja_id` corretamente (ver [ADR 0006](0006-isolamento-por-filtro-de-aplicacao.md)).
- Modelo de autenticação simplificado do Streamlit (sem sistema de contas nativo robusto) reforçou a escolha do token único por loja (ADR 0004) em vez de um sistema de login mais tradicional.
- Sem camada de API intermediária, qualquer regra de validação de negócio que não esteja no Postgres (ex.: "não remover o último vendedor ativo") só existe na própria tela — não há reuso garantido se outro cliente (app mobile, outra automação) vier a acessar os mesmos dados no futuro.
