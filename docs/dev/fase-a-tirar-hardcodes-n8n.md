# Fase A — tirar os hardcodes de loja do n8n

> Change-set para a Fase A do [plano-multiloja](../plano-multiloja.md). Levantado em 2026-09-23 contra o workflow real `Renato Motors Amarrar Lead` (`Qj200sqS9544ao3d`, 67 nós), lendo os nós um a um — não inferido da documentação.
>
> **Ainda não aplicado.** Três pontos precisam de decisão do dono antes (seção "Decisões pendentes").

## O que o plano dizia, e o que é de fato

O plano listava **8 nós**. A varredura encontrou **14 nós** com valores fixos, mas nem todos são hardcode de loja:

| Categoria | Nós | Ação |
|---|---|---|
| **Hardcode de loja** | `Montar Alerta`, `Enviar Alerta Conexão`, `Alerta Lead Nao Distribuido`, `Alerta Loja Nao Encontrada`, `Alerta NaPista Sem Telefone`, `Extrai Dados NaPista` | sair |
| **Constante de plataforma** | `Duplicado de Plataforma?`, `Filtro Msg Vazia`, `Verificar Origem`, `Telefone do Cliente?` | **ficar** |
| **Infra compartilhada** | `Normaliza Dados Mobiauto`, `Normaliza Dados Webmotors` (URL da Evolution) | ficar, com ressalva |
| **Nome de rota** | `Webhook` (`renato-motors`), `Webhook Webmotors` (`webmotors/renato-motors`) | ficar |

**Constante de plataforma não é hardcode de loja.** Os números `551131361712` (NaPista) e `551130044558` (iCarros) identificam o remetente-robô da plataforma e são os mesmos para qualquer loja do Brasil. O que eles são de verdade é **duplicação**: os mesmos dois números aparecem em 5 nós. Se a NaPista trocar de número, são 5 edições. Isso é dívida separada, não Fase A.

## De onde vêm os dados certos

O nó `Encaminhar ao Vendedor` **já faz certo** e é o modelo a copiar. A razão de funcionar: a própria Evolution manda `instance`, `server_url` e `apikey` no corpo do webhook, e `Normaliza Dados` transforma isso em campos.

| Quero | Expressão | Disponível a partir de |
|---|---|---|
| URL do servidor Evolution | `$('Normaliza Dados').item.json.evolutionServerUrl` | `Normaliza Dados` |
| Instância da loja | `$('Normaliza Dados').item.json.instancia` | `Normaliza Dados` |
| Chave da Evolution | `$('Normaliza Dados').item.json.evolutionApiKey` | `Normaliza Dados` |
| ID da loja | `$('Preparar Dados Loja').item.json.lojaId` | `Preparar Dados Loja` |
| **WhatsApp da loja** | `$('Preparar Dados Loja').item.json.lojaNumero` | `Preparar Dados Loja` |

> **`lojaNumero` já existe e já flui.** `Identificar Loja` seleciona `numero_whatsapp` da tabela `lojas` e `Preparar Dados Loja` expõe como `lojaNumero`. O plano dizia que o destino do alerta *"exige buscar o gerente pelo `loja_id` (hoje nenhum nó faz isso)"* — **isso só vale se o destino tiver que ser o gerente**. Se o número da loja servir, o custo é zero nó novo.

## Nem todo alerta tem contexto de loja

Isto o plano não previu, e muda o desenho. Rastreando as conexões:

| Alerta | Cadeia | Tem loja? |
|---|---|---|
| `Alerta Lead Nao Distribuido` | ← `Vendedor Encontrado?` / `Duplicado de Plataforma?` ← … ← `Preparar Dados Loja` | **sim** |
| `Alerta NaPista Sem Telefone` | ← `Telefone do Cliente?` ← … ← `Preparar Dados Loja` | **sim** |
| `Alerta Loja Nao Encontrada` | ← `Loja Encontrada?` [saída falsa] | **não** — a loja é justamente o que não foi achado |
| `Montar Alerta` → `Enviar Alerta Conexão` | ← `É Mensagem?` ← `Webhook` (ramo que **desvia** de `Normaliza Dados`) | **não** — nem `Normaliza Dados` rodou |

Consequência: **`Alerta Loja Nao Encontrada` e o alerta de conexão são alertas de operador, não de loja.** Ter o número do dono ali não é bug — é a natureza deles. O que sai é a URL/instância/chave fixas, não o destino.

E `Montar Alerta` não pode usar `$('Normaliza Dados')`: precisa ler do próprio webhook (`$input.first().json.body`), que é o que ele já faz para o `state`.

---

# Change-set

## 1 · `Alerta Lead Nao Distribuido` · `Alerta NaPista Sem Telefone`

Os dois têm contexto de loja. Mesma mudança nos dois:

| Campo | Hoje | Vira |
|---|---|---|
| `url` | `https://evolution.yavoh.cloud/message/sendText/renato-motors` | `={{ $('Normaliza Dados').item.json.evolutionServerUrl }}/message/sendText/{{ $('Normaliza Dados').item.json.instancia }}` |
| header `apikey` | chave fixa da Evolution | `={{ $('Normaliza Dados').item.json.evolutionApiKey }}` |
| `number` no corpo | `'5519996977453'` | **decisão 1** — `$('Preparar Dados Loja').item.json.lojaNumero`, ou o gerente |

## 2 · `Alerta Loja Nao Encontrada`

| Campo | Hoje | Vira |
|---|---|---|
| `url` | fixa | `={{ $('Normaliza Dados').item.json.evolutionServerUrl }}/message/sendText/{{ $('Normaliza Dados').item.json.instancia }}` |
| header `apikey` | chave fixa | `={{ $('Normaliza Dados').item.json.evolutionApiKey }}` |
| `number` | `'5519996977453'` | **fica** — é alerta de operador |

Com loja 2, o alerta sai pela instância da loja 2 (a única disponível) e chega ao operador. Correto.

## 3 · `Montar Alerta` (code)

```js
// hoje
const texto = `${emoji} *Alerta Evolution API*\n\nInstância: renato-motors\n...`;
return [{ json: { number: '5519996977453', text: texto } }];

// vira
const instancia = $input.first().json.body?.instance || 'desconhecida';
const texto = `${emoji} *Alerta Evolution API*\n\nInstância: ${instancia}\n...`;
return [{ json: { number: '5519996977453', text: texto } }];  // destino de operador, fica
```

## 4 · `Enviar Alerta Conexão`

| Campo | Hoje | Vira |
|---|---|---|
| `url` | fixa | `={{ $('Webhook').item.json.body.server_url }}/message/sendText/{{ $('Webhook').item.json.body.instance }}` |
| header `apikey` | chave fixa | `={{ $('Webhook').item.json.body.apikey }}` |

Aqui é `$('Webhook')`, **não** `$('Normaliza Dados')` — este ramo desvia dela.

## 5 · `Extrai Dados NaPista` — não é mecânico

Este nó tem `instancia: 'renato-motors'`, `lojaId` fixo, `lojaNome: 'Renato Motors'`, URL e chave da Evolution fixas. **Mas o hardcode aqui não é preguiça: é falta de discriminador.**

Os outros ramos sabem de que loja se trata porque a Evolution manda `instance` no webhook. **Um e-mail não tem instância.** O `Gmail Trigger` lê **uma** caixa; nada no fluxo diz de que loja aquele lead é.

O discriminador existe e foi confirmado em 2026-09-23: o cabeçalho **`to`** do e-mail (`headers.to` / `headers.delivered-to`). Desenho proposto:

1. `lojas` ganha coluna `email_leads` (o endereço que a loja cadastra na plataforma).
2. Nó novo entre `Origem NaPista` e `Extrai Dados NaPista`: consulta `lojas?email_leads=eq.<to>&select=id,nome,instancia_evolution,evolution_api_key`.
3. `Extrai Dados NaPista` passa a ler `lojaId`, `lojaNome`, `instancia` e `evolutionApiKey` desse retorno.

**Custo:** uma migration + um nó novo. **Pré-requisito:** cada loja precisa de uma caixa própria, senão não há o que discriminar.

---

# Decisões pendentes

### 1. Destino dos alertas de loja

O [RUNBOOK do incidente](../historico/incidentes/2026-09-23-napista-leads-perdidos/RUNBOOK.md) registra: *"Decisão do dono: o alerta de lead do NaPista vai para o gerente. Estado atual: todos os alertas vão para o dono (`5519996977453`), por escolha dele, para observar o comportamento antes de repassar ao gerente."*

Mexer no destino agora **desfaz esse teste**. Três saídas:

| | Destino | Custo |
|---|---|---|
| **a** | `lojaNumero` (`lojas.numero_whatsapp`) | zero nó novo |
| **b** | gerente da loja | nó novo consultando `gerentes` por `loja_id` |
| **c** | manter o número do dono por ora, trocar só URL/instância/chave | zero — e preserva a observação em curso |

A **(c)** entrega o essencial da Fase A (loja 2 deixa de mandar alerta pela instância da loja 1) sem atropelar o teste. As decisões de destino ficam para quando a observação terminar.

### 2. `Extrai Dados NaPista` entra agora ou depois?

Exige migration e nó novo. Pode ficar para quando houver perspectiva de segunda loja com e-mail próprio.

### 3. Como aplicar

O MCP do n8n desta sessão só tem `search_workflows`, `get_workflow_details` e `execute_workflow` — **não escreve**. Para aplicar: chave da API pública do n8n (`PUT /api/v1/workflows/{id}`), ou edição manual na tela (são 4 nós e ~9 campos), ou eu preparo o JSON e você cola.

---

# Achados fora do escopo

Encontrados durante o levantamento. **Não são Fase A** — registrados para não se perderem.

### O alerta de desconexão é estruturalmente indeliverável

> **Resolvido em 2026-10-10:** o alerta passou a ir por **e-mail** (Gmail), fora da instância que caiu, com espera de 5 min e reconferência para não alertar oscilação. Ver RUNBOOK do incidente NaPista. O texto abaixo é o diagnóstico original.

`Enviar Alerta Conexão` envia **através da própria instância que caiu**. Quando `state === 'close'`, a Evolution não entrega — o alerta `❌ DESCONECTADO`, que é o único que importa, nunca chega. Só o `✅ RECONECTADO` chega, e só depois de resolvido.

Isso vale mais do que parece: foram **62 quedas em 14 dias** com uma loja, e a razão de ligar esse alerta era não perder lead em silêncio. Conserto exige um canal fora da instância que caiu (outra instância, e-mail, Telegram).

### Chave `service_role` do Supabase escrita no nó `Normaliza Dados` (achado em 2026-10-09)

O campo `supabaseKey` desse nó guarda um JWT com `role: service_role` do projeto, em texto, no próprio workflow. É a chave que contorna o RLS. Não aparecia no levantamento acima porque ele procurava valores fixos **de loja**, e esta é uma credencial.

Impacto para vender: o workflow é editável por quem tiver acesso ao n8n e pode ser exportado ou copiado em backup. Cada cópia carrega acesso total ao banco de todas as lojas. Relevante também para o caso de clonar o workflow por loja.

Correção prevista: guardar como credencial do n8n (por exemplo, Header Auth) e referenciá-la nos nós de HTTP que usam `supabaseKey`; depois **rotacionar a chave** no Supabase, porque a atual já esteve em texto. Rotacionar exige atualizar também o `.env` do Dashboard. Não aplicado.

### Os números de plataforma estão duplicados em 5 nós

`551131361712` e `551130044558` aparecem em `Duplicado de Plataforma?`, `Filtro Msg Vazia`, `Verificar Origem`, `Telefone do Cliente?` e `Extrai Dados NaPista`. Portal que troque de número quebra em 5 lugares — e, pelo histórico da NaPista, portal troca de número. Candidato natural a virar tabela.

### `webmotors/renato-motors` é diferente dos outros paths

O path do `Webhook` principal pode ficar, porque `Identificar Loja` resolve pela instância. Mas `Webhook Webmotors` tem o nome da loja **na rota**, e é a Webmotors quem chama. Loja 2 precisaria de rota própria cadastrada lá — ou de um path genérico com a loja no corpo. Não bloqueia hoje; bloqueia no onboarding da segunda loja com Webmotors.
