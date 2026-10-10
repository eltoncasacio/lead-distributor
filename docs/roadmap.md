# Roadmap / Fora de Escopo

> Consolida `Fora do Escopo/Roadmap Futuro.md` e `IDEIAS_MELHORIA.md` do projeto original. Nada aqui está implementado, salvo nota em contrário. Quando o usuário trouxer as próximas mudanças de regra de negócio, revisar esta lista primeiro.

## Ideias que pareciam já parcialmente construídas (corrigido)

- **Lembrete diário de leads pendentes** — uma versão anterior deste documento afirmava que já existia um workflow n8n pronto ("Lembrete Leads Pendentes (Diário)"), desativado, avisando vendedores sobre leads parados. Verificado ao vivo em 2026-09-11 (`n8n_list_workflows`): esse workflow **não existe** — só há 1 workflow no n8n (`Renato Motors Amarrar Lead`). Continua sendo uma ideia de roadmap válida (parecida, mas não igual, à ideia de "relatório automático para o gerente" abaixo — esse seria um lembrete individual ao vendedor, não um resumo consolidado), só que do zero, não "pronta aguardando ativação". Ver [historico/AUDITORIA_COMERCIAL_2026-09-11.md](historico/AUDITORIA_COMERCIAL_2026-09-11.md#2-achado-confirmado-divergência-sobre-o-workflow-lembrete-leads-pendentes).

## Inteligência e automação

- IA para interpretar comandos em linguagem natural (hoje só `status`/`leads` funcionam, texto exato).
- IA para classificar mensagens (lead genuíno vs. cobrança vs. spam vs. conversa interna) — havia uma proposta técnica detalhada para isso num documento antigo, marcada como "aprovada para implementação", mas **não foi encontrada em produção** na auditoria de 2026-09-11 (ver [historico/AUDITORIA_2026-09-11.md](historico/AUDITORIA_2026-09-11.md)).
- Analytics preditivo (previsão de volume, melhor horário, conversão por vendedor).

## Rastreamento e resposta

- Link rastreável de "Click to Chat" enviado junto com o lead ao vendedor, medindo tempo até o vendedor abrir a conversa.
- Redistribuição automática se o vendedor não responder/clicar em X minutos.

## Relatórios e métricas

- SLA de atendimento (tempo de resposta).
- Relatório diário automático para o gerente via WhatsApp (resumo do dia + ranking de vendedores) — distinto do lembrete de leads pendentes já construído (ver acima).
- Exportação CSV/Excel, comparativo mensal, dashboard de conversão/ROI por origem.

## Integrações externas

- Puxar leads diretamente de mais plataformas via API própria (hoje Mobiauto e Webmotors já têm webhook dedicado, NaPista chega por e-mail — ver [specs/tecnica/03-workflow-n8n.md](specs/tecnica/03-workflow-n8n.md); as demais ainda dependem de mensagem de WhatsApp).
- Sincronização com CRMs externos (Pipedrive, RD Station, HubSpot).
- Webhooks customizados para sistemas terceiros.

## Gestão e operação

- Autosserviço via WhatsApp (gerente cadastrar/remover vendedor por comando, sem abrir o Dashboard).
- Priorização/peso por vendedor na distribuição (hoje é estritamente round-robin igualitário).
- Estados de lead mais granulares (o fluxo real hoje é só `negociando`/`sem_resposta`/`sem_interesse`/`vendido`).
- Merge manual de clientes que trocam de número de telefone.
- Suporte real a múltiplas lojas simultâneas (arquitetura já é multi-tenant no banco, mas o workflow n8n tem valores hardcoded para uma única loja hoje — ver [specs/operacao/04-onboarding-nova-loja.md](specs/operacao/04-onboarding-nova-loja.md)).

## Interface mobile

- App nativo iOS/Android para gerentes/vendedores.
- Notificações push de novo lead.
