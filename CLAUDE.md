# CLAUDE.md

Instruções para assistentes de IA (Claude Code e similares) trabalhando neste repositório.

## O que é este projeto

Dashboard Web (Streamlit) de um sistema de distribuição de leads de WhatsApp para concessionárias/revendas de veículos. A automação real de distribuição (recebimento de mensagem, round-robin, deduplicação) roda **fora deste repositório**, em n8n + funções SQL no Supabase — este repo é só a camada de gestão. Antes de qualquer tarefa, leia:

1. **[docs/PRD.md](docs/PRD.md)** — o que o sistema faz e para quem.
2. **[docs/specs/](docs/specs/)** — a spec relevante à sua tarefa (regras de negócio, operação, técnica).
3. **[docs/adr/](docs/adr/)** — antes de propor mudar uma decisão arquitetural, veja se ela já foi tomada com um trade-off explícito.

## Regra mais importante: não invente regras nem funcionalidades

Este projeto já passou por um ciclo de deriva grave entre documentação e sistema real (ver [docs/historico/AUDITORIA_2026-09-11.md](docs/historico/AUDITORIA_2026-09-11.md)) — documentos afirmavam coisas que não eram mais verdade no código/banco. Para não repetir isso:

- **Toda regra de negócio real vive no Postgres** (funções `distribuir_lead`, `identificar_remetente`, `comando_status`, `comando_leads` — ver [docs/specs/tecnica/02-modelo-de-dados.md](docs/specs/tecnica/02-modelo-de-dados.md)), não neste repositório Python. Se uma tarefa envolve mudar regra de distribuição/deduplicação/round-robin, a mudança é em SQL (via migration do Supabase), não em `utils/queries.py`.
- Se algo não estiver documentado em `docs/specs/`, **pergunte antes de assumir** — não presuma que uma funcionalidade existe ou não existe sem checar o código ou (quando disponível) o estado ao vivo via MCP do Supabase/n8n.
- Ao descobrir uma divergência entre a documentação e o código real, **atualize a documentação junto com a mudança de código** — é exatamente esse tipo de divergência acumulada que gerou a auditoria de 2026-09-11.

## Convenções do repositório

- Toda leitura/escrita ao Supabase passa por `utils/queries.py` — **exceção conhecida**: `pages/4_Leads.py` escreve direto (débito técnico registrado, não é padrão a seguir em código novo).
- Autenticação é por código único por loja (sem contas individuais) — não assuma que existe conceito de "usuário logado" além da loja.
- `vendedores.ordem_fila` e o drag-and-drop do Dashboard **não afetam** o round-robin real (que segue `criado_em`) — não trate essa coluna como fonte de verdade da fila.
- Sem suíte de testes automatizada de verdade (`test_date_filters.py`/`validate_signatures.py` são scripts avulsos contra Supabase real, não testes de CI). Não assuma cobertura de testes ao alterar código.

## Débito técnico conhecido (não corrigir por conta própria sem pedir)

Ver [docs/historico/AUDITORIA_2026-09-11.md](docs/historico/AUDITORIA_2026-09-11.md) para a lista completa (autenticação por UUID permanente na URL, falta de retry no n8n, etc.). O usuário já sinalizou que vai tratar isso em rodadas futuras, com mudanças de regra de negócio — não assuma que deve corrigir proativamente.

## Comandos úteis

```bash
source venv/bin/activate
streamlit run Home.py              # rodar o Dashboard localmente
python3 test_date_filters.py       # script de checagem de filtros de data (usa Supabase real)
python3 validate_signatures.py     # valida assinaturas de funções de utils/queries.py
```

Não há linter/formatter configurado no repositório hoje.

## Verificação ao vivo (quando disponível)

Se você tiver acesso a ferramentas MCP de Supabase/n8n, prefira **verificar o estado real** (schema, função SQL, workflow) antes de documentar ou basear uma decisão em algo — foi exatamente essa verificação que corrigiu várias afirmações erradas na reescrita de 2026-09-11 (ex.: a função `distribuir_lead` real tem 7 argumentos e lógica diferente do que estava documentado antes). Não assuma que a documentação em `docs/` está 100% correta para sempre — ela é boa no momento em que foi escrita (2026-09-11), mas pode ficar desatualizada de novo se o sistema mudar sem atualização correspondente.
