# Dashboard Web (Streamlit)

> Baseado em leitura completa do código-fonte em `lead-distributor/` (2026-09-11). Substitui `Técnica/11` do vault e o `README.md`/`SETUP.md`/`SISTEMA.md` antigos do próprio app, que descreviam um projeto "Semana 1/2/3" pré-alpha — o Dashboard descrito neste documento já está implementado e em uso.

## Stack

Streamlit + Supabase (`supabase-py`, chave de serviço) + Plotly (gráficos) + `streamlit-sortables` (drag-and-drop) + `streamlit-keyup` (busca com debounce). Deploy: Streamlit Cloud. Sem lockfile — `requirements.txt` usa apenas versões mínimas (`>=`), sem teto.

## Autenticação

Login por **código de acesso único por loja** (`AUT-YYYYMMDD-XXXX`, tabela `loja_acesso`). Não há contas de usuário individuais — todo gerente da loja usa o mesmo código. Ao validar o código, a sessão é mantida via `st.query_params["s"] = loja_id` (o UUID da loja fica na URL) e restaurada em cada carregamento de página lendo esse parâmetro. **Não há expiração nem revogação** desse "token" — ele é, na prática, uma credencial permanente. Ver débito técnico abaixo.

## Páginas

| Página | Função |
|---|---|
| `Home.py` | Login, layout, navegação |
| `1_📊_Dashboard.py` | KPIs do dia, fila de distribuição (drag-and-drop — não afeta o round-robin real, ver [regras-de-negocio/01](../regras-de-negocio/01-round-robin.md)), funil de conversão, leads por origem/horário/dia, filtro de período customizado |
| `2_👨‍💼_Gerentes.py` | CRUD de gerentes |
| `3_👤_Vendedores.py` | CRUD de vendedores + templates de "Mensagens Prontas" (padrão da loja e overrides por vendedor) |
| `4_Leads.py` | Lista de leads com filtros (data, vendedor, origem, busca), abas por status, edição inline de status |

## Acesso a dados

Camada única em `utils/queries.py` (~30 funções). **Exceção**: `pages/4_Leads.py` escreve diretamente no Supabase (`supabase.table("leads").update(...)`), pulando essa camada — é a única página que faz isso.

O cálculo de "leads hoje" no Dashboard é feito **no cliente** (Python), porque a RPC `comando_status` retorna uma janela fixa de 3 dias, não "hoje" (ver [operacao/02-comandos-whatsapp.md](../operacao/02-comandos-whatsapp.md)) — isso não é um bug do Dashboard, é uma escolha deliberada de manter o comando de WhatsApp com janela de 3 dias enquanto o Dashboard mostra "hoje" de verdade.

## Débito técnico conhecido (registrado, não corrigido nesta rodada)

- **Autenticação fraca**: UUID da loja na URL funciona como credencial permanente sem expiração — qualquer pessoa que obtenha essa URL (histórico do navegador, referrer, print compartilhado) tem acesso total ao Dashboard daquela loja.
- **Sem confirmação antes de excluir** gerente/vendedor (delete acontece direto ao marcar o checkbox).
- **Regra "não remover o último gerente/vendedor ativo" só existe na UI**, não como constraint/validação no backend — uma chamada direta à função de deleção não teria essa proteção.
- **Sem suíte de testes automatizada**: `test_date_filters.py` e `validate_signatures.py` são scripts avulsos que rodam contra um Supabase real, não testes de CI.
- **Sem cache de queries** (`@st.cache_data` não é usado) — toda renderização de página reconsulta tudo.
- Funções mortas em `utils/queries.py` (`get_fila_distribuicao`, `get_leads_por_vendedor`, `get_limite_leads`) e em `utils/ui.py` (`render_header`, `render_metric_card`, explicitamente marcadas `DEPRECATED`).
- `utils/theme.py` tem estrutura de dark mode nunca finalizada (`get_theme()`/`set_theme()` sempre retornam/forçam `"light"`).
