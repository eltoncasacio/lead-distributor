# Sistema de Distribuição de Leads

Distribuição automática de leads de WhatsApp e classificados (iCarros, OLX, Mobiauto, Webmotors, Mercado Livre, Facebook, NaPista) para vendedores, em round-robin justo, com deduplicação e continuidade de atendimento por cliente. Vendedores e gerentes operam por comandos de WhatsApp (`status`, `leads`); gerentes têm também um Dashboard Web para gestão.

Este repositório contém o **Dashboard Web** (Streamlit). A automação de distribuição roda em n8n + Supabase (fora deste repositório — ver [docs/specs/tecnica/](docs/specs/tecnica/)).

## Contexto e documentação

Este projeto tem uma base de documentação completa em `docs/`, escrita e verificada contra o sistema real (banco de dados e workflow n8n em produção), não apenas contra intenção original:

- **[docs/PRD.md](docs/PRD.md)** — visão de produto, problema, público-alvo, escopo real.
- **[docs/specs/](docs/specs/)** — regras de negócio, operação (fluxo/comandos/erros/onboarding) e arquitetura técnica, uma spec por tema.
- **[docs/adr/](docs/adr/)** — decisões de arquitetura já tomadas, com contexto e trade-offs.
- **[docs/historico/](docs/historico/)** — auditorias técnicas anteriores e o registro do incidente de race condition de 31/08/2026.
- **[docs/roadmap.md](docs/roadmap.md)** — ideias futuras, claramente marcadas como não implementadas.
- **[CLAUDE.md](CLAUDE.md)** — instruções para assistentes de IA trabalhando neste repositório.

Se algo neste README parecer desatualizado no futuro, a fonte de verdade é sempre `docs/specs/` — atualize os dois juntos.

## Stack

Python 3.11 · [Streamlit](https://streamlit.io/) · [Supabase](https://supabase.com/) (Postgres + RPC, acessado via `service_role` key) · [Plotly](https://plotly.com/python/) (gráficos) · `streamlit-sortables` (fila drag-and-drop) · `streamlit-keyup` (busca com debounce).

## Estrutura do projeto

```
lead-distributor/
├── Home.py                  # Entry point: login, layout, navegação
├── pages/
│   ├── 1_📊_Dashboard.py    # KPIs, funil, gráficos de origem/horário
│   ├── 2_👨‍💼_Gerentes.py     # CRUD de gerentes
│   ├── 3_👤_Vendedores.py    # CRUD de vendedores + mensagens prontas
│   └── 4_Leads.py           # Lista de leads, filtros, edição de status
├── utils/
│   ├── auth.py              # Login por código de loja, sessão via query param
│   ├── queries.py           # Camada de acesso ao Supabase (única, exceto 4_Leads.py)
│   ├── supabase_client.py   # Factory do client Supabase (st.secrets → .env)
│   ├── theme.py             # CSS/paleta (dark mode nunca finalizado)
│   ├── ui.py                # Componentes de UI reutilizáveis
│   └── validators.py        # Validação de nome/whatsapp
├── docs/                    # PRD, specs, ADRs, histórico — ver acima
├── requirements.txt
└── .streamlit/config.toml
```

## Como rodar localmente

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # preencher SUPABASE_URL e SUPABASE_SERVICE_KEY
streamlit run Home.py
```

> Não existe `.env.example` neste repositório ainda — crie um `.env` com `SUPABASE_URL` e `SUPABASE_SERVICE_KEY` manualmente antes de rodar (ver `utils/supabase_client.py` para as variáveis exatas esperadas). Em produção (Streamlit Cloud), as mesmas chaves são lidas de `st.secrets`.

## Login

Não há cadastro de usuário individual — o Dashboard é acessado por um código único por loja, formato `AUT-YYYYMMDD-XXXX` (tabela `loja_acesso` no Supabase). Ver [docs/adr/0004-autenticacao-por-token-de-loja.md](docs/adr/0004-autenticacao-por-token-de-loja.md) para o racional e as limitações conhecidas desse modelo.

## Estado do projeto

Em produção real para 1 loja (Renato Motors), ~1.200 leads distribuídos até 2026-09-11. Não é mais um projeto "em construção" — Dashboard, CRUD de vendedores/gerentes, lista de leads e mensagens prontas estão todos implementados e em uso. Débito técnico conhecido (não corrigido nesta rodada de reorganização de documentação) está listado em [docs/historico/AUDITORIA_2026-09-11.md](docs/historico/AUDITORIA_2026-09-11.md).
