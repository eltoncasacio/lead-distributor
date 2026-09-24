# Migração de Frontend: o que o Streamlit faz hoje e viabilidade de Next.js

> Baseado em leitura completa de `Home.py`, `pages/*.py`, `utils/auth.py` e `utils/queries.py`. Objetivo: servir de referência para reescrever o Dashboard em React/Next.js sem precisar reabrir o código Python.
>
> Escrito em 2026-09-11, **revisado em 2026-09-23** — quando a tela de Triagem entrou e `utils/queries.py` chegou a 39 funções. Esta é a **Fase D** do [plano-multiloja](../../plano-multiloja.md), que recomenda concluir as Fases A, B e C antes: o front herda o modelo de autenticação e de isolamento, e construí-lo antes significa refazê-lo depois.

## 1. O que o Dashboard Streamlit faz hoje, página por página

### `Home.py` — shell da aplicação (login + navegação)

- **Login**: formulário único com campo "Código de Acesso" (`AUT-YYYYMMDD-XXXX`). Valida contra `loja_acesso.codigo_acesso` e `lojas.ativa` (ver `utils/auth.validar_codigo`).
- **Sessão**: não há cookie nem JWT. A sessão vive em `st.session_state` (memória do processo Streamlit) e é replicada na URL via `st.query_params["s"] = loja_id` — o UUID da loja fica literalmente na URL (`?s=<uuid>`) e é isso que restaura a sessão em qualquer reload (`restaurar_sessao()`, que revalida contra `lojas.ativa` a cada carregamento de página). **Não há expiração nem logout forçado** — é uma credencial permanente enquanto a URL existir.
- **Logout**: limpa `session_state` e `query_params`.
- **Navegação**: `st.navigation()` com **5 páginas**, nesta ordem — Dashboard, Leads, Triagem, Gerentes, Vendedores. Sidebar colapsável (só ícones quando fechada).

### `pages/1_Dashboard.py`

- **4 KPI cards**: Leads Hoje (com variação % vs. ontem), Último Lead Recebido (com "há X min/horas" relativo), Próximo Vendedor na Fila, Vendedores Ativos.
- **Fila de distribuição** (drag-and-drop horizontal, lib `streamlit-sortables` → `dnd-kit` por baixo): mostra vendedores ativos ordenados a partir do "próximo" da fila, com setas entre os cards. Arrastar chama `reordenar_vendedores(loja_id, novos_ids)`, que só atualiza `vendedores.ordem_fila` — **não afeta o round-robin real**, que segue `criado_em` no Postgres (ver [regras-de-negocio/01](../regras-de-negocio/01-round-robin.md)). Isso é puramente cosmético/informativo hoje.
- **Timeline de Atividades Recentes**: últimas 8 linhas de `atividades`, com timestamp relativo em pt-BR (fuso `America/Sao_Paulo`).
- **Filtro de período customizado** (data início/fim, padrão últimos 30 dias, botão "Hoje").
- **4 gráficos Plotly**: fluxo de leads por dia (linha/spline), funil de status (Recebidos → Sem Resposta / Sem Interesse / Vendido), leads por origem (barra horizontal), leads por hora (barra).
- Todos os dados vêm de `utils/queries.py`: `get_metricas_hoje`, `get_leads_ontem`, `get_leads_por_dia`, `get_leads_por_hora`, `get_leads_por_origem_comparativo`, `get_metricas_funil`, `get_atividades_recentes`, `get_leads_hoje_por_vendedor`, `get_ultimo_lead_info`, `obter_proximo_vendedor`.

### `pages/2_Gerentes.py`

- Lista todos os gerentes da loja numa tabela editável (`st.data_editor`): colunas Nome, WhatsApp, checkbox Remover.
- Botão "Adicionar Gerente" abre formulário inline (Nome + WhatsApp).
- Edição de nome/WhatsApp é auto-save ao detectar diff na tabela; delete é via checkbox "Remover" + rerun.
- Validações antes de salvar: `validar_nome`, `validar_whatsapp` + `formatar_whatsapp` (adiciona `55` e formata), e checagem de duplicidade cross-tabela (`whatsapp_ja_existe`, único entre gerentes E vendedores).
- **Regra "não remover o único gerente"**: `pode_remover = len(gerentes) > 1`, aplicada só na UI (desabilita a checkbox) — não há constraint equivalente no banco.

### `pages/3_Vendedores.py`

- Mesma mecânica de tabela editável de Gerentes, mas com uma coluna a mais: **Status** (`ativo`/`inativo`, `SelectboxColumn`), e "Excluir" em vez de "Remover" (seta `status = 'removido'`, soft-delete — vendedores removidos somem da lista mas continuam no banco).
- Regra "não pode inativar/excluir o único vendedor ativo": checada via `contar_vendedores_ativos(loja_id)` antes de aplicar, também só na UI.
- **Mensagens Prontas** (seção separada, abaixo da tabela): 2 abas — "Padrão da Loja" e "Por Vendedor" (override por vendedor específico, cai pro padrão da loja se não houver). CRUD completo (adicionar/editar/deletar), com chips de placeholder clicáveis (`{nome_cliente}`, `{vendedor_nome}`, `{anuncio}`, `{origem}`) que inserem o texto no cursor, e preview ao vivo substituindo os placeholders por valores de exemplo. A primeira mensagem da lista (por `ordem`) é a que vai automaticamente como link `wa.me` quando um lead é distribuído.

### `pages/4_Leads.py`

- Filtros: data início/fim (padrão últimos 30 dias), vendedor (dropdown, inclui inativos), origem (lista fixa: iCarros/NaPista/Mobiauto/Facebook/OLX/Mercado Livre/WhatsApp Direto), busca por texto com debounce de 300ms (`streamlit-keyup`) sobre nome/telefone/anúncio.
- Abas por status (Todos/Negociando/Sem Resposta/Sem Interesse/Vendido), cada uma com contador no próprio rótulo da aba.
- Tabela com edição inline **só da coluna Status** (`SelectboxColumn`), auto-save por diff de hash entre estado original e editado.
- **Importante para quem for portar**: esta é a única página que **escreve direto no Supabase** (`supabase.table("leads").update(...)`), sem passar por `utils/queries.py` — é um desvio de padrão já conhecido, não uma decisão a preservar na reescrita.
- Cada mudança de status grava uma linha em `atividades` via `registrar_atividade`.

### `pages/5_Triagem.py`

Entrou em 2026-09-23, no incidente NaPista. É onde um humano completa o que a automação não conseguiu: mensagens que chegaram, foram registradas em `mensagens_recebidas`, mas **não viraram lead** porque não havia telefone aproveitável do cliente.

- **3 abas** via `st.radio` horizontal (não `st.tabs`): "A revisar" (com contador no rótulo), "Já revisadas", "Todas as mensagens". A aba ativa vive em `st.session_state["triagem_aba"]`.
- **"A revisar"** é renderizada como **cards** (`st.container(border=True)`), um por mensagem, cada um com: nome/origem/horário, veículo, trecho do texto (400 chars), botão **Arquivar**, e um formulário inline com **Telefone do cliente** + **Nome** + botão **Distribuir**.
- As outras duas abas são `st.dataframe` somente leitura.

> **Decisão de design que precisa sobreviver à migração** (está no docstring do arquivo): cards, **não** `data_editor`. Cada ação aqui distribui um lead de verdade e dispara WhatsApp para um vendedor — o auto-save por diff de hash usado em `4_Leads.py` promoveria leads numa edição acidental. Na versão React, **ação destrutiva/irreversível exige clique explícito**, nunca salvamento automático.

- **Critério de "a revisar"** (`listar_mensagens_para_revisao`): `revisado_em IS NULL` **e** `telefone_extraido` vazio ou pertencente a `NUMEROS_DE_PLATAFORMA`. O filtro final roda em Python, não em SQL — puxa até 500 linhas e filtra na aplicação. Vale revisar isso na reescrita.
- **Distribuir** valida o telefone (`validar_whatsapp` + `formatar_whatsapp`) e chama a RPC `promover_mensagem_para_lead`, que chama `distribuir_lead` por dentro. **A tela não decide para quem vai** — round-robin e dedup continuam só no Postgres ([ADR 0001](../../adr/0001-postgres-rpc-dono-da-atomicidade.md)). O retorno traz `lead_id`, `vendedor_nome` e `duplicado`, e a UI dá mensagens diferentes para cada caso.
- **Arquivar** chama a RPC `arquivar_mensagem` — marca como não-lead sem apagar nada.
- Nas duas ações, o `registrar_atividade` está dentro de `try/except` que **engole a exceção de propósito**: a RPC já é atômica e o lead já existe naquele ponto; falhar ao registrar a atividade não pode desfazer nem esconder isso. Preservar esse comportamento.

### Camada de dados (`utils/queries.py`, 39 funções)

Único ponto de acesso ao Supabase (exceto a exceção acima). **Três dessas funções chamam RPC do Postgres** e não são CRUD: `get_metricas_hoje` → `comando_status`, `promover_mensagem_para_lead` → RPC de mesmo nome, `arquivar_mensagem` → RPC de mesmo nome. As outras 36 são `.table()` direto.

Todas as funções recebem `loja_id` e filtram por ele — é a *única* linha de defesa do isolamento multi-tenant (RLS não cumpre esse papel hoje, ver [regras-de-negocio/04](../regras-de-negocio/04-isolamento-multi-loja.md)). Usa a `service_role` key do Supabase (`utils/supabase_client.py`), que roda só no processo servidor do Streamlit — nunca chega ao navegador.

## 2. É viável desacoplar em Next.js?

**Sim.** Não é só trocar a tecnologia de UI — dá pra manter (e até melhorar) o mesmo modelo de segurança:

- A `service_role` key continua existindo **só no servidor** — em Next.js isso vira API Routes ou Server Actions chamando o Supabase a partir do backend, exatamente como o Streamlit faz hoje a partir do seu processo Python. O browser nunca vê essa chave, igual hoje.
- As ~30 funções de `utils/queries.py` mapeiam quase 1:1 para endpoints/Server Actions — é trabalho de tradução, não de redesenho de lógica.
- RPCs do Postgres não mudam — continuam vivendo no banco. Mas **corrigindo a versão anterior deste documento**: o frontend *já chama RPC direto hoje*, em três pontos (`comando_status`, `promover_mensagem_para_lead`, `arquivar_mensagem`). A versão Next.js precisa chamar as mesmas, do servidor. O que continua exclusivo do n8n é `distribuir_lead` (chamada direta), `identificar_remetente` e `comando_leads`.

### O que precisa ser redesenhado (não é "portar componente por componente")

| Streamlit | Equivalente em React/Next.js | Observação |
|---|---|---|
| `st.data_editor` (edição inline em tabela, auto-save) | Data-grid editável (ex.: TanStack Table + inputs controlados, ou uma lib de grid pronta) + chamada de API com salvamento otimista | Streamlit resolve isso "de graça"; em React é a peça que exige mais trabalho de UI |
| `streamlit-sortables` (drag-and-drop da fila) | `dnd-kit` direto (é a mesma lib por baixo) | Mais simples sem a camada Streamlit no meio |
| Plotly via `st.plotly_chart` | `react-plotly.js` (mesma lib `plotly.js`) ou trocar por outra lib de gráficos | Decisão de gosto, não de viabilidade — os dados/lógica dos gráficos não mudam |
| `st.session_state` + `query_params["s"]` | Cookie de sessão (ideal: assinado/httpOnly) ou, no mínimo, o mesmo padrão de UUID em cookie em vez de querystring | Ver ponto de decisão abaixo |
| `st.toast` / mensagens de sucesso/erro | Toast library (ex.: Sonner, ou similar) | Trivial |
| Cards da Triagem com ação explícita | Lista de cards + botões, **sem** auto-save | Não converter em grid editável: cada ação distribui lead de verdade |
| `st.radio` horizontal como abas (Triagem) | Tabs normais | Streamlit usa radio aqui só para manter o contador no rótulo |

### Ponto que vale mais discussão: autenticação

O modelo atual (UUID permanente na URL, sem expiração) já é um débito técnico conhecido — link vazado = acesso total e indefinido à loja. Uma reescrita de frontend é o momento natural para resolver isso (ex.: cookie de sessão assinado com expiração, em vez de UUID na querystring), mas isso é uma decisão de produto/segurança independente de "ser Next.js" — dá pra fazer a migração de UI mantendo o modelo de auth atual e resolver isso depois, ou resolver junto. Recomendo tratar como duas decisões separadas.

### Estratégia de migração recomendada

Reescrever página por página, rodando em paralelo ao Streamlit (ex.: `app.dominio.com` novo apontando pro mesmo Supabase). Ordem recomendada, alinhada com a Fase D do [plano-multiloja](../../plano-multiloja.md):

**Gerentes → Vendedores → Triagem → Leads → Dashboard**

Começa pelo CRUD direto (Gerentes/Vendedores), que valida o modelo de dados e de auth cedo e com risco baixo. Triagem vem em seguida porque é pequena e exercita a chamada de RPC a partir do servidor. Dashboard fica por último: é onde estão os gráficos e o drag-and-drop.

**Critério de corte entre telas**: cada tela migrada precisa ter paridade funcional com a do Streamlit antes da próxima começar, e o Streamlit continua no ar durante toda a migração.
