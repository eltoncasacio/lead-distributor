# Revisão e Validação Pré-Implementação (HISTÓRICO)

**⚠️ ATENÇÃO:** Este documento reflete a **revisão ANTES da implementação** (histórico). Para o estado **ATUAL** do sistema implementado, consulte:
- `AUDITORIA_TECNICA_2026-02-19.md` (estado real validado)
- `Técnica/09 - Estado Real vs Documentado.md` (gaps spec vs realidade)

---

Resultado da revisão completa de toda a documentação (~25 arquivos) antes da implementação do workflow n8n e persistência no Supabase. Inclui inconsistências encontradas, lacunas documentadas, testes de mesa e decisões tomadas.

---

## Objetivo (na época)

Garantir que:
- A documentação reflete **fielmente** as regras de negócio
- O sistema **soluciona** a dor do cliente de forma confiável
- Todos os **edge cases** estão cobertos
- O modelo de dados e a lógica estão prontos para implementação **sem ambiguidades**

---

## Estado Atual (Pré-Implementação - HISTÓRICO)

**Data desta revisão:** Antes de 2026-02-08

| Componente | Estado (na época) |
|------------|--------|
| **Supabase** | Nenhuma migration aplicada; nenhuma tabela do projeto existe |
| **n8n** | Workflow "Distribuição de Leads" (`XYaAkGd7lz-TsGAo6DzOM`) existe vazio (0 nós), inativo |
| **Documentação** | ~25 documentos completos com inconsistências e lacunas identificadas abaixo |

**Estado PÓS-Implementação (2026-02-19):**
- ✅ Supabase: 9 migrations aplicadas, 4 tabelas, 4 funções RPC
- ✅ n8n: 43 nós ativos, workflow funcional
- ⚠️ Gaps identificados: retry, error handling, código duplicado

---

## PARTE 1: Inconsistências Encontradas

Contradições entre documentos que **devem** ser corrigidas antes da implementação.

### 1.1 Unicidade do `numero_whatsapp` do Gerente

**Severidade:** CRÍTICA

**Contradição entre documentos:**

| Documento | O que diz |
|-----------|-----------|
| [[06 - Modelo de Dados Detalhado]] (linha 104) | "Um gerente está vinculado a apenas uma loja no sistema" |
| [[06 - Modelo de Dados Detalhado]] (DDL, linha 387) | `UNIQUE(loja_id, numero_whatsapp)` — unicidade apenas POR LOJA |
| [[04 - Isolamento Multi-Loja]] (linha 23) | "Um número pode ser gerente de mais de uma loja somente se houver suporte explícito" |
| [[02 - Modelo Mental de Dados]] (linha 11) | "para uma (ou mais) loja(s)" |

**Problema concreto:** Se o mesmo número for cadastrado como gerente na Loja A e Loja B, ao enviar "status", a query `SELECT loja_id FROM gerentes WHERE numero_whatsapp = :numero AND ativo = true` retorna **2 linhas**. O sistema não sabe qual loja mostrar.

**Correção aplicada:**
- Schema: `UNIQUE(numero_whatsapp)` globalmente (substitui `UNIQUE(loja_id, numero_whatsapp)`)
- Todos os documentos atualizados para refletir: **"No sistema, um número pode ser gerente de apenas uma loja"**

---

### 1.2 Unicidade do `numero_whatsapp` do Vendedor

**Severidade:** CRÍTICA

**Contradição entre documentos:**

| Documento | O que diz |
|-----------|-----------|
| [[04 - Isolamento Multi-Loja]] (linha 11) | "um mesmo número não pode ser vendedor de duas lojas ao mesmo tempo no sistema" |
| [[06 - Modelo de Dados Detalhado]] (DDL, linha 376) | `UNIQUE(loja_id, numero_whatsapp)` — unicidade apenas POR LOJA |

**Problema concreto:** O schema permite cadastrar o mesmo número WhatsApp como vendedor em 2 lojas diferentes, violando diretamente a regra de negócio documentada.

**Correção aplicada:**
- Schema: `UNIQUE(numero_whatsapp)` globalmente (substitui `UNIQUE(loja_id, numero_whatsapp)`)
- Documentação atualizada para refletir unicidade global

---

### 1.3 Unicidade da `instancia_evolution`

**Severidade:** IMPORTANTE

**Problema:** Nenhuma constraint UNIQUE existe em `lojas.instancia_evolution`. Se duas lojas receberem acidentalmente a mesma instância, o sistema identificaria a loja errada e distribuiria leads incorretamente.

**Correção aplicada:**
- Schema: `CREATE UNIQUE INDEX idx_lojas_instancia_unique ON lojas(instancia_evolution) WHERE instancia_evolution IS NOT NULL;`
- Índice parcial permite múltiplos NULLs (lojas sem instância configurada)

---

## PARTE 2: Lacunas na Documentação

Comportamentos não documentados que precisam de definição explícita para implementação.

### 2.1 Lógica de Roteamento de Mensagens

**Severidade:** CRÍTICA (primeiro nó do workflow n8n)

**Situação:** Nenhum documento consolidava a árvore de decisão completa que o sistema toma ao receber qualquer mensagem. A lógica estava distribuída entre [[01 - Fluxo Principal]], [[02 - Comandos via WhatsApp]] e [[04 - Tratamento de Erros]], mas nunca unificada.

**Árvore de decisão definida:**

```
Mensagem chega no WhatsApp da loja (webhook Evolution API)
│
├── data.key.fromMe = true?
│   └── SIM → IGNORAR (eco de mensagem própria)
│
├── Extrair: numero_remetente de data.key.remoteJid
├── Identificar: loja a partir de instance (lojas.instancia_evolution)
│
├── Loja não encontrada?
│   └── SIM → LOGAR e PARAR (indeterminação da loja)
│
├── Consultar: É gerente ativo desta loja?
│   │
│   ├── SIM → Texto é exatamente "status" ou "relatorio"?
│   │   │
│   │   ├── SIM → EXECUTAR COMANDO (escopado pela loja do gerente)
│   │   │
│   │   └── NÃO → RESPONDER "Comando não reconhecido.
│   │              Comandos disponíveis: status, relatorio"
│   │              (NÃO distribui como lead)
│   │
│   └── NÃO → É vendedor ativo/inativo desta loja?
│       │
│       ├── SIM → IGNORAR (vendedor mandando msg para número da loja)
│       │
│       └── NÃO → TRATAR COMO LEAD
│                  → Extrair dados → Round-Robin → Encaminhar ao vendedor
```

**Justificativas das decisões:**
- **Papéis exclusivos:** Um número não pode ser gerente e vendedor ao mesmo tempo, portanto os caminhos da árvore são mutuamente exclusivos.
- **Vendedor é ignorado:** Se um vendedor enviar mensagem para o número da loja, não é um lead de cliente. Ignorar silenciosamente.
- **Mensagem não-comando do gerente:** Responder com mensagem padrão informando os comandos disponíveis. Isso dá feedback claro ao gerente sem poluir a fila de leads.

---

### 2.2 Comportamento para Mensagem Não-Comando do Gerente

**Severidade:** MENOR

**Situação:** [[02 - Comandos via WhatsApp]] define os comandos `status` e `relatorio` mas não definia o que acontece quando um gerente envia qualquer outro texto (ex: "oi", "bom dia").

**Decisão:** O sistema responde com mensagem padrão:
> "Comando não reconhecido. Comandos disponíveis: status, relatorio"

A mensagem **NÃO** é distribuída como lead.

---

### 2.3 Mesmo Número como Gerente e Vendedor

**Severidade:** EDGE CASE

**Situação:** Nenhum documento abordava o cenário onde o mesmo número WhatsApp é cadastrado como gerente E vendedor na mesma loja.

**Decisão:** PROIBIR overlap. Um número **não pode** ser gerente e vendedor ao mesmo tempo. Validar no cadastro. Isso simplifica a lógica de roteamento — os caminhos gerente/vendedor/lead são mutuamente exclusivos.

---

### 2.4 Concorrência — Locking Explícito

**Severidade:** CRÍTICA (afeta confiabilidade do Round-Robin)

**Situação:** [[06 - Modelo de Dados Detalhado]] menciona "transação no banco de dados" e "lock pessimista ou otimista" no tratamento de leads simultâneos, mas os exemplos SQL **NÃO** incluem `SELECT FOR UPDATE` ou qualquer mecanismo de locking.

**Problema demonstrado (Teste de Mesa #7):**

```
Thread 1: lê ponteiro = Vendedor A
Thread 2: lê ponteiro = Vendedor A  ← (antes da Thread 1 atualizar!)
Thread 1: distribui lead para A, avança ponteiro para B
Thread 2: distribui lead para A, avança ponteiro para B

Resultado: A recebe 2 leads, B recebe 0. Round-Robin QUEBRADO.
```

**Correção:** Criar função PostgreSQL `distribuir_lead()` que encapsula toda a lógica em uma única transação atômica com `SELECT ... FOR UPDATE`:

```sql
-- Pseudocódigo da função
CREATE FUNCTION distribuir_lead(p_loja_id UUID, ...) RETURNS ...
AS $$
BEGIN
  -- 1. Lock na linha da loja (impede leitura concorrente)
  SELECT proximo_vendedor_id INTO v_ponteiro
  FROM lojas WHERE id = p_loja_id
  FOR UPDATE;

  -- 2. Buscar próximo vendedor ativo (Round-Robin com wrap)
  -- 3. Inserir lead
  -- 4. Avançar ponteiro para o próximo-próximo
  -- 5. Atualizar ultima_distribuicao_em
  -- 6. Retornar vendedor atribuído
END;
$$;
```

O n8n chama esta função via RPC do Supabase — **uma única chamada atômica** que elimina completamente o problema de concorrência.

---

### 2.5 Mensagens de Mídia (Imagem, Áudio, Vídeo)

**Severidade:** IMPORTANTE

**Situação:** Nenhum documento definia como tratar mensagens não-texto recebidas de clientes.

**Decisão:** Encaminhar normalmente via Round-Robin, como qualquer lead. O vendedor recebe a mídia no seu WhatsApp. O campo `mensagem_original` pode ficar vazio ou conter descrição do tipo de mídia (ex: "[imagem]", "[áudio]").

---

### 2.6 Extração de Dados do Lead

**Severidade:** IMPORTANTE

**Situação:** Documentação dizia que `nome_cliente` e `anuncio` devem ser extraídos "quando disponível", mas não definia o método de extração.

**Decisão Versão atual:** Usar **LLM (modelo de linguagem)** para extração de dados estruturados:

| Dado | Fonte | Método |
|------|-------|--------|
| `numero_cliente` | `data.key.remoteJid` (metadata WhatsApp) | Direto — sempre disponível |
| `nome_cliente` | `pushName` + conteúdo da mensagem | `pushName` como fallback; LLM extrai do texto |
| `anuncio` | Conteúdo da mensagem | LLM extrai identificação do anúncio/veículo |
| `mensagem_original` | `data.message.conversation` ou equivalente | Sempre salvo integralmente |

**Nota:** O LLM é usado **apenas para extração de dados**, não para interpretação de comandos do gerente (que são fixos).

---

## PARTE 3: Testes de Mesa

Simulação manual de cada cenário crítico do sistema para validar que as regras funcionam corretamente.

### Teste 1: Round-Robin Normal (3 vendedores, 6 leads)

**Resultado: PASSA**

**Setup:** Vendedores: A(ordem=1), B(ordem=2), C(ordem=3). Ponteiro inicial: A.

| Lead | Distribuído para | Ponteiro avança para |
|------|------------------|---------------------|
| 1 | A | B |
| 2 | B | C |
| 3 | C | A (wrap) |
| 4 | A | B |
| 5 | B | C |
| 6 | C | A (wrap) |

**Verificação:** Cada vendedor recebeu exatamente 2 leads. Distribuição justa.

---

### Teste 2: Desativação de Vendedor no Meio do Ciclo

**Resultado: PASSA**

**Setup:** A(1), B(2), C(3). Ponteiro: B. **Ação:** B é desativado.

**Comportamento esperado:** Conforme fluxo documentado, se `proximo_vendedor_id = B`, avançar ponteiro para próximo ativo.

| Evento | Resultado |
|--------|-----------|
| B desativado | Ponteiro avança para C |
| Lead 1 | Distribuído para C, ponteiro → A (wrap, pula B) |
| Lead 2 | Distribuído para A, ponteiro → C (pula B) |

**Verificação:** B corretamente excluído da fila. Distribuição continua entre A e C.

---

### Teste 3: Nenhum Vendedor Ativo

**Resultado: PASSA**

**Setup:** Todos os vendedores desativados. Ponteiro: NULL.

| Evento | Resultado |
|--------|-----------|
| Lead chega | `vendedor_id = NULL`, `distribuido_em = NULL` |
| | Lead persistido para auditoria |
| | Não encaminhado a ninguém |

**Verificação:** Conforme [[04 - Tratamento de Erros]]. Lead não se perde; fica registrado como não distribuído.

---

### Teste 4: Reativação de Vendedor

**Resultado: PASSA**

**Setup:** A(ordem=1), C(ordem=3) ativos. B é reativado.

**Comportamento:** B recebe `ordem_fila = 4` (último + 1). Nova fila: A(1), C(3), B(4).

| Lead | Distribuído para | Ponteiro |
|------|------------------|----------|
| 1 | A | C |
| 2 | C | B |
| 3 | B | A (wrap) |

**Verificação:** B entra no final da fila. Distribuição segue nova ordem corretamente.

---

### Teste 5: `proximo_vendedor_id` = NULL (Inicialização)

**Resultado: PASSA**

**Comportamento:** Query busca primeiro vendedor ativo por `ordem_fila ASC LIMIT 1`. Sistema se auto-inicializa.

---

### Teste 6: `ordem_fila` com Gaps

**Resultado: PASSA**

**Setup:** Vendedores com `ordem_fila`: 1, 5, 12 (gaps de vendedores removidos/reativados).

**Comportamento:** SQL usa `ordem_fila > :atual ORDER BY ordem_fila ASC LIMIT 1`. Gaps não afetam a lógica — o próximo é sempre o menor `ordem_fila` maior que o atual.

---

### Teste 7: Leads Simultâneos (Concorrência)

**Resultado: FALHA SEM LOCKING / PASSA COM CORREÇÃO**

**Cenário sem locking:**
```
Thread 1: lê ponteiro = A
Thread 2: lê ponteiro = A  ← concorrência!
Thread 1: distribui para A, ponteiro → B
Thread 2: distribui para A, ponteiro → B  ← DUPLICADO!

Resultado: A recebe 2, B recebe 0. INJUSTO.
```

**Com `SELECT FOR UPDATE` (correção aplicada):**
```
Thread 1: SELECT ... FOR UPDATE → lock na loja → lê ponteiro = A
Thread 2: SELECT ... FOR UPDATE → AGUARDA (lock)
Thread 1: distribui para A, ponteiro → B → COMMIT → libera lock
Thread 2: agora lê ponteiro = B → distribui para B → ponteiro → C

Resultado: A recebe 1, B recebe 1. JUSTO.
```

---

### Teste 8: Comando "status" do Gerente

**Resultado: PASSA** (com correção de unicidade global)

**Setup:** Gerente com `numero_whatsapp` único globalmente. Envia "status".

**Fluxo:**
1. Query: `SELECT loja_id FROM gerentes WHERE numero_whatsapp = :numero AND ativo = true` → retorna **1 linha**
2. Query: `COUNT(*) FROM leads WHERE loja_id = :id AND DATE(recebido_em) = CURRENT_DATE` → total do dia
3. Query: `SELECT ultima_distribuicao_em, proximo_vendedor.nome FROM lojas JOIN vendedores` → último horário e próximo

**Resposta montada corretamente e escopada pela loja do gerente.**

---

### Teste 9: Comando "relatorio" do Gerente

**Resultado: PASSA**

**Verificação:** `LEFT JOIN` com vendedores garante que **todos** os vendedores ativos aparecem, mesmo com 0 leads no dia. Corretamente escopado por `loja_id`.

---

### Teste 10: Troca de Número WhatsApp da Loja

**Resultado: PASSA**

**Ação:** `UPDATE lojas SET numero_whatsapp = 'novo', instancia_evolution = 'nova'`

**Verificação:** Todos os FKs usam `loja.id` (UUID), não o número. Vendedores, leads, estado da fila, gerentes — tudo preservado. Apenas a conexão (QR Code) precisa ser refeita.

---

### Teste 11: Tentativa de Cadastrar Mesmo Número como Gerente e Vendedor

**Resultado: PASSA** (com decisão da seção 2.3)

**Setup:** Tentativa de cadastrar número 5511999 como gerente E vendedor da Loja A.

**Comportamento:** O sistema **rejeita** o cadastro. Um número não pode ser gerente e vendedor ao mesmo tempo. A validação ocorre no momento do cadastro (operador do sistema). Isso simplifica a lógica de roteamento — os caminhos gerente/vendedor/lead são mutuamente exclusivos.

---

## PARTE 4: Schema Corrigido (DDL Final)

O DDL abaixo incorpora **todas** as correções identificadas nesta revisão:

```sql
-- Tabela: lojas
CREATE TABLE lojas (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nome VARCHAR(255) NOT NULL,
  numero_whatsapp VARCHAR(20),
  instancia_evolution VARCHAR(100),
  ativa BOOLEAN NOT NULL DEFAULT true,
  proximo_vendedor_id UUID,
  ultima_distribuicao_em TIMESTAMPTZ,
  criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- CORREÇÃO 1.3: Unicidade da instância Evolution (parcial, permite NULLs)
CREATE UNIQUE INDEX idx_lojas_instancia_unique
  ON lojas(instancia_evolution)
  WHERE instancia_evolution IS NOT NULL;

-- Tabela: vendedores
CREATE TABLE vendedores (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  loja_id UUID NOT NULL REFERENCES lojas(id) ON DELETE CASCADE,
  nome VARCHAR(255) NOT NULL,
  numero_whatsapp VARCHAR(20) NOT NULL,
  status VARCHAR(20) NOT NULL CHECK (status IN ('ativo', 'inativo', 'removido')),
  ordem_fila INTEGER NOT NULL,
  criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  -- CORREÇÃO 1.2: Unicidade GLOBAL (não por loja)
  UNIQUE(numero_whatsapp)
);

-- Tabela: gerentes
CREATE TABLE gerentes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  loja_id UUID NOT NULL REFERENCES lojas(id) ON DELETE CASCADE,
  numero_whatsapp VARCHAR(20) NOT NULL,
  nome VARCHAR(255) NOT NULL,
  ativo BOOLEAN NOT NULL DEFAULT true,
  criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  -- CORREÇÃO 1.1: Unicidade GLOBAL (não por loja)
  UNIQUE(numero_whatsapp)
);

-- Tabela: leads
CREATE TABLE leads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  loja_id UUID NOT NULL REFERENCES lojas(id) ON DELETE CASCADE,
  vendedor_id UUID REFERENCES vendedores(id) ON DELETE SET NULL,
  numero_cliente VARCHAR(20) NOT NULL,
  nome_cliente VARCHAR(255),
  anuncio VARCHAR(500),
  mensagem_original TEXT,
  recebido_em TIMESTAMPTZ NOT NULL,
  distribuido_em TIMESTAMPTZ,
  criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Índices para performance
CREATE INDEX idx_vendedores_loja_status_ordem
  ON vendedores(loja_id, status, ordem_fila);

CREATE INDEX idx_leads_loja_recebido
  ON leads(loja_id, recebido_em DESC);

CREATE INDEX idx_leads_loja_vendedor_recebido
  ON leads(loja_id, vendedor_id, recebido_em DESC);

CREATE INDEX idx_gerentes_numero
  ON gerentes(numero_whatsapp);

-- Foreign key da fila Round-Robin (ponteiro circular)
ALTER TABLE lojas
  ADD CONSTRAINT fk_proximo_vendedor
  FOREIGN KEY (proximo_vendedor_id)
  REFERENCES vendedores(id)
  ON DELETE SET NULL;
```

**Diferenças em relação ao DDL original ([[06 - Modelo de Dados Detalhado]]):**

| Item | Original | Corrigido | Motivo |
|------|----------|-----------|--------|
| `vendedores` UNIQUE | `UNIQUE(loja_id, numero_whatsapp)` | `UNIQUE(numero_whatsapp)` | Regra: vendedor pertence a 1 loja |
| `gerentes` UNIQUE | `UNIQUE(loja_id, numero_whatsapp)` | `UNIQUE(numero_whatsapp)` | Regro sistema: gerente vinculado a 1 loja |
| `lojas.instancia_evolution` | Sem constraint | `UNIQUE INDEX ... WHERE NOT NULL` | Previne 2 lojas com mesma instância |
| Timestamps | `TIMESTAMP` | `TIMESTAMPTZ` | Boas práticas PostgreSQL (timezone-aware) |
| `idx_vendedores_loja_numero` | Existia | Removido | Redundante com UNIQUE global |
| `idx_gerentes_numero_loja` | `(numero_whatsapp, loja_id)` | `(numero_whatsapp)` | Simplificado pela unicidade global |

---

## PARTE 5: Ordem de Implementação

```
PASSO 1 ─ Corrigir documentação (7 arquivos)
           Ajustar inconsistências e adicionar lacunas
           ↓
PASSO 2 ─ Criar schema no Supabase (1 migration)
           Tabelas + constraints corrigidas + índices
           ↓
PASSO 3 ─ Criar função distribuir_lead() (1 migration)
           Transação atômica com FOR UPDATE
           ↓
PASSO 4 ─ Criar funções fn_status() e fn_relatorio() (1 migration)
           Helpers para comandos do gerente
           ↓
PASSO 5 ─ Habilitar RLS no Supabase
           Negar anon key, permitir service_role
           ↓
PASSO 6 ─ Seed data para testes
           1 loja, 3 vendedores, 1 gerente
           ↓
PASSO 7 ─ Construir workflow n8n
           Webhook → Roteamento → Lead/Comando paths
```

---

## PARTE 6: Checklist de Verificação Pós-Implementação

- [ ] Round-Robin distribui corretamente entre vendedores ativos
- [ ] Vendedor inativo é ignorado na distribuição
- [ ] Nenhum vendedor ativo → lead persistido com `vendedor_id = NULL`
- [ ] Dois leads simultâneos vão para vendedores diferentes
- [ ] Comando "status" retorna dados corretos do dia
- [ ] Comando "relatorio" mostra todos os vendedores ativos (mesmo com 0 leads)
- [ ] Gerente envia texto aleatório → recebe "Comando não reconhecido"
- [ ] Número não-gerente envia "status" → ignorado
- [ ] Vendedor envia mensagem para número da loja → ignorado
- [ ] Dados de Loja A nunca aparecem em consultas da Loja B
- [ ] Troca de número WhatsApp da loja preserva todos os dados
- [ ] RLS bloqueia acesso via anon key
- [ ] Mensagens de mídia (imagem, áudio) são distribuídas normalmente
- [ ] Supabase advisors (security + performance) sem alertas críticos

---

## Documentos Afetados pelas Correções

| Documento | Alterações necessárias |
|-----------|----------------------|
| [[06 - Modelo de Dados Detalhado]] | Corrigir UNIQUE constraints, adicionar UNIQUE em instancia_evolution, adicionar FOR UPDATE nos exemplos SQL, atualizar DDL, mudar TIMESTAMP para TIMESTAMPTZ |
| [[04 - Isolamento Multi-Loja]] | Linha 23: fixar regra gerente para "apenas uma loja no sistema"; adicionar nota sobre overlap gerente-vendedor |
| [[02 - Modelo Mental de Dados]] | Linha 11: trocar "uma (ou mais) loja(s)" por "uma loja (versão atual)" |
| [[01 - Fluxo Principal]] | Adicionar seção com árvore de decisão de roteamento; nota sobre parsing best-effort; nota sobre mídia |
| [[02 - Comandos via WhatsApp]] | Adicionar comportamento para mensagem não-comando do gerente |
| [[04 - Tratamento de Erros]] | Adicionar caso: mensagem de vendedor (ignorar); caso: mídia (encaminhar) |
| [[03 - Fluxos Técnicos (n8n)]] | Adicionar nota sobre mensagens de mídia |
