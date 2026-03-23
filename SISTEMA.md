# Sistema de Distribuição de Leads via WhatsApp

## O que o sistema faz

Recebe leads por WhatsApp (de portais como iCarros, NaPista ou direto) e distribui automaticamente para vendedores usando Round-Robin (distribuição justa, um por vez, em sequência).

---

## Arquitetura

### n8n (Backend/Orquestração)
- Recebe mensagens do WhatsApp via webhook (Evolution API)
- Identifica a loja (multi-tenant)
- Extrai dados do lead (nome cliente, anúncio, telefone)
- Salva no banco (PostgreSQL/Supabase)
- Executa Round-Robin: seleciona próximo vendedor ativo da fila
- Encaminha lead para o vendedor via WhatsApp
- Atualiza ponteiro da fila para o próximo

### App Web (Dashboard Streamlit)
Interface de gerenciamento para lojas:

**Dashboard**
- Métricas do dia (total leads, último lead, próximo vendedor)
- Fila de distribuição (arraste para reordenar)
- Atividades recentes (log em tempo real)
- Gráficos (tendência, origem, horários, funil de vendas)

**Gerentes**
- Cadastro de gerentes (nome + WhatsApp)
- Ativar/desativar gerentes

**Vendedores**
- Adicionar/remover vendedores
- Ativar/pausar (inativos não recebem leads)
- Reordenar fila manualmente

**Leads**
- Lista completa com filtros (data, vendedor, origem, status)
- Edição de status inline (novo → atendido → negociando → venda/desistiu)
- Auto-save instantâneo

---

## Fluxo completo

1. **Cliente envia WhatsApp** → Evolution API
2. **Evolution API** → n8n webhook
3. **n8n** processa:
   - Identifica loja
   - Extrai dados do lead
   - Persiste no Supabase
   - Round-Robin: pega próximo vendedor ativo
   - Encaminha lead via WhatsApp
4. **Vendedor recebe** mensagem no WhatsApp
5. **Dashboard reflete**: lead aparece em atividades, métricas atualizam, fila avança

---

## Stack Técnica

- **n8n**: Orquestração de workflows
- **Evolution API**: Gateway WhatsApp
- **Supabase/PostgreSQL**: Banco de dados + RLS
- **Streamlit**: Interface web (Python)
- **Deploy**: Streamlit Cloud (app) + n8n Cloud/self-hosted

---

## V1 Scope
✅ Distribuição Round-Robin fair (sem pesos)
✅ Multi-tenant (isolamento por loja)
✅ Comandos WhatsApp: `/status`, `/leads`
✅ Interface web completa
✅ Log de atividades em tempo real

❌ Fora do sistema: Dashboard analytics avançado, IA/ML, integrações API diretas (OLX/Webmotors), SLA tracking, app mobile
