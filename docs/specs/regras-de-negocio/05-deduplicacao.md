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

## Casos extremos conhecidos (herdados do documento antigo, ainda não resolvidos)

- Cliente troca de número de telefone → tratado como cliente novo (chave é o número). Merge manual pelo Dashboard é ideia de roadmap, não implementada.
- Mudança no formato do texto do anúncio pela plataforma de origem (ex.: "Gol 2020 1.0" → "Volkswagen Gol 1.0 2020") quebra a comparação exata de `anuncio` no Passo 1, gerando um lead duplicado em vez de silenciado. Não há normalização/fuzzy-match implementada.
