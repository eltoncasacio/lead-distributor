# Passo a passo — colocar uma segunda loja no ar (começando por uma loja fake)

> Escrito em 2026-10-10, depois das Fases A e B. Levantado contra o sistema real: webhook e configurações da instância `renato-motors` lidos da Evolution, tabelas lidas do Supabase, fluxo lido do n8n (`versionId 2931765f`). **A loja fake é ensaio da loja real**: mesmos passos, e no fim ela é desativada.

## O que já está pronto (não precisa mexer)

- **n8n:** um workflow só atende todas as lojas. A loja é descoberta pela **instância da Evolution** (`Identificar Loja`), e envio ao vendedor, alertas, comandos e IA leem instância e chave da própria mensagem (Fase A).
- **Isolamento:** provado em produção na Fase B (26 verificações).
- **Alertas:** queda da conexão da loja nova chega por e-mail para o dono, sem configurar nada.

## Pré-requisitos (do dono)

| Item | Para quê | Observação |
|---|---|---|
| **Um segundo número de WhatsApp**, num celular | é o "WhatsApp da loja fake", onde os clientes escrevem | qualquer chip; WhatsApp comum ou Business |
| **Chave GLOBAL da Evolution** (`AUTHENTICATION_API_KEY` do servidor `evolution.yavoh.cloud`) | criar a instância nova | **recuperada em 10/10**: está em `EVOLUTION_GLOBAL_KEY` no `.env`. Origem: Portainer (https://portainer.yavoh.cloud) → container da Evolution → Env → `AUTHENTICATION_API_KEY`. Também dá acesso ao painel https://evolution.yavoh.cloud/manager. A chave de instância da Renato Motors não serve para criar instância |
| **Número do gerente** | administrar a loja pelo WhatsApp | o seu (`…7453`) serve: o mesmo número pode ser gerente em duas lojas (provado na Fase B) |
| **Um celular de "vendedor"** | receber o lead | um número que você controle e que **não** seja o da loja fake |
| **Um celular de "cliente"** | mandar a mensagem de teste | qualquer número que não esteja cadastrado na loja fake |

## Passo 0 — mensagem padrão do sistema ✅ feito em 2026-10-10

Loja sem mensagem pronta cadastrada parava o fluxo antes de avisar o vendedor (lead criado e distribuído em silêncio). Corrigido no n8n (`2931765f` → `03b218b7`): sem mensagem cadastrada, o aviso ao vendedor usa a **mensagem padrão do sistema** — "Olá, meu nome é {vendedor} e sou consultor de vendas da {nome da loja}…". Nada a fazer por loja.

## Passo 1 — criar a instância na Evolution (dono, com a chave global)

```bash
curl -X POST https://evolution.yavoh.cloud/instance/create \
  -H "apikey: <CHAVE_GLOBAL>" -H "Content-Type: application/json" \
  -d '{"instanceName": "loja-teste", "integration": "WHATSAPP-BAILEYS", "qrcode": false}'
```

A resposta traz a **chave da instância** (na Evolution v2, campo `hash` — confira na resposta). Guarde: vai para `lojas.evolution_api_key`. O nome (`loja-teste`) vai para `lojas.instancia_evolution`; não pode repetir.

## Passo 2 — apontar o webhook para o n8n (mesma configuração da Renato Motors)

```bash
curl -X POST https://evolution.yavoh.cloud/webhook/set/loja-teste \
  -H "apikey: <CHAVE_DA_INSTANCIA>" -H "Content-Type: application/json" \
  -d '{"webhook": {"enabled": true,
                   "url": "https://webhook.yavoh.cloud/webhook/renato-motors",
                   "events": ["MESSAGES_UPSERT", "CONNECTION_UPDATE"],
                   "byEvents": false, "base64": true}}'
```

A URL termina em `renato-motors` **de propósito**: é só o nome do caminho no n8n, igual para todas as lojas. Quem decide a loja é o campo `instance` que a Evolution manda. Conferir com `GET /webhook/find/loja-teste` — deve bater com a Renato Motors (eventos `MESSAGES_UPSERT` e `CONNECTION_UPDATE`, `webhookBase64: true`).

## Passo 3 — cadastrar a loja no banco (Claude faz, com o ok do dono)

Antes de conectar o número, para a primeira mensagem já achar a loja. Duas inserções obrigatórias e uma opcional:

> **Vendedor por SQL (corrigido em 2026-10-17, onboarding da Fitcar):** `vendedores.ordem_fila` é `NOT NULL` — informe 1, 2, 3… (não afeta o rodízio, que segue `criado_em`). E insira um vendedor por vez, em transações separadas, senão o `criado_em` empata e o rodízio trava.

```sql
-- loja
INSERT INTO lojas (nome, numero_whatsapp, instancia_evolution, evolution_api_key, ativa)
VALUES ('Loja Teste', '55DDNNNNNNNNN', 'loja-teste', '<CHAVE_DA_INSTANCIA>', true)
RETURNING id;

-- gerente (pode ser o mesmo número de gerente da Renato Motors)
INSERT INTO gerentes (loja_id, nome, numero_whatsapp, ativo)
VALUES ('<id>', 'Elton', '5519996977453', true);

-- OPCIONAL: mensagem pronta própria da loja. Sem ela vale a padrão do sistema (Passo 0).
INSERT INTO mensagens_prontas (loja_id, vendedor_id, titulo, texto, ordem, ativo)
VALUES ('<id>', NULL, 'Mensagem Padrão',
        'Olá, meu nome é {vendedor_nome} e sou consultor de vendas da Loja Teste, tudo bem? Vi seu interesse em {anuncio}.',
        1, true);
```

Regras do banco que valem aqui: loja ativa precisa de `instancia_evolution`; a instância não pode repetir; telefone de vendedor/gerente é único **dentro da loja** (pode repetir entre lojas). Placeholders da mensagem pronta: `{nome_cliente}`, `{vendedor_nome}`, `{anuncio}`, `{origem}` e, desde 10/10, `{loja_nome}`.

## Passo 4 — conectar o número da loja (dono, no celular da loja)

```bash
curl "https://evolution.yavoh.cloud/instance/connect/loja-teste?number=55DDNNNNNNNNN" \
  -H "apikey: <CHAVE_DA_INSTANCIA>"
```

Devolve um **código de pareamento** de 8 caracteres (vale ~1 minuto). No celular da loja: WhatsApp → **Dispositivos conectados** → **Conectar dispositivo** → **Conectar com número de telefone** → digitar o código. Conferir: `GET /instance/connectionState/loja-teste` → `"state": "open"`.

## Passo 5 — cadastrar vendedor pelo próprio WhatsApp (gerente)

Do celular do gerente, **para o número da loja fake**:

1. `menu` → deve vir a lista de comandos.
2. `inserir vendedor Teste 19 9XXXX-XXXX` (o celular do "vendedor") → o sistema mostra o que vai fazer → responder `sim`.
3. `listar vendedores` → só o vendedor da loja fake (nenhum da Renato Motors).

Isso já prova o caminho de comandos na loja nova. Com IA também funciona: "cadastra o Teste, 19 9XXXX-XXXX".

## Passo 6 — o teste que importa: um lead de verdade

Do celular do "cliente", para o número da loja fake: `Olá, tenho interesse no carro`.

**Esperado:**
- o celular do vendedor recebe **"🚗 Novo Lead — WhatsApp Direto"**, com o telefone do cliente e o link "Mensagem Padrão" (com o nome da loja fake — a cadastrada no Passo 3 ou a padrão do sistema);
- a Renato Motors **não** recebe nada e a fila dela não anda (`python3 auditoria_producao.py`);
- o vendedor manda `meus leads` para o número da loja fake e vê esse lead.

Claude confere a execução no n8n e a tabela `leads` (loja certa, vendedor certo).

## Passo 7 — testes opcionais

| Teste | Como | Esperado |
|---|---|---|
| Alerta de queda | no celular da loja fake, desconectar o dispositivo "Evolution" | em ~5 min, e-mail "WhatsApp da loja DESCONECTADO — loja-teste". Reconectar pelo Passo 4 |
| Vendedor pausado | gerente: `pausar Teste` → `sim`; cliente manda outra mensagem | lead fica sem vendedor (só um vendedor e pausado) → alerta "Lead não distribuído" no WhatsApp do dono, saindo **pela instância da loja fake** |
| Isolamento de comando | gerente manda `listar vendedores` para o número da **Renato Motors** | só vendedores da Renato Motors |

## Passo 8 — encerrar a loja fake

Desativar, sem apagar nada: `UPDATE lojas SET ativa = false WHERE instancia_evolution = 'loja-teste';` — mensagens que chegarem nela passam a gerar o e-mail "instância não cadastrada". Para remover de vez: desconectar e apagar a instância na Evolution (`DELETE /instance/logout/loja-teste` e `DELETE /instance/delete/loja-teste`, chave global) e apagar as linhas da loja (Claude faz, com o ok do dono).

## O que este roteiro não cobre (fica para a loja real)

- **E-mail da NaPista:** o ramo de e-mail (`Extrai Dados NaPista`) ainda tem a Renato Motors fixa. Loja real que receba NaPista por e-mail precisa de `lojas.email_leads` e de um nó de consulta pelo destinatário — ver `docs/dev/fase-a-tirar-hardcodes-n8n.md`, item 5.
- **Mobiauto / Webmotors:** chegam por webhooks próprios cuja URL leva a instância da loja no caminho (`…/{loja}`), cadastrados no portal. Loja nova precisa da URL dela cadastrada lá.
- **Destino dos alertas de lead:** hoje vão para o dono (decisão de 10/10). Com loja real de terceiros, decidir se passam a ir para o gerente da loja.
- **Acesso a painel:** não há (Streamlit fora do plano); a loja administra tudo pelo WhatsApp.
