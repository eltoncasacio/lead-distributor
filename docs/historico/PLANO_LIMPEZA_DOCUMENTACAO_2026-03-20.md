# Plano de Limpeza e Organização da Documentação

**Data:** 2026-03-20
**Objetivo:** Eliminar documentos duplicados, desatualizados ou sem valor, preservando conhecimento útil.

---

## 📊 Análise de Arquivos

### ✅ MANTER (Documentação Core)

Estes documentos são essenciais e devem permanecer:

**Diretório raiz:**
- `Sumário.md` — Índice principal ✅
- `CLAUDE.md` — Instruções para Claude Code ✅
- `Conexão Supabase via DBeaver.md` — Tutorial técnico útil ✅

**Documento Comercial/** (4 arquivos)
- Todos mantidos ✅ — Visão comercial consolidada

**Produto/** (5 arquivos - **1 duplicado**)
- `01 - Visão Geral e Problema.md` ✅
- `01 - Visão Geral.md` ❌ **DUPLICADO - DELETAR** (conteúdo similar ao de cima)
- `03 - Público-Alvo.md` ✅
- `04 - Objetivo do Sistema.md` ✅
- `05 - Princípios do Produto.md` ✅

**Regras de Negócio/** (5 arquivos)
- Todos mantidos ✅ — Regras core do sistema

**Operação/** (4 arquivos)
- Todos mantidos ✅ — Fluxos operacionais críticos

**Técnica/** (11 arquivos)
- Todos mantidos ✅ — Arquitetura e implementação

**Fora do Escopo/**
- `Roadmap Futuro.md` ✅ — Recém-renomeado e atualizado

---

## ❌ DELETAR ou CONSOLIDAR

### 1. Arquivos Históricos/Auditoria (mover para `docs/historico/`)

**Ação:** MOVER para `docs/historico/` (já existe)

- ❌ `AUDITORIA_TECNICA_2026-02-19.md` → mover
- ❌ `DOCUMENTOS_ATUALIZADOS_2026-02-19.md` → mover
- ❌ `docs/REORGANIZACAO_2026-02-28.md` → **já está em `docs/`**, mover para `docs/historico/`

### 2. Planos Implementados ou Obsoletos

**Ação:** DELETAR (conteúdo já consolidado em documentos finais)

- ❌ `PLANO_APP_WEB_STREAMLIT.md` — **DELETAR** (conteúdo consolidado em `Técnica/11 - Dashboard Web Streamlit.md`)
- ❌ `IMPLEMENTACAO_FILTROS_DATA.md` — **DELETAR** (feature já implementada, sem valor futuro)
- ❌ `docs/VALIDACAO_FLUXO_N8N.md` — **DELETAR** (checklist de validação concluída, histórico sem valor)
- ❌ `docs/N8N_DOCUMENT/Plano - Fluxo n8n Distribuição de Leads.md` — **MANTER** (referência técnica valiosa, mas verificar duplicação com outros docs)

### 3. Arquivos Fragmentados / Notas

**Ação:** CONSOLIDAR ou DELETAR

- ❌ `Ideias.md` — **REVISAR CONTEÚDO** → mover itens válidos para `Roadmap Futuro.md`, depois deletar
- ❌ `📄 Documento Comercial.md` — **DUPLICADO** de `Documento Comercial/00 - Produto.md`? **VERIFICAR e DELETAR se duplicado**
- ❌ `WORKFLOW-EXPLICACAO.md` — **VERIFICAR** se conteúdo duplica `Técnica/08 - Workflow n8n - Documentação Detalhada.md`. Se sim, DELETAR.

### 4. Documentos em `docs/` (fora de `docs/historico/`)

**Ação:** MOVER para subdiretórios apropriados ou DELETAR

- ❌ `docs/ESTILIZACAO.md` — **MOVER** para `lead-distributor/docs/` (específico do Dashboard)
- ❌ `docs/INFRA.md` — **MANTER** (referência de infraestrutura útil)
- ❌ `docs/NOVA_FEATURE.md` — **DELETAR** (nome genérico, provavelmente obsoleto — revisar conteúdo primeiro)
- ❌ `docs/OPERACAO_ONBOARDING_NOVA_LOJA.md` — **MANTER** (tutorial operacional valioso)
- ❌ `docs/dados-loja.md` — **VERIFICAR** se tem dados sensíveis ou se é apenas exemplo. Se exemplo, manter. Se dados reais, **DELETAR ou MOVER para fora do repositório**.

### 5. Diretório `docs/N8N_DOCUMENT/`

**Ação:** AVALIAR cada arquivo

- ✅ `API-e-Exemplos.md` — MANTER (referência técnica)
- ✅ `N8N-MCP.md` — MANTER (documentação MCP tools)
- ❓ `Plano - Fluxo n8n Distribuição de Leads.md` — **VERIFICAR** se duplica `Técnica/03` ou `Técnica/08`. Se duplica, consolidar e deletar.
- ✅ `README.md` — MANTER (índice do diretório)

### 6. Diretório `docs/project-build/`

**Ação:** MANTER (prompts para IA)

- ✅ `base.md` — Prompt base
- ✅ `doc-create.md` — Prompt de criação de docs

---

## 🗂️ Estrutura Final Proposta

```
02 - Sistema de Distribuição de Leads/
├── Sumário.md
├── CLAUDE.md
├── Conexão Supabase via DBeaver.md
│
├── Documento Comercial/ (4 arquivos) ✅
├── Produto/ (4 arquivos - após deletar duplicado) ✅
├── Regras de Negócio/ (5 arquivos) ✅
├── Operação/ (4 arquivos) ✅
├── Técnica/ (11 arquivos) ✅
├── Fora do Escopo/ (1 arquivo) ✅
│
├── docs/
│   ├── historico/ (3+ arquivos movidos)
│   ├── roteiros-video/ (3 arquivos) ✅
│   ├── N8N_DOCUMENT/ (4 arquivos) ✅
│   ├── project-build/ (2 arquivos) ✅
│   ├── prompts/ (1 arquivo) ✅
│   ├── INFRA.md ✅
│   ├── OPERACAO_ONBOARDING_NOVA_LOJA.md ✅
│   └── dados-loja.md (se não sensível) ✅
│
└── lead-distributor/ (código + docs específicos)
    ├── README.md ✅
    ├── SETUP.md ✅
    ├── SISTEMA.md ✅
    ├── IDEIAS_MELHORIA.md ✅
    └── docs/
        └── ESTILIZACAO.md (movido)
```

---

## 📋 Checklist de Execução

### Fase 1: Revisão Manual (FAZER ANTES DE DELETAR)

- [ ] Abrir `Ideias.md` → migrar itens úteis para `Roadmap Futuro.md`
- [ ] Abrir `📄 Documento Comercial.md` → comparar com `Documento Comercial/00 - Produto.md` → confirmar duplicação
- [ ] Abrir `WORKFLOW-EXPLICACAO.md` → comparar com `Técnica/08` → confirmar duplicação
- [ ] Abrir `docs/NOVA_FEATURE.md` → revisar conteúdo → decidir se tem valor
- [ ] Abrir `docs/dados-loja.md` → verificar se há dados sensíveis (números reais, nomes reais)
- [ ] Abrir `Produto/01 - Visão Geral.md` → comparar com `01 - Visão Geral e Problema.md` → confirmar qual manter

### Fase 2: Backup

- [ ] Criar backup completo antes de qualquer deleção:
  ```bash
  cd "/Users/eltoncasaccia/Documents/Obsidian Vault/02 - Sistema de Distribuição de Leads"
  tar -czf "../backup-pre-cleanup-$(date +%Y%m%d-%H%M%S).tar.gz" .
  ```

### Fase 3: Mover para Histórico

- [ ] Mover `AUDITORIA_TECNICA_2026-02-19.md` → `docs/historico/`
- [ ] Mover `DOCUMENTOS_ATUALIZADOS_2026-02-19.md` → `docs/historico/`
- [ ] Mover `docs/REORGANIZACAO_2026-02-28.md` → `docs/historico/`

### Fase 4: Deletar Arquivos Consolidados

- [ ] Deletar `PLANO_APP_WEB_STREAMLIT.md` (conteúdo em `Técnica/11`)
- [ ] Deletar `IMPLEMENTACAO_FILTROS_DATA.md` (feature implementada)
- [ ] Deletar `docs/VALIDACAO_FLUXO_N8N.md` (validação concluída)
- [ ] Deletar `Produto/01 - Visão Geral.md` (duplicado - APÓS confirmar)
- [ ] Deletar `📄 Documento Comercial.md` (duplicado - APÓS confirmar)
- [ ] Deletar `WORKFLOW-EXPLICACAO.md` (duplicado - APÓS confirmar)
- [ ] Deletar `Ideias.md` (APÓS migrar conteúdo útil)
- [ ] Deletar `docs/NOVA_FEATURE.md` (APÓS revisar)

### Fase 5: Reorganizar

- [ ] Mover `docs/ESTILIZACAO.md` → `lead-distributor/docs/ESTILIZACAO.md`
- [ ] Atualizar wikilinks no Sumário.md se algum arquivo foi renomeado

### Fase 6: Validação Final

- [ ] Abrir Obsidian e testar navegação completa pelo Sumário.md
- [ ] Verificar se todos wikilinks funcionam (não há links quebrados)
- [ ] Testar busca por palavras-chave críticas: "Round-Robin", "Deduplicação", "Dashboard"

---

## 💡 Resultado Esperado

**Antes:**
- 60+ arquivos markdown (muitos duplicados/obsoletos)
- Estrutura confusa (planos misturados com docs finais)
- Difícil navegar e encontrar informação

**Depois:**
- ~40 arquivos markdown (apenas essenciais)
- Estrutura clara: Comercial / Produto / Regras / Operação / Técnica
- Histórico separado em `docs/historico/`
- Fácil navegação via Sumário.md

---

## ⚠️ IMPORTANTE

**NUNCA DELETAR SEM REVISAR CONTEÚDO PRIMEIRO!**

Antes de executar qualquer deleção:
1. Abrir arquivo
2. Ler conteúdo completo
3. Buscar no vault se há informação única
4. Se houver dúvida, **mover para `docs/historico/`** em vez de deletar

Princípio: **É melhor manter arquivo desnecessário do que perder conhecimento valioso.**
