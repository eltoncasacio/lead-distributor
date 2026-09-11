# Auditoria Técnica Completa — 2026-09-11

> Seguindo o formato de `docs/prompts/auditoria.md` (o template de auditoria já estabelecido pelo projeto). Base: leitura completa de toda a documentação antiga do vault + código de `lead-distributor/` + verificação ao vivo via MCP (n8n workflow `Qj200sqS9544ao3d` e Supabase). Esta auditoria motivou a reescrita completa da documentação em `docs/` — os documentos em [`specs/`](../specs/) e [`adr/`](../adr/) refletem o estado real descrito aqui. Tudo que não pôde ser confirmado ao vivo está marcado como "não verificado".

## 1. Resumo Executivo

O sistema está em produção, funcional, para 1 loja (Renato Motors), com ~1.200 leads distribuídos. A lógica central (round-robin, deduplicação, isolamento multi-loja) está implementada corretamente no Postgres e foi corrigida de um problema real de concorrência em 31/08/2026. O maior problema encontrado não é de lógica de negócio, mas de **documentação completamente desatualizada frente ao sistema real**: o workflow n8n cresceu de 38 para 62 nós sem atualização de doc, 3 origens de lead inteiras (Facebook, Webmotors, NaPista-por-e-mail) não estavam documentadas ou estavam documentadas como "não implementadas", e documentos-chave (README/SETUP/SISTEMA do Dashboard) descreviam um produto pré-alpha quando o produto real já tem Dashboard completo em uso. 🚨 O maior risco técnico real (não de documentação) é o modelo de autenticação do Dashboard, que usa um UUID permanente na URL como credencial sem expiração.

## 2. Visão Geral do Sistema

Ver [PRD.md](../PRD.md) para a visão de produto completa. Resumo técnico: Evolution API (WhatsApp) → n8n (orquestração, roteamento multi-origem) → Supabase/Postgres (persistência + regras de negócio via RPC) → Dashboard Streamlit (gestão). 8 origens de lead ativas hoje: WhatsApp direto, iCarros, OLX, Mercado Livre, Facebook, Mobiauto, Webmotors, NaPista (e-mail).

## 3. Documentação Técnica por Workflow

Workflow ativo real: **"Renato Motors Amarrar Lead"** (`Qj200sqS9544ao3d`), 62 nós, 45 conexões, ativo, atualizado pela última vez em 2026-06-23. Detalhamento completo do grafo, dos 4 pontos de entrada e do roteador de 8 origens em [specs/tecnica/03-workflow-n8n.md](../specs/tecnica/03-workflow-n8n.md). 13 dos 62 nós foram inspecionados em configuração completa; os demais só por topologia (nome/tipo/conexões) — declarado aqui explicitamente por não terem sido verificados em detalhe.

Existe um segundo workflow, **"Lembrete Leads Pendentes (Diário)"** (`7MXTR5JegFMkihWc`, 8 nós), construído e funcional, mas **inativo**.

### Riscos por nó (amostra dos 13 nós inspecionados em detalhe)

| Nó | Risco | Observação |
|---|---|---|
| `Vendedor Encontrado?` | ⚠️ Médio | Compara `vendedor_id` com a string literal `"null"`, não com valor nulo — frágil a qualquer mudança de serialização da resposta HTTP |
| `Duplicado de Plataforma?` | 🟢 Baixo | Depende de números de telefone fixos hardcoded (iCarros/NaPista); se a plataforma trocar o número, a detecção quebra silenciosamente |
| `Extrai Dados NaPista` (código) | ⚠️ Médio | `lojaId`, URL e chave da Evolution API hardcoded no próprio nó — funciona só para esta loja; parsing por regex de HTML de e-mail é frágil a mudança de formato do remetente |
| `Separar Leads NaPista` (código, caminho legado) | ⚠️ Médio | Parser paralelo e redundante ao de e-mail acima — dois caminhos ativos para a mesma origem, não consolidados |
| `Montar Alerta` / `Enviar Alerta Conexão` | 🟢 Baixo | Tem `onError: continueRegularOutput` — falha no envio do alerta não derruba o workflow; risco é só não avisar do problema de conexão |
| Nós HTTP em geral (13 inspecionados) | ⚠️ Médio | Nenhum com retry configurado |

## 4. Análise de Risco

- 🚨 **CRÍTICO** — Autenticação do Dashboard: UUID da loja na URL como credencial permanente, sem expiração/revogação (ver [specs/tecnica/05-dashboard-streamlit.md](../specs/tecnica/05-dashboard-streamlit.md)). Fora de escopo de correção nesta rodada por decisão do usuário.
- 🚨 **CRÍTICO** — Falha ao encaminhar lead ao vendedor não é detectada nem re-tentada: lead fica "distribuído" no banco, vendedor nunca recebe, ninguém é avisado.
- ⚠️ **ATENÇÃO** — Isolamento multi-tenant depende 100% de filtro de aplicação (`loja_id`), sem RLS real como segunda camada (ver [ADR 0006](../adr/0006-isolamento-por-filtro-de-aplicacao.md)). Nunca testado com 2+ lojas em produção.
- ⚠️ **ATENÇÃO** — Página `pages/4_Leads.py` do Dashboard escreve direto no Supabase, pulando a camada `utils/queries.py` usada por todo o resto do app.
- ⚠️ **ATENÇÃO** — Regra "não remover o último gerente/vendedor ativo" só existe na UI do Dashboard, não como validação no backend.
- 💡 **MELHORIA** — Dois parsers paralelos e redundantes para a origem NaPista (WhatsApp legado + e-mail atual) — consolidar.
- 💡 **MELHORIA** — Funções `fn_status`/`fn_relatorio` no banco parecem legado morto (não chamadas por nada em produção) — candidatas a remoção.
- 💡 **MELHORIA** — Coluna `vendedores.ordem_fila` e o drag-and-drop do Dashboard não têm efeito real no round-robin — ou implementar de verdade, ou remover a UI que sugere que tem efeito.

## 5. Auditoria do Banco

Schema completo, RLS, policies e catálogo de funções em [specs/tecnica/02-modelo-de-dados.md](../specs/tecnica/02-modelo-de-dados.md). Pontos relevantes:
- 🟢 Round-robin protegido por `FOR UPDATE` + lock advisory por `(loja, cliente)` desde 31/08/2026 — sem race condition conhecida hoje.
- 🟢 Constraints `UNIQUE` corretas em `numero_whatsapp` (global) e `instancia_evolution` — previnem duplicidade de cadastro.
- ⚠️ **ATENÇÃO** — `atividades.tipo` CHECK não cobre reatribuição manual de lead (não há tipo `'lead_reatribuido'`) — aconteceu de verdade no incidente de 31/08 e não deixou rastro.
- ⚠️ **ATENÇÃO** — 7 funções (`distribuir_lead` ×2, `comando_status`, `comando_leads`, `comando_relatorio`, `fn_status`, `fn_relatorio`, `identificar_remetente`) com `search_path` mutável (advisory de segurança do Supabase) — não corrigido nesta rodada por instrução do usuário.
- ⚠️ **ATENÇÃO** — `identificar_remetente` é `SECURITY DEFINER` e executável pelos roles `anon`/`authenticated` sem autenticação adicional via API REST pública.
- 🟢 Risco de vendedor inexistente receber lead: mitigado — `distribuir_lead` sempre valida `status = 'ativo'` antes de atribuir.
- 🟢 Risco de inconsistência de status: baixo — CHECK constraints cobrem os valores válidos de `vendedores.status` e `leads.status_lead`.

## 6. Conformidade com Regras de Negócio

| Regra | Status |
|---|---|
| Round-robin justo entre vendedores ativos | ✅ Implementada corretamente (verificado no código-fonte real da função) |
| Deduplicação por duplicata exata + amarração de cliente | ✅ Implementada corretamente, mas documentação antiga descrevia errado (numeração "2 níveis" vs "3 passos" contraditória) — corrigido em [specs/regras-de-negocio/05](../specs/regras-de-negocio/05-deduplicacao.md) |
| Isolamento multi-loja | ✅ Implementada a nível de dados; ⚠️ nunca testada com 2+ lojas reais |
| Estados de vendedor (ativo/inativo/removido) | ✅ Implementada; documentação antiga citava um estado `'pausado'` inexistente |
| "100% via WhatsApp, sem integração direta com portais" | ❌ **Falsa hoje** — Mobiauto e Webmotors têm webhook HTTP dedicado; NaPista chega por e-mail |
| Comando `relatorio` | ❌ Não existe mais (renomeado para `leads`); onboarding antigo ainda citava o nome velho |
| `status`/`leads` retornam dados de "hoje" | ❌ Retornam janela fixa de 3 dias, por decisão deliberada da equipe (migration revertida de propósito) |

## 7. Sugestões Estratégicas

- 💡 Consolidar os dois parsers de NaPista num só.
- 💡 Adicionar retry nos nós HTTP críticos (ao menos "Distribuir Lead" e "Encaminhar ao Vendedor").
- 💡 Adicionar tipo `'lead_reatribuido'` ao CHECK de `atividades.tipo` antes que uma próxima reatribuição manual aconteça sem rastro.
- 💡 Se uma segunda loja for onboarded, generalizar os valores hardcoded do workflow n8n (webhook por loja, `lojaId` dinâmico) antes — hoje a automação real não é multi-tenant, só o banco é.
- 💡 Revisar o modelo de autenticação do Dashboard quando o usuário tratar pendências de robustez/segurança (fora desta rodada).

## 8. Pontos Críticos

🚨 Autenticação do Dashboard (token permanente na URL). 🚨 Falha silenciosa no encaminhamento ao vendedor sem alerta. Ambos registrados como débito técnico conhecido, não corrigidos nesta rodada por decisão explícita do usuário (esta rodada é só reorganização de documentação).

---

*Auditorias anteriores do projeto (`AUDITORIA_TECNICA_2026-02-19`, revisão pré-implementação, etc.) estão preservadas em [`historico/`](.) para referência histórica — muitos dos problemas que elas levantaram (nós duplicados, constraints ausentes) já foram resolvidos; os que ainda não foram estão listados nesta auditoria como vigentes.*
