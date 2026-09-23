# Portaria — classificação de mensagens (prompt v2)

> **STATUS: proposta, não implementado.** Nada neste documento está em produção. É o desenho da Fase 4 do plano de remediação de 2026-09-23. Quando for implementado, este aviso sai e o documento passa a descrever o que existe.

Todos os exemplos abaixo são mensagens **reais** da Renato Motors, tiradas dos 511 leads de origem "WhatsApp Direto".

## Antes da IA: filtros determinísticos

A IA só vê o que sobra. Mandar mensagem para o modelo quando uma regra resolve é mais caro, mais lento e menos confiável.

| Filtro | Decisão | Por quê |
|---|---|---|
| eco (`fromMe`), evento de conexão, mensagem vazia | descarta | já é assim hoje |
| remetente é gerente ou vendedor cadastrado | roteador de comandos | já é assim hoje |
| webhook dedicado (Mobiauto, Webmotors) | lead, origem conhecida | payload estruturado |
| remetente é número de plataforma conhecido | lead, parser da origem | template conhecido |
| **remetente já é `numero_cliente` com vendedor ativo** | **lead, vai pro mesmo vendedor** | a amarração do Passo 2 já resolve — não perguntar ao modelo |
| **mídia sem texto** (áudio, vídeo, foto, álbum) | **lead** | não há texto para classificar. Quem manda áudio para uma revenda é cliente |
| **só saudação** (≤12 caracteres, ou casa `^(oi+|ol[aá]|bo[am] (dia\|tarde\|noite)\|tudo bem)[\s!?.]*$`) | **lead** | **119 de 492 mensagens (24%)** são isso. Não há conteúdo para classificar, e quem cumprimenta uma revenda é cliente |
| `placeholderMessage` | erro + alerta | falha de entrega, não é mensagem |

Só o que passa por todos vai ao modelo. Pela amostra, é ~60% do balde "Outros".

## Categorias

Quatro, e a terceira nasceu dos dados — não estava no desenho original:

| Categoria | O que é | Para onde vai |
|---|---|---|
| `lead_novo` | alguém querendo comprar, trocar, financiar ou vender um veículo | distribui pela fila |
| `pos_venda` | quem **já comprou** falando de revisão, garantia, documentação | vai pro mesmo vendedor (Passo 2 já faz), **sem contar como lead novo** |
| `nao_lead` | cobrança, boleto, fatura, marketing, oferta B2B, engano de número | arquiva, com desfazer em 1 clique |
| `incerto` | qualquer dúvida | **distribui e marca** |

O campo `intencao` (`comprar` / `vender_ou_trocar` / `servico` / `outro`) é metadado, não decide roteamento. Serve para medir quanto tráfego de consignação existe antes de decidir se vale um fluxo próprio.

## System prompt

```
Você classifica mensagens que chegam no WhatsApp de uma revenda de veículos
usados no interior de São Paulo. Decida em qual categoria a mensagem se
encaixa e extraia o que der.

CATEGORIAS

lead_novo — pessoa interessada em comprar, trocar, financiar ou vender um
  veículo para a loja. Inclui quem pergunta sobre um anúncio, pede simulação,
  oferece o próprio carro em troca ou consignação, ou pergunta se aprova
  financiamento no nome dela.

pos_venda — pessoa que JÁ COMPROU desta loja e escreve sobre revisão,
  garantia, documentação, emplacamento ou pós-venda. O sinal é passado:
  "comprei", "peguei o carro", "da minha compra".

nao_lead — não é cliente em potencial. Cobrança, boleto, fatura, aviso de
  banco ou operadora, marketing, oferta comercial B2B, corretor de outro
  ramo, engano de número.

incerto — use sempre que não tiver convicção. Não force uma categoria.

REGRA DE CUSTO ASSIMÉTRICO

Errar chamando de nao_lead uma mensagem que era cliente faz a loja perder
uma venda e o cliente nunca ser respondido. Errar mandando ruído para um
vendedor custa trinta segundos de atenção dele. Na dúvida, escolha incerto.
Só use nao_lead quando a mensagem for inequivocamente comercial ou
automática.

EVIDÊNCIA

Em trecho_evidencia, copie um pedaço LITERAL da mensagem que justifica sua
decisão — caracteres exatos, sem parafrasear. Se não conseguir citar um
trecho literal, use incerto.

TELEFONE

Só preencha telefone_cliente se um número aparecer escrito na mensagem.
Nunca deduza, nunca complete, nunca invente. Sem número escrito, use null.
```

## Exemplos (few-shot, todos reais)

```
"Olá! Tenho interesse e queria mais informações, por favor."
→ lead_novo, comprar, 0.93
   evidência: "Tenho interesse e queria mais informações"

"Trnho interesse no fusion, fariam permuta?"
→ lead_novo, vender_ou_trocar, 0.95
   evidência: "interesse no fusion, fariam permuta"
   anuncio: "Fusion"

"Gostaria de fazer a troca da minha Ecosport por um pinto"
→ lead_novo, vender_ou_trocar, 0.94
   evidência: "fazer a troca da minha Ecosport"

"Tenho um kia soul 2015"
→ lead_novo, vender_ou_trocar, 0.71
   evidência: "Tenho um kia soul 2015"
   (oferecendo o próprio carro — consignação ou troca)

"Boa tarde, td bem? Prazer Jenyffer, gostaria de saber se no meu nome
 aprova um financiamento"
→ lead_novo, comprar, 0.91
   evidência: "no meu nome aprova um financiamento"
   nome_cliente: "Jenyffer"

"Bom dia, aqui é o Josiel que comprou o Palio na sexta-feira, preciso
 fazer aquela revisãozinha para ativar a garantia dele"
→ pos_venda, servico, 0.96
   evidência: "que comprou o Palio na sexta-feira"
   nome_cliente: "Josiel"

"Olá! Informamos que sua fatura já está disponível, com vencimento em
 11/05. O boleto foi enviado para o seu e-mail"
→ nao_lead (cobranca), outro, 0.97
   evidência: "sua fatura já está disponível, com vencimento"

"Prezado(a) Renato, Consta uma pendência financeira relacionada ao
 financiamento do seu veículo."
→ nao_lead (cobranca), outro, 0.96
   evidência: "Consta uma pendência financeira"

"Oiee, eu sou a Josi e estou em um pré-lançamento de apartamentos no
 Bairro Parque Gabriel em Hortolândia-SP"
→ nao_lead (marketing), outro, 0.95
   evidência: "pré-lançamento de apartamentos"

"Bom dia eu vi um carro de voces"
→ lead_novo, comprar, 0.88
   evidência: "vi um carro de voces"
```

## Schema da resposta

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["classificacao","intencao","confianca","motivo",
               "categoria_nao_lead","nome_cliente","telefone_cliente",
               "anuncio","trecho_evidencia"],
  "properties": {
    "classificacao":      {"enum": ["lead_novo","pos_venda","nao_lead","incerto"]},
    "intencao":           {"enum": ["comprar","vender_ou_trocar","servico","outro"]},
    "confianca":          {"type": "number", "minimum": 0, "maximum": 1},
    "motivo":             {"type": "string", "maxLength": 140},
    "categoria_nao_lead": {"type": ["string","null"],
                           "enum": ["cobranca","spam","marketing","pessoal",
                                    "engano","outro",null]},
    "nome_cliente":       {"type": ["string","null"]},
    "telefone_cliente":   {"type": ["string","null"]},
    "anuncio":            {"type": ["string","null"]},
    "trecho_evidencia":   {"type": ["string","null"]}
  }
}
```

## Chamada

```
POST https://api.anthropic.com/v1/messages
x-api-key: <credencial do n8n>
anthropic-version: 2023-06-01

model: claude-opus-5
max_tokens: 512
output_config: { effort: "low", format: { type: "json_schema", schema: <acima> } }
```

`effort: low` porque classificar é tarefa simples — mais rápido e mais barato sem perda de qualidade nesse tipo de rótulo.

## Travas depois do modelo (Code node, não prompt)

Prompt é pedido; código é garantia.

```js
const d = s => String(s ?? '').replace(/\D/g, '');
const bruto = JSON.stringify($('Webhook').item.json) + ' ' + texto;

const telOk = d(ia.telefone_cliente).length >= 10
           && d(bruto).includes(d(ia.telefone_cliente));

const citou = ia.trecho_evidencia && texto.includes(ia.trecho_evidencia);

return [{ json: {
  ...ia,
  telefone_verificado: telOk,
  classificacao: citou ? ia.classificacao : 'incerto'
}}];
```

## Decisão final

| Modelo diz | Ação |
|---|---|
| `lead_novo`, confiança ≥ 0.80 | distribui pela fila |
| `pos_venda`, confiança ≥ 0.80 | distribui (amarração leva ao mesmo vendedor), **não conta como lead novo** |
| `nao_lead`, confiança ≥ 0.90 | arquiva com desfazer |
| tudo mais — `incerto`, confiança baixa, trava falhou, timeout, API fora | **distribui e marca dúvida** |

## Como medir antes de ligar

Sem medição, mudar o prompt é chute. O caminho:

1. Amostrar ~100 das 492 mensagens reais com texto
2. Rotular à mão (o dono decide os casos de fronteira — é regra de negócio, não técnica)
3. Rodar o prompt contra a amostra e medir
4. **Portão:** zero mensagens rotuladas como cliente que o modelo chamou de `nao_lead`. Falso `lead_novo` é tolerado — já é o comportamento de hoje

Repetir a cada mudança de redação. O que não passa no portão não sobe.

## Histórico

- **v2** (2026-09-23) — versão inicial escrita. Categoria `pos_venda` adicionada a partir do caso real do cliente Josiel (leads de 15/09 e 21/09, mesmo telefone, mesmo vendedor). Filtro de saudação adicionado depois de medir que 24% das mensagens são só cumprimento. Campo `intencao` adicionado para medir volume de consignação antes de decidir sobre um fluxo próprio.
- v1 — esboço no plano de remediação, com três categorias e sem filtros determinísticos documentados.
