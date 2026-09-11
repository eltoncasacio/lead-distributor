# Fluxo Principal

> Verificado ao vivo contra o workflow n8n de produção **"Renato Motors Amarrar Lead"** (id `Qj200sqS9544ao3d`, ativo, 62 nós), 2026-09-11. Substitui `Operação/01` e `WORKFLOW-EXPLICACAO.md` do vault antigo, que descreviam uma versão de 38 nós já defasada.

## Entradas (webhooks/triggers)

O workflow tem **4 pontos de entrada** distintos, todos convergindo no mesmo pipeline de "Normaliza Dados" → identificação → distribuição:

1. **Webhook principal** (Evolution API — WhatsApp da loja): recebe todo evento da instância, inclusive eventos que não são mensagem (ex.: mudança de estado da conexão — ver alerta abaixo).
2. **Webhook Mobiauto**: endpoint HTTP dedicado, a plataforma manda o lead direto (nome, telefone, veículo, mensagem), sem passar pelo WhatsApp.
3. **Webhook Webmotors**: mesmo padrão do Mobiauto, endpoint próprio.
4. **Gmail Trigger**: e-mails recebidos na caixa configurada são varridos; um filtro por remetente detecta e-mails da NaPista e extrai os dados por regex do HTML do e-mail.

## Caminho de uma mensagem de WhatsApp (entrada 1)

1. **É Mensagem?** — separa eventos de mensagem de outros eventos do webhook Evolution (ex.: status de conexão).
   - Se **não é mensagem**: monta um alerta de conexão (ver abaixo) e não segue no fluxo de leads.
   - Se é mensagem: segue.
2. **Filtro fromMe** — descarta mensagens enviadas pela própria loja (eco do que o sistema mandou).
3. **Normaliza Dados** — padroniza os campos (remetente, texto, timestamp, `pushName`).
4. **Filtro Msg Vazia** — descarta mensagens sem texto.
5. **Identificar Loja** (`GET` na tabela `lojas` por `instancia_evolution`) → **Loja Encontrada?** — se não, a mensagem é descartada silenciosamente (loja desconhecida/instância mal configurada).
6. **Identificar Remetente** (RPC `identificar_remetente`) → classifica em `gerente` / `vendedor` / `lead`.
7. **Não É Lead?** (papel = gerente OU vendedor):
   - **Sim** → vai para o roteador de comandos (`status` / `leads` / não reconhecido — ver [02-comandos-whatsapp.md](02-comandos-whatsapp.md)).
   - **Não** (é lead) → vai para o roteador de origem, **Verificar Origem**.

## Roteamento de origem (nó "Verificar Origem")

Determina de onde veio o lead e prepara os dados no formato esperado por `distribuir_lead`. Branches reais (nessa ordem de avaliação): iCarros (número fixo) → NaPista (por palavra-chave "napista" na mensagem OU número fixo alternativo) → OLX (palavra-chave) → Mobiauto (`origem` já setada pelo webhook dedicado) → Mercado Livre (palavra-chave) → Facebook (metadado `entryPointConversionApp` do payload da Evolution) → Webmotors (`origem` já setada pelo webhook dedicado) → Outros (fallback = WhatsApp direto). Detalhe completo em [tecnica/03-workflow-n8n.md](../tecnica/03-workflow-n8n.md).

## Distribuição

1. **Normalizar Saída Lead** — converge todos os branches de origem num formato único.
2. **Loop Over Items** → **Distribuir Lead** (RPC `distribuir_lead`, ver [regras-de-negocio/05](../regras-de-negocio/05-deduplicacao.md)).
3. **Vendedor Encontrado?** — checa `vendedor_id != "null"` (comparação de string, não de `null` real — ponto frágil, ver débito técnico).
4. **Duplicado de Plataforma?** — se `duplicado = true` **e** remetente é número oficial de iCarros/NaPista → não notifica de novo (NoOp). Caso contrário, segue para notificação.
5. **Buscar Mensagens Prontas** → **Montar Notificação** → **Encaminhar ao Vendedor** (envia a mensagem original + dados do lead pro WhatsApp do vendedor sorteado).

## Alerta de conexão (não documentado antes desta reescrita)

Quando o webhook da Evolution API recebe um evento que não é mensagem (ex.: a sessão do WhatsApp da loja caiu ou reconectou), o workflow monta e envia um alerta de WhatsApp para um número fixo (presumivelmente o operador do sistema), avisando `DESCONECTADO` ou `RECONECTADO`. Isso é uma funcionalidade real de monitoramento operacional, sem nenhuma menção em documentação anterior.

## Comandos fixos e Dashboard

Ver [02-comandos-whatsapp.md](02-comandos-whatsapp.md) para o roteador de comando, e a spec técnica do [Dashboard](../tecnica/05-dashboard-streamlit.md) para a interface de gestão dos gerentes.
