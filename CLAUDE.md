# CLAUDE.md

Instruções para assistentes de IA (Claude Code e similares) trabalhando neste repositório.

## O que é este projeto

Dashboard Web (Streamlit) de um sistema de distribuição de leads de WhatsApp para concessionárias/revendas de veículos. A automação real de distribuição (recebimento de mensagem, round-robin, deduplicação) roda **fora deste repositório**, em n8n + funções SQL no Supabase — este repo é só a camada de gestão. Antes de qualquer tarefa, leia:

1. **[docs/PRD.md](docs/PRD.md)** — o que o sistema faz e para quem.
2. **[docs/specs/](docs/specs/)** — a spec relevante à sua tarefa (regras de negócio, operação, técnica).
3. **[docs/adr/](docs/adr/)** — antes de propor mudar uma decisão arquitetural, veja se ela já foi tomada com um trade-off explícito.

## Continuidade entre sessões — leia isto primeiro

**Cada sessão de IA começa do zero.** Nada do que foi conversado antes vem junto: nem credenciais, nem decisões, nem o que já foi tentado. O usuário costuma lembrar de algo "que combinamos" — e o assistente não tem isso. **Se não está escrito em arquivo, não existe.**

Por isso, antes de propor qualquer coisa:

0. **Leia [docs/dev/handoff-2026-10-10.md](docs/dev/handoff-2026-10-10.md)** — o que foi feito na última sessão, o que está em produção e o que está só no repo, e os próximos passos em ordem. É o ponto de retomada dos comandos por WhatsApp.
1. **Rode a auditoria** — `python3 auditoria_producao.py`. Em 5 segundos responde se o sistema está distribuindo, qual o ritmo de leads, se a fila está coerente e **se alguma origem parou de dar sinal**. É a foto do estado real, não do estado documentado.
2. **Leia [docs/plano-multiloja.md](docs/plano-multiloja.md)** — o roteiro vigente, com as fases, o que já foi feito e o que falta. É onde as decisões de rumo ficam registradas.
3. **Leia o [RUNBOOK do incidente NaPista](docs/historico/incidentes/2026-09-23-napista-leads-perdidos/RUNBOOK.md) e o [ACEITE](docs/historico/incidentes/2026-09-23-napista-leads-perdidos/ACEITE.md)** — o que foi aplicado em produção, com `versionId`, e principalmente **o que foi deixado sem testar de propósito**.

### Ao terminar uma sessão que mudou algo

Atualize o arquivo correspondente **na mesma sessão**, não "depois":

| Mudou | Atualize |
|---|---|
| rumo, prioridade, fase | `docs/plano-multiloja.md` |
| workflow n8n em produção | RUNBOOK do incidente (com `versionId` antes/depois) |
| algo que ficou sem teste | `ACEITE.md`, dizendo **por que** não foi testado |
| entendimento de como o sistema funciona | a spec em `docs/specs/` correspondente |

Diagnóstico que se provou errado **não se apaga**: corrige-se com a data e o motivo. Foi assim que a conclusão "a NaPista cortou o e-mail" foi desfeita em 2026-09-23 — a versão errada continua no RUNBOOK, marcada como errada, porque saber que ela existiu evita refazer o mesmo caminho.

### Credenciais

Nenhuma credencial vive no repositório. O `.env` (fora do git) tem `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` e, desde 2026-10-10, `N8N_API_KEY` (chave da API **pública** do n8n, `aud: public-api`, expira em 2026-11-09). Chave da API do n8n e do MCP são **coisas diferentes e não intercambiáveis** — o MCP do n8n só lê, não escreve workflow. Se `N8N_API_KEY` estiver ausente ou vencida, peça uma nova ao dono — para ele gravar no `.env`, não colar no chat.

## Regra mais importante: não invente regras nem funcionalidades

Este projeto já passou por um ciclo de deriva grave entre documentação e sistema real (ver [docs/historico/AUDITORIA_2026-09-11.md](docs/historico/AUDITORIA_2026-09-11.md)) — documentos afirmavam coisas que não eram mais verdade no código/banco. Para não repetir isso:

- **Toda regra de negócio real vive no Postgres** (funções `distribuir_lead`, `identificar_remetente`, `comando_status`, `comando_leads` — ver [docs/specs/tecnica/02-modelo-de-dados.md](docs/specs/tecnica/02-modelo-de-dados.md)), não neste repositório Python. Se uma tarefa envolve mudar regra de distribuição/deduplicação/round-robin, a mudança é em SQL (via migration do Supabase), não em `utils/queries.py`.
- Se algo não estiver documentado em `docs/specs/`, **pergunte antes de assumir** — não presuma que uma funcionalidade existe ou não existe sem checar o código ou (quando disponível) o estado ao vivo via MCP do Supabase/n8n.
- Ao descobrir uma divergência entre a documentação e o código real, **atualize a documentação junto com a mudança de código** — é exatamente esse tipo de divergência acumulada que gerou a auditoria de 2026-09-11.

## Convenções do repositório

- Toda leitura/escrita ao Supabase passa por `utils/queries.py` — **exceção conhecida**: `pages/4_Leads.py` escreve direto (débito técnico registrado, não é padrão a seguir em código novo).
- Autenticação é por código único por loja (sem contas individuais) — não assuma que existe conceito de "usuário logado" além da loja.
- `vendedores.ordem_fila` e o drag-and-drop do Dashboard **não afetam** o round-robin real (que segue `criado_em`) — não trate essa coluna como fonte de verdade da fila.
- **Existe suíte de testes, mas ela cobre uma coisa só**: `tests/` roda com pytest, sem rede, com um Supabase falso (`tests/fake_supabase.py`), e prova o **isolamento multi-loja** de `utils/queries.py` — que nenhuma escrita alcança outra loja, e que nenhuma função nova entra sem filtro de `loja_id`. Rode com `python3 -m pytest tests/ -q`. **Não há cobertura de mais nada**: páginas Streamlit, gráficos e filtros de data seguem sem teste. `test_date_filters.py` e `validate_signatures.py` continuam sendo scripts avulsos contra o Supabase real, não testes.

## Débito técnico conhecido (não corrigir por conta própria sem pedir)

Ver [docs/historico/AUDITORIA_2026-09-11.md](docs/historico/AUDITORIA_2026-09-11.md) para a lista completa (autenticação por UUID permanente na URL, falta de retry no n8n, etc.). O usuário já sinalizou que vai tratar isso em rodadas futuras, com mudanças de regra de negócio — não assuma que deve corrigir proativamente.

## Comandos úteis

```bash
source venv/bin/activate
streamlit run Home.py              # rodar o Dashboard localmente
python3 test_date_filters.py       # script de checagem de filtros de data (usa Supabase real)
python3 validate_signatures.py     # valida assinaturas de funções de utils/queries.py
python3 auditoria_producao.py      # foto do estado real de produção (somente leitura) — só Renato Motors
python3 monitor_lojas.py           # todas as lojas ativas; roda sozinho de hora em hora (docs/dev/monitor-lojas.md)
```

Não há linter/formatter configurado no repositório hoje.

## Verificação ao vivo (quando disponível)

Se você tiver acesso a ferramentas MCP de Supabase/n8n, prefira **verificar o estado real** (schema, função SQL, workflow) antes de documentar ou basear uma decisão em algo — foi exatamente essa verificação que corrigiu várias afirmações erradas na reescrita de 2026-09-11 (ex.: a função `distribuir_lead` real tem 7 argumentos e lógica diferente do que estava documentado antes). Não assuma que a documentação em `docs/` está 100% correta para sempre — ela é boa no momento em que foi escrita (2026-09-11), mas pode ficar desatualizada de novo se o sistema mudar sem atualização correspondente.
