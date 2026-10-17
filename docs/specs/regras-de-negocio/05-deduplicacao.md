# Deduplicação de Leads

> Este documento substitui a versão antiga, que se contradizia internamente ("2 níveis" no resumo, mas "3 passos" no corpo do texto, e um "Passo/Nível 3" que na real é só round-robin, não dedup). Conteúdo abaixo extraído diretamente do código-fonte real de `distribuir_lead()` (Supabase, definição atual em produção, 2026-09-11).

## Os 3 passos reais (dentro de `distribuir_lead`, nessa ordem, por transação)

**Passo 0 — Lock anti-race** (não é dedup, é controle de concorrência): trava por `(loja_id, numero_cliente)` antes de qualquer leitura, para que duas mensagens quase simultâneas do mesmo cliente não passem pelos passos 1/2 ao mesmo tempo. Ver [ADR 0002](../../adr/0002-lock-advisory-race-condition.md).

**Passo 1 — Duplicata exata** — chave `(numero_cliente, loja_id, anuncio)`:
Se já existe um lead desse cliente, nessa loja, para o **mesmo anúncio**, e o vendedor daquele lead ainda está `ativo` → retorna `duplicado = true`, **não cria um novo lead**, devolve os dados do vendedor já responsável. Isso cobre o caso de a mesma plataforma reenviar/republicar o mesmo anúncio.

**Passo 2 — Amarração de cliente ("cliente retornando")** — chave `(numero_cliente, loja_id)`, **sem considerar o anúncio**:
Se o cliente já tem qualquer lead anterior (para qualquer anúncio) atribuído a um vendedor ainda `ativo`, o lead novo vai para **esse mesmo vendedor**, pulando o round-robin. Cobre o caso de um cliente perguntar sobre um segundo carro depois de já ter conversado com um vendedor.

**Passo 3 — Round-robin**: só executa se não caiu em duplicata exata nem em amarração (cliente novo, ou todos os vendedores anteriores dele estão inativos/removidos). Ver [01-round-robin.md](01-round-robin.md).

## O que muda em relação à versão antiga do documento

- Não existe mais um campo `cliente_retornando` no retorno da função (existiu, foi removido pela migration `remove_cliente_retornando_from_distribuir_lead`, 2026-02-28) — a lógica de amarração continua ativa, só não é mais sinalizada separadamente no retorno.
- A numeração "2 níveis" vs "3 passos" é resolvida: são **3 passos de decisão** (Passo 1 e 2 são dedup propriamente dita; Passo 3 é o fallback padrão, não uma forma de dedup). Ao citar isso em outros documentos, usar "Passo 1/2/3", não "nível".

## O que silencia a mensagem (NoOp) vs. o que é encaminhado

`duplicado = true` sozinho **não** significa silêncio automático. O workflow n8n só descarta a mensagem (não notifica o vendedor de novo) quando `duplicado = true` **e** o remetente é um número oficial de plataforma conhecida (iCarros ou NaPista, por regex de número fixo — ver [tecnica/03](../tecnica/03-workflow-n8n.md)). Um cliente que manda a mesma pergunta duas vezes por WhatsApp direto (`duplicado = true` mas remetente não é plataforma) **é encaminhado normalmente** de novo ao vendedor. Isso nunca esteve claro nos documentos antigos.

**Formato do aviso (desde 2026-10-17, `3df66b7f`):** quando é encaminhado com `duplicado = true`, o vendedor recebe um **aviso curto** (nome, telefone, texto, link para responder), não o "🚗 Novo Lead" completo com mensagens prontas. Áudio, foto, vídeo e documento são repassados como arquivo. Cliente que cai no Passo 2 (outro anúncio) volta como `duplicado = false` e recebe o aviso completo.

## Medido em 2026-10-10: cliente que escreve de novo vira lead novo

Queixa do dono: o cliente manda mensagem, é encaminhado ao vendedor, escreve de novo no número da loja e **conta como lead novo**. Confirmado no código e nos dados.

**Causa:** o Passo 2 (amarração) **cria uma linha nova em `leads`** com o mesmo vendedor e devolve `duplicado = false` — para o n8n é um lead novo, e o vendedor recebe de novo como "novo lead". O Passo 1 só segura se o `anuncio` for **idêntico**, e não é no caso mais comum: a primeira mensagem vem com o texto do OLX (`anuncio` preenchido) e a segunda, segundos depois, cai como `WhatsApp Direto` com `anuncio` vazio.

**Volume (histórico completo, 1.299 leads, sem contar números de plataforma):** 119 leads repetidos do mesmo cliente (~9%).

| Intervalo entre os dois | mesmo vendedor | outro vendedor |
|---|---|---|
| < 10 min | 80 | 16 |
| 10 min – 24 h | 8 | 0 |
| 1 – 7 dias | 6 | 0 |
| 7 – 30 dias | 3 | 2 |
| 30 – 90 dias | 0 | 3 |
| > 90 dias | 1 | 0 |

Os 16 casos "outro vendedor em menos de 10 min" são provavelmente anteriores ao lock de 31/08 ([ADR 0002](../../adr/0002-lock-advisory-race-condition.md)) — **não verificado**. Os de 7+ dias com outro vendedor batem com vendedor que saiu (amarração só vale com vendedor `ativo`).

**Decisão do dono (2026-10-10): não corrigir — fica como está.** Registrado para não ser reaberto nem "corrigido" por conta própria; a medição acima fica como referência se o assunto voltar.

## Casos extremos conhecidos (herdados do documento antigo, ainda não resolvidos)

- Cliente troca de número de telefone → tratado como cliente novo (chave é o número). Merge manual pelo Dashboard é ideia de roadmap, não implementada.
- Mudança no formato do texto do anúncio pela plataforma de origem (ex.: "Gol 2020 1.0" → "Volkswagen Gol 1.0 2020") quebra a comparação exata de `anuncio` no Passo 1, gerando um lead duplicado em vez de silenciado. Não há normalização/fuzzy-match implementada.
