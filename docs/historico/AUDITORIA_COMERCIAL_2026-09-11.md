# Auditoria de Prontidão Comercial — 2026-09-11

> Motivação: o usuário vai começar a comercializar o sistema para outras concessionárias. Este documento junta achados **novos** desta rodada com débitos **já conhecidos** (linkados, não repetidos) em [historico/AUDITORIA_2026-09-11.md](AUDITORIA_2026-09-11.md) e [specs/tecnica/02-modelo-de-dados.md](../specs/tecnica/02-modelo-de-dados.md), sob a pergunta: "o que impede vender isso com segurança para vários clientes pagantes?"

## 1. Achado novo e crítico: qualidade da contagem de leads

O usuário suspeitava que a contagem de leads pudesse incluir spam, cobrança ou outras mensagens que não são leads de verdade. **Confirmado ao vivo** na estrutura real do workflow n8n em produção (`Renato Motors Amarrar Lead`, 62 nós):

- Depois de identificar que quem escreveu **não é** um vendedor/gerente conhecido (nó "Não É Lead"), a mensagem vai direto para "Verificar Origem" → preparação de dados → **`Distribuir Lead`**.
- **Não existe nenhuma etapa de classificação de conteúdo** entre esses dois pontos — nem palavra-chave, nem lista de bloqueio, nem IA. Qualquer número desconhecido que mande qualquer mensagem (cobrança, engano de número, spam, corretor de outro assunto) é tratado exatamente como um lead de compra e entra na distribuição round-robin.
- Consequência prática: os **1.205 leads** hoje em produção não têm garantia de serem todos leads genuínos de compra — não há como separar isso do que é ruído sem auditoria manual do campo `mensagem_original`.
- **Recomendação**: a ideia do usuário de um menu de primeiro contato (Comprar/Consignado/Outros) com triagem por LLM em "Outros" ataca exatamente esse problema. Está desenhada como proposta de produto separada — ver plano de implementação em andamento — e não foi implementada nesta rodada por ser mudança de regra de negócio (n8n + Postgres).

## 2. Achado confirmado (e corrigido): divergência sobre o workflow "Lembrete Leads Pendentes"

Uma versão anterior de `docs/PRD.md` e `docs/roadmap.md` (escrita hoje, mesma data, antes desta auditoria) citava um segundo workflow n8n, **"Lembrete Leads Pendentes (Diário)"**, já construído mas desativado. Consultei `n8n_list_workflows` sem filtro e depois com `active:false` explícito: o resultado é **1 workflow no total, 0 inativos** — só o `Renato Motors Amarrar Lead`.

Confirmado com o usuário: a afirmação estava **errada** (não existe um segundo projeto/credencial n8n). `docs/PRD.md` §6 e `docs/roadmap.md` foram corrigidos para remover essa afirmação — o "lembrete diário de leads pendentes" volta a ser só uma ideia de roadmap, não um recurso pronto aguardando ativação.

## 3. Gaps de prontidão para múltiplos clientes pagantes

| Gap | Por que importa com N clientes (não importava tanto com 1) | Referência |
|---|---|---|
| **Onboarding de loja nova é 100% manual**: SQL direto nas tabelas + edição manual do node do n8n pra trocar a instância/chave Evolution (hardcoded no node, não lida de `lojas.evolution_api_key`) | Não escala para vender sozinho — cada cliente novo exige trabalho de engenharia, não é self-service | [specs/tecnica/04-integracao-evolution-api.md](../specs/tecnica/04-integracao-evolution-api.md) |
| **`lojas.limite_leads` sem enforcement** — coluna de plano existe no schema mas nenhum código (Dashboard ou n8n) a lê para bloquear ou avisar | Sem isso não há diferenciação de plano/billing de verdade — qualquer cliente tem uso "ilimitado" de fato | [specs/tecnica/02-modelo-de-dados.md](../specs/tecnica/02-modelo-de-dados.md) |
| **Autenticação por UUID permanente na URL, sem expiração** | Com 1 cliente é um risco controlado; com N clientes pagantes, um link vazado (print, histórico de navegador, referrer) dá acesso total e indefinido a um cliente específico — vira um incidente de confiança, não só um bug | [specs/tecnica/05-dashboard-streamlit.md](../specs/tecnica/05-dashboard-streamlit.md), [ADR 0004](../adr/0004-autenticacao-por-token-de-loja.md) |
| **`codigo_acesso` não tem nenhuma geração automática** — verificado em todo o histórico do git (`git log --all -p`): o código só é **lido** (`utils/auth.py`) e **exibido** na sidebar em qualquer commit já existente; nunca há uma linha que o escreva. O `AUT-20260304-X7Y2` que aparece no placeholder do login é só um texto de exemplo, não algo que o sistema produz | Onboarding de cliente novo depende de alguém digitar o código manualmente na tabela `loja_acesso` (Table Editor ou SQL) — sem geração/rotação, não dá pra oferecer "esqueci meu código" nem trocar o código de um cliente sem mexer direto no banco | Confirmado nesta rodada via `git log --all -p -- '*.py'` |
| **Isolamento multi-tenant nunca testado em produção com 2+ lojas** | É a base de toda a promessa comercial ("suas lojas não veem os dados umas das outras") — nunca foi exercitado de verdade | [regras-de-negocio/04-isolamento-multi-loja.md](../specs/regras-de-negocio/04-isolamento-multi-loja.md), roteiro em [dev/roteiro-loja-fake-multitenant.md](../dev/roteiro-loja-fake-multitenant.md) |
| **Sem retry/monitoramento no envio via Evolution API** | Com 1 loja, uma falha pontual passa despercebida; com N lojas pagando, vira ponto de suporte recorrente e motivo de cancelamento se não for percebido rápido | [specs/operacao/03-tratamento-de-erros.md](../specs/operacao/03-tratamento-de-erros.md) |
| **Funções mortas confirmadas no banco**: `fn_status`, `fn_relatorio`, `comando_relatorio` (versões antigas não referenciadas), e overload de 6 argumentos de `distribuir_lead` (legado, o real usa 7) | Risco de manutenção — alguém (humano ou IA) pode chamar a função errada por engano ao mexer no sistema para um cliente novo | [specs/tecnica/02-modelo-de-dados.md](../specs/tecnica/02-modelo-de-dados.md) |
| **`search_path` mutável em 7 funções + `identificar_remetente` como `SECURITY DEFINER` executável por `anon`/`authenticated` via REST** | Debitado tecnicamente hoje por instrução do usuário de não tratar segurança nesta rodada — mas com múltiplos tenants pagantes a superfície de ataque de uma função SQL exposta publicamente pesa mais | Supabase Security Advisors (verificado ao vivo 2026-09-11), [specs/tecnica/02-modelo-de-dados.md](../specs/tecnica/02-modelo-de-dados.md) |
| **Sem ambiente de desenvolvimento/staging separado de produção** | `.env` local aponta para o mesmo projeto Supabase que produção; n8n tem só 1 workflow, sem cópia de teste; não existe uma 2ª instância Evolution API. Qualquer mudança de schema ou de workflow hoje é testada direto em cima dos dados da Renato Motors (ou não é testada de ponta a ponta) | Verificado ao vivo: `get_project_url` do MCP bate com `SUPABASE_URL` do `.env`; `list_branches` retornou vazio (branching disponível mas não usado) |

## 4. Checklist priorizado sugerido

1. Rodar o [roteiro de loja fake](../dev/roteiro-loja-fake-multitenant.md) e validar isolamento na prática, antes de prometer isso comercialmente.
2. Decidir e desenhar em detalhe a triagem de primeiro contato (menu + LLM) — ataca diretamente o achado #1 (qualidade de lead), que é provavelmente o argumento comercial mais forte do produto ("todo lead contado é um lead de verdade").
3. Resolver a autenticação permanente antes de assinar o primeiro cliente novo pagante — é o gap que mais rapidamente vira incidente de confiança.
4. Formalizar onboarding de loja nova (reduzir dependência de edição manual do workflow n8n) — só compensa investir nisso quando houver 2º/3º cliente confirmado, não antes.
5. Enforcement de `lojas.limite_leads`, se o modelo comercial depender de planos com limite.

Esta ordem é uma sugestão, não uma decisão — validar com o usuário antes de agir em qualquer item.
