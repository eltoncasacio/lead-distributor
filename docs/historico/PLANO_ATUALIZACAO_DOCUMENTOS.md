# 📝 PLANO DE ATUALIZAÇÃO DE DOCUMENTOS
**Data:** 2026-02-19
**Baseado em:** AUDITORIA_TECNICA_2026-02-19.md

---

## 🎯 OBJETIVO

Atualizar documentação para refletir o **estado real** do sistema conforme auditoria técnica.

---

## 📋 DOCUMENTOS QUE PRECISAM ATUALIZAÇÃO

### 1. ❌ CRÍTICO: Técnica/08 - Workflow n8n - Documentação Detalhada.md

**Problemas encontrados:**
- ❌ Menciona **NaPista** (linhas 19, 42-44) que **NÃO EXISTE** no workflow real
- ❌ Total de nós: documenta 34, real é **43 nós**
- ❌ Diagrama de fluxo inclui branches inexistentes
- ❌ Não menciona **código duplicado** (5 pares de nós)

**Ações:**
- [ ] REMOVER todas as menções a NaPista
- [ ] ATUALIZAR diagrama de fluxo (remover branches NaPista)
- [ ] CORRIGIR total de nós: 43 (37 operacionais + 6 sticky notes)
- [ ] ADICIONAR seção sobre código duplicado
- [ ] ATUALIZAR "Verificar Origem" para apenas icarros + fallback

---

### 2. ⚠️ MÉDIO: Operação/04 - Tratamento de Erros.md

**Problemas encontrados:**
- ⚠️ Documento descreve tratamento de erros como se estivesse implementado
- ⚠️ Auditoria mostrou: **NENHUM retry implementado**
- ⚠️ Documento não deixa claro que é "especificação" vs "implementado"

**Ações:**
- [ ] ADICIONAR seção "⚠️ STATUS DE IMPLEMENTAÇÃO"
- [ ] MARCAR cada item como "✅ Implementado" ou "❌ Não Implementado"
- [ ] ADICIONAR nota: "Este documento descreve comportamento ESPERADO, não atual"

---

### 3. ⚠️ MÉDIO: Técnica/03 - Fluxos Técnicos (n8n).md

**Problemas encontrados:**
- ⚠️ Linha 37: Menciona "extração de dados via LLM" que **NÃO EXISTE**
- ⚠️ Não menciona ausência de error handling

**Ações:**
- [ ] REMOVER seção "Extração de dados via LLM" (não implementado)
- [ ] ADICIONAR nota sobre ausência de retry/error handling

---

### 4. 🟢 BAIXO: Técnica/07 - Revisão e Validação Pré-Implementação.md

**Problemas encontrados:**
- 🟢 Documento está correto mas desatualizado (fala "Pré-Implementação")
- 🟢 Não reflete estado pós-implementação

**Ações:**
- [ ] ATUALIZAR título para "Revisão Pré-Implementação (HISTÓRICO)"
- [ ] ADICIONAR nota: "Este documento reflete validação ANTES da implementação"
- [ ] REFERENCIAR AUDITORIA_TECNICA_2026-02-19.md para estado atual

---

### 5. ✅ CRIAR NOVO: Técnica/09 - Estado Real vs Documentado.md

**Objetivo:** Documento reconciliador entre spec e realidade

**Conteúdo:**
- [ ] Tabela comparativa: "Documentado" vs "Implementado"
- [ ] Gaps conhecidos (NaPista, LLM, retry)
- [ ] Código duplicado não documentado
- [ ] Referência cruzada com auditoria

---

## 📊 RESUMO DE GAPS ENCONTRADOS

| Item | Documentado | Implementado | Ação |
|---|---|---|---|
| **NaPista** | ✅ Sim (Técnica/08) | ❌ Não | Remover docs |
| **LLM extraction** | ✅ Sim (Técnica/03) | ❌ Não | Remover docs |
| **Error handling** | ✅ Sim (Operação/04) | ❌ Não | Marcar como "spec" |
| **Retry em HTTP** | ❌ Não documentado | ❌ Não | OK (consistente) |
| **Código duplicado** | ❌ Não documentado | ✅ Sim (5 pares) | Adicionar docs |
| **icarros** | ✅ Sim | ✅ Sim | OK |
| **Round-Robin** | ✅ Sim | ✅ Sim | OK |
| **Isolamento multi-loja** | ✅ Sim | ✅ Sim | OK |

---

## 🚀 ORDEM DE EXECUÇÃO

1. **Técnica/08** (CRÍTICO - documento mais consultado)
2. **Técnica/09** (CRIAR NOVO - reconciliação)
3. **Operação/04** (MÉDIO - operadores consultam)
4. **Técnica/03** (MÉDIO - desenvolvedores)
5. **Técnica/07** (BAIXO - histórico)

---

## ✅ CHECKLIST FINAL

Após atualizações, verificar:
- [ ] Nenhuma menção a NaPista em documentos técnicos
- [ ] Nenhuma menção a LLM extraction
- [ ] Operação/04 deixa claro que é "spec" não "implementado"
- [ ] Técnica/08 reflete 43 nós reais
- [ ] Técnica/09 criado como ponte entre spec e realidade
- [ ] Referências cruzadas entre auditoria e docs atualizados

---

**Status:** Plano criado, aguardando execução
