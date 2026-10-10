# PRD — Sistema de Distribuição de Leads

> Documento de produto. Descreve o que o sistema **é hoje**, para quem, e por quê. Regras de negócio detalhadas estão em [`specs/regras-de-negocio/`](specs/regras-de-negocio/); arquitetura técnica em [`specs/tecnica/`](specs/tecnica/); decisões de projeto em [`adr/`](adr/).

## 1. Problema

Concessionárias e revendas de veículos (e negócios similares, como imobiliárias com múltiplos corretores) recebem leads de várias plataformas de classificados (iCarros, OLX, Mobiauto, Webmotors, Mercado Livre, NaPista) e do WhatsApp direto — todos convergindo para **um único número de WhatsApp da loja**. Sem um sistema de distribuição:

- Vendedores disputam o mesmo cliente manualmente.
- Leads se perdem ou demoram a ser respondidos.
- Não há como saber quem atendeu quem, nem cobrar produtividade por vendedor.

## 2. Proposta

Um sistema que recebe automaticamente as mensagens de todas as origens no WhatsApp da loja (ou por integração direta, quando a plataforma oferece webhook/e-mail), identifica se quem está escrevendo é um **cliente (lead)**, um **vendedor** ou um **gerente**, e:

- Se é lead → distribui automaticamente para o próximo vendedor disponível (round-robin), evitando duplicidade e brigando por cliente.
- Se é vendedor/gerente → responde comandos fixos (`status`, `leads`) via WhatsApp, sem necessidade de abrir nenhum app.
- Gerentes também têm acesso a um **Dashboard Web** para gestão completa (vendedores, leads, métricas).

## 3. Público-alvo

- Concessionárias/revendas de veículos com 2+ vendedores recebendo leads por WhatsApp e classificados.
- Times de vendas via WhatsApp em geral (ex.: imobiliárias) que querem distribuição justa sem adotar um CRM pesado.
- **Não é para**: quem já usa um CRM completo, negócios que recebem leads só por e-mail/formulário sem WhatsApp, ou quem precisa de triagem por IA mais sofisticada que uma classificação fixa de origem (ver §7, Fora de Escopo).

## 4. Modelo de interação

- **Vendedores e gerentes**: 100% via WhatsApp. Sem app, sem login — apenas dois comandos de texto (`status`, `leads`). Zero curva de aprendizado.
- **Gerentes**: adicionalmente têm acesso a um Dashboard Web (Streamlit), autenticado por um código de acesso por loja (formato `AUT-YYYYMMDD-XXXX`), para gestão de vendedores, gerentes, leads e mensagens prontas, e visualização de métricas.

## 5. Princípios do produto

- **Round-robin justo**: todo vendedor ativo recebe leads na mesma proporção, sem favorecimento manual (ver [ADR 0001](adr/0001-postgres-rpc-dono-da-atomicidade.md)).
- **Continuidade do atendimento**: um cliente que volta a escrever fala com o mesmo vendedor de antes, quando esse vendedor ainda está ativo (regra de "amarração", [spec 05](specs/regras-de-negocio/05-deduplicacao.md)).
- **Isolamento total entre lojas**: cada loja é um tenant isolado — vendedores, leads e configurações nunca vazam entre lojas.
- **Simplicidade operacional para quem vende**: a interface do vendedor é o WhatsApp que ele já usa, sem sistema novo para aprender.

## 6. Escopo atual (produção real, verificado em 2026-09-11)

O sistema está em produção para **1 loja ativa** (Renato Motors), com 6 vendedores, 1 gerente, ~1.200 leads distribuídos. A arquitetura é multi-tenant (suporta múltiplas lojas), mas só há uma loja onboarded até o momento.

Origens de lead **realmente implementadas e ativas** no workflow de produção (verificado ao vivo, não apenas documentado — ver [spec técnica 03](specs/tecnica/03-workflow-n8n.md)):

| Origem | Canal de entrada | Observação |
|---|---|---|
| WhatsApp direto | WhatsApp (Evolution API) | Origem padrão ("Outros") |
| iCarros | WhatsApp (número fixo da plataforma) | Identificado por número do remetente |
| OLX | WhatsApp | Identificado por palavra-chave na mensagem |
| Mercado Livre | WhatsApp | Identificado por palavra-chave na mensagem |
| Facebook (Ads/Catálogo) | WhatsApp | Identificado por metadado `entryPointConversionApp` do payload |
| Mobiauto | Webhook HTTP dedicado | Integração direta, não passa pelo WhatsApp |
| Webmotors | Webhook HTTP dedicado | Integração direta, não passa pelo WhatsApp |
| NaPista | **E-mail (Gmail)** | Não chega por WhatsApp nem webhook — é parseado de e-mails recebidos via Gmail Trigger. Existe também um caminho legado por número de WhatsApp fixo, mantido em paralelo (ver débito técnico em [historico/AUDITORIA_2026-09-11.md](historico/AUDITORIA_2026-09-11.md)) |

Isso contradiz a documentação antiga do projeto, que afirmava "100% via WhatsApp, sem integrações diretas com portais" — essa afirmação **não é mais verdadeira** e foi removida desta reescrita.

Funcionalidades do Dashboard Web hoje: KPIs do dia, fila de distribuição (drag-and-drop visual — **atenção**: reordenar aqui não altera a ordem real do round-robin, que segue `criado_em`, ver débito técnico), gráficos de funil/origem/horário, CRUD de gerentes e vendedores, lista de leads com filtro e edição de status, mensagens prontas (templates de resposta por vendedor/loja).

## 7. Fora de escopo (hoje)

Ver [roadmap.md](roadmap.md) para a lista completa de ideias futuras. Destaques que **não** estão implementados apesar de aparecerem em conversas/rascunhos antigos:
- Classificação de mensagens por IA (proposta em documento antigo, **não encontrada no workflow de produção**).
- Redistribuição automática por timeout de resposta do vendedor.
- Múltiplas lojas para o mesmo gerente.
- Merge manual de clientes que trocam de número.
- SLA e fechamento automático de lead.

Uma versão anterior deste documento (mesma data) citava um segundo workflow n8n, "Lembrete Leads Pendentes (Diário)", já construído mas desativado. Verificado ao vivo em 2026-09-11 na auditoria comercial (`n8n_list_workflows`, sem filtro e com `active:false`): **esse workflow não existe** — há apenas 1 workflow no ambiente n8n conectado (`Renato Motors Amarrar Lead`). A afirmação anterior estava incorreta e foi removida. Ver [historico/AUDITORIA_COMERCIAL_2026-09-11.md](historico/AUDITORIA_COMERCIAL_2026-09-11.md#2-achado-confirmado-divergência-sobre-o-workflow-lembrete-leads-pendentes).

## 8. Métricas relevantes hoje

Não há metas formais documentadas. O Dashboard expõe: leads/dia, funil de conversão por status, leads por origem, leads por horário, leads por vendedor. Usar esses dados como base para definir metas quando o produto amadurecer.
