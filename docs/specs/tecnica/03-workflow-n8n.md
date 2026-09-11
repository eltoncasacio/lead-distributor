# Workflow n8n

> Verificado ao vivo via MCP do n8n em 2026-09-11. Substitui `Técnica/08 - Workflow n8n - Documentação Detalhada.md`, que descrevia uma versão de 38 nós — o workflow de produção real tem hoje **62 nós e 45 conexões**. 13 dos 62 nós foram inspecionados em detalhe de configuração (não apenas topologia); o restante foi mapeado só por nome/tipo/conexões.

## Identidade do workflow

- **Nome real em produção**: `Renato Motors Amarrar Lead`
- **ID**: `Qj200sqS9544ao3d`
- **Status**: ativo
- **Última atualização**: 2026-06-23

Existem outras versões no mesmo ambiente n8n, todas **arquivadas** (não ativas, não usadas): `Renato Motors` (44 nós), `Renato Motors v0` (30 nós), `Renato Motors Amarrar Lead v2` (43 nós) — esta última é notável: foi criada em 06/03, ficou ativa por poucas horas e foi revertida/arquivada no mesmo dia, e a v1 original continuou recebendo nós novos depois disso (62 hoje) — ou seja, o "v2" **não é** a versão mais atual, apesar do nome. Não usar o nome do workflow como indicador de qual é a versão vigente — sempre confirmar por `active: true`.

## Pontos de entrada (4 triggers/webhooks)

1. **Webhook** (nó `n8n-nodes-base.webhook`) — recebe todos os eventos da instância Evolution API da loja (mensagens e eventos de conexão).
2. **Webhook Mobiauto** — endpoint HTTP dedicado só para leads da Mobiauto.
3. **Webhook Webmotors** — endpoint HTTP dedicado só para leads da Webmotors. **Não documentado em nenhum lugar antes desta reescrita** — a documentação de produto antiga chegava a afirmar que não havia integração direta com portais.
4. **Gmail Trigger** — lê e-mails recebidos; um filtro (`Origem NaPista`, checa se o remetente contém "NaPista") separa e-mails da NaPista para extração.

## Grafo principal (mensagem de WhatsApp)

```
Webhook → É Mensagem? ─(não)→ Montar Alerta → Enviar Alerta Conexão
              │(sim)
              ▼
        Filtro fromMe ─(é eco)→ NoOp
              │
        Normaliza Dados → Filtro Msg Vazia → Identificar Loja → Loja Encontrada?
                                                                       │
                                                          Preparar Dados Loja
                                                                       │
                                                          Identificar Remetente (RPC)
                                                                       │
                                                             Não É Lead? (gerente/vendedor)
                                                     (sim) ↙                    ↘ (não, é lead)
                                          Identificar Comando              Verificar Origem
                                          (status/leads/não reconhecido)   (8 branches, ver abaixo)
```

## Roteador "Verificar Origem" (8 branches, avaliados nessa ordem)

| # | Branch | Condição real (verificada no nó) |
|---|---|---|
| 1 | iCarros | `remetenteNumero == "551130044558"` |
| 2 | NaPista | `mensagemTexto` contém `"napista"` |
| 3 | NaPista (regra duplicada) | `remetenteNumero == "551131361712"` — mesma saída da regra 2 |
| 4 | OLX | `mensagemTexto` contém `"olx"` |
| 5 | Mobiauto | `origem == "Mobiauto"` (setado pelo Webhook Mobiauto antes de convergir aqui) |
| 6 | Mercado Livre | `mensagemTexto` contém `"mercadolivre"` |
| 7 | Facebook | campo `contextInfo.entryPointConversionApp` do payload original do Webhook contém `"facebook"` (leads de anúncio/catálogo do Facebook que chegam via WhatsApp) |
| 8 | Webmotors | `origem == "Webmotors"` (setado pelo Webhook Webmotors) |
| — | Outros (fallback) | nenhuma das anteriores — tratado como "WhatsApp Direto" |

Cada branch tem seu próprio nó "Prepara Dados {Origem}" que formata o payload antes de convergir em **Normalizar Saída Lead** → **Loop Over Items** → **Distribuir Lead** (RPC).

### Caso especial: NaPista tem dois caminhos paralelos e distintos

1. **Caminho legado (dentro de "Verificar Origem")**: ativado por número de WhatsApp fixo ou palavra "napista" na mensagem → nó `Separar Leads NaPista` (parseia um link `wa.me/+<numero>` e um nome entre `*asteriscos*` de uma mensagem de template do WhatsApp) → `Prepara Dados NaPista`.
2. **Caminho novo (Gmail)**: `Gmail Trigger` → `Origem NaPista` (filtro por remetente) → `Extrai Dados NaPista` (parseia HTML de e-mail por regex: nome, telefone, e-mail, CPF, veículo, mensagem) → junta no fluxo principal a partir de `Normaliza Dados`, como se fosse uma mensagem de WhatsApp normal, com `remetenteNumero` = telefone extraído do e-mail, ou um número fixo de fallback se não achar telefone no e-mail.

Isso significa que **hoje existem dois parsers de NaPista diferentes, ativos ao mesmo tempo**, um herdado de quando a origem chegava por WhatsApp e outro para quando passou a chegar por e-mail. Não há indicação de qual efetivamente recebe leads reais hoje — ambos continuam no workflow ativo. Vale investigar/consolidar quando o usuário decidir revisar regras de negócio (fora do escopo desta rodada).

O código de `Extrai Dados NaPista` tem o `lojaId`, a URL e a chave da Evolution API **hardcoded no próprio node** (não usa variável de ambiente do n8n) — mesma situação do nó de alerta de conexão abaixo. Por instrução do usuário, isso é uma limitação conhecida do plano gratuito do n8n (que não oferece variáveis de ambiente) e não é tratada como pendência de segurança nesta rodada.

## Alerta de conexão da Evolution API (não documentado antes)

Quando o Webhook principal recebe um evento que **não** é mensagem (`É Mensagem?` = não), o workflow monta uma mensagem de alerta (`Montar Alerta`, nó de código) lendo `body.data.state` do payload — `close` vira "❌ DESCONECTADO" com aviso de que leads podem se perder, `open` vira "✅ RECONECTADO" — e envia via `Enviar Alerta Conexão` (chamada HTTP direta à Evolution API, `apikey` também hardcoded no nó) para um número de WhatsApp fixo (presumivelmente o operador/dono do sistema). Esse nó tem `onError: continueRegularOutput`, ou seja, se o envio do alerta falhar, não derruba a execução do workflow.

## Distribuição e comandos (nós finais, comuns a lead e comando)

- **Identificar Comando** (switch de 3 saídas: `status`, `leads`, `Não Reconhecido`) → `Buscar Status`/`Buscar Leads` (RPC via HTTP) → `Montar Resp Status`/`Montar Resp Leads` → `Enviar Resp Comando`.
- **Distribuir Lead** → **Vendedor Encontrado?** (compara `vendedor_id` com a string `"null"`, não com `null` real — fragilidade já sinalizada em auditorias anteriores do projeto, ainda presente) → **Duplicado de Plataforma?** (duplicado E remetente é número oficial iCarros/NaPista → NoOp; senão → `Buscar Mensagens Prontas` → `Montar Notificação` → `Encaminhar ao Vendedor`).

## Workflow separado: "Lembrete Leads Pendentes (Diário)"

- **ID**: `7MXTR5JegFMkihWc`, **status: inativo**, 8 nós.
- Grafo: `Schedule Trigger` → `Buscar Vendedores Ativos` → (loop) `Buscar Leads Pendentes` por vendedor → `Tem Leads Pendentes?` → se sim, `Formatar Mensagem Lembrete` → `Enviar Lembrete WhatsApp`.
- É a implementação de uma ideia que estava listada como "melhoria futura não implementada" em documentação antiga (`IDEIAS_MELHORIA.md`) — na verdade **já foi construída**, só não está ligada. Ver [PRD §7](../../PRD.md) e [roadmap.md](../../roadmap.md).

## O que não foi confirmado

- Não foi encontrado nenhum nó de classificação de mensagens por IA/LLM na lista de 62 nós (nenhum tipo de node de IA/HTTP para OpenAI/Anthropic identificável pelo nome). A proposta de classificação por IA documentada em versão antiga do projeto **parece não ter sido implementada** em produção — mas isso não foi verificado node a node em 100% dos 62 nós, então trate como "não encontrado", não como "confirmado ausente".
- Configuração de retry nos nós HTTP não foi verificada em todos os 62 nós (apenas nos 13 inspecionados, nenhum tinha retry configurado). Ver [operacao/03-tratamento-de-erros.md](../operacao/03-tratamento-de-erros.md).
