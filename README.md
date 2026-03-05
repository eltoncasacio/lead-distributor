# 📊 Sistema de Distribuição de Leads - App Web

Interface web (Streamlit) para gerenciar vendedores, visualizar KPIs e controlar fila de distribuição.

## 🚀 Setup Local

### 1. Instalar dependências

```bash
pip install -r requirements.txt
```

### 2. Configurar variáveis de ambiente

Copie `.env.example` para `.env` e preencha:

```bash
cp .env.example .env
```

Edite o `.env` com as credenciais do Supabase Dev:

```
SUPABASE_URL=https://iiiapbjzeruaqegotdvp.supabase.co
SUPABASE_SERVICE_KEY=<sua_service_key_aqui>
```

### 3. Rodar o app

```bash
streamlit run Home.py
```

### 4. Fazer login

Use um dos códigos fake:
- **Auto Show SP:** `AUT-20260304-X7Y2`
- **Mega Veículos RJ:** `MEG-20260304-K9L3`

## 📁 Estrutura

```
streamlit-lead-distributor/
├── Home.py                  # Página de login
├── pages/
│   ├── 1_📊_Dashboard.py   # Dashboard (placeholder - Semana 3)
│   ├── 2_👨‍💼_Gerentes.py   # CRUD Gerentes ✅
│   └── 3_👤_Vendedores.py  # CRUD Vendedores ✅
├── utils/
│   ├── auth.py             # Sistema de autenticação
│   ├── supabase_client.py  # Cliente Supabase
│   ├── ui.py               # Componentes reutilizáveis
│   ├── queries.py          # Queries SQL ✅
│   └── validators.py       # Validações ✅
├── requirements.txt
├── .env                     # Configuração local (gitignored)
└── README.md
```

## ✅ Status - Semana 1

- [x] Estrutura de pastas
- [x] Requirements.txt
- [x] Cliente Supabase
- [x] Sistema de autenticação
- [x] Página de login
- [x] Template base (header + logout)
- [ ] Teste completo

### ✅ Checklist de Testes

Execute estes testes para validar a Semana 1:

**1. Teste de login válido:**
- [ ] Login com `AUT-20260304-X7Y2` funciona
- [ ] Nome "Auto Show SP" aparece no header
- [ ] Dashboard placeholder carrega

**2. Teste de isolamento:**
- [ ] Logout
- [ ] Login com `MEG-20260304-K9L3`
- [ ] Nome "Mega Veículos RJ" aparece no header
- [ ] Confirma que é loja diferente

**3. Teste de código inválido:**
- [ ] Logout
- [ ] Tenta login com `CODIGO-INVALIDO-XXX`
- [ ] Mostra erro "Código inválido"

**4. Teste de navegação:**
- [ ] Estando logado, clica no sidebar em "Dashboard"
- [ ] Página carrega sem erro
- [ ] Botão "Sair" funciona
- [ ] Redireciona para login após logout

## ✅ Status - Semana 2

- [x] utils/queries.py com funções SQL
- [x] utils/validators.py com validações
- [x] Página Gerentes com CRUD completo
- [x] Página Vendedores com CRUD completo
- [x] Validação WhatsApp único
- [x] Validação último vendedor ativo
- [ ] Teste completo

### ✅ Checklist de Testes - Semana 2

**Gerentes:**
- [ ] Adicionar gerente com WhatsApp válido
- [ ] Tentar adicionar com WhatsApp duplicado → deve dar erro
- [ ] Editar nome de gerente existente
- [ ] Desativar gerente
- [ ] Deletar gerente

**Vendedores:**
- [ ] Adicionar vendedor → deve aparecer no final da fila
- [ ] Ver "próximo vendedor" destacado
- [ ] Tentar adicionar vendedor com WhatsApp de gerente → deve dar erro
- [ ] Editar vendedor
- [ ] Inativar vendedor (tendo 2+ ativos)
- [ ] Tentar inativar único vendedor ativo → botão deve estar desabilitado
- [ ] Ativar vendedor inativo
- [ ] Remover vendedor da fila

## 🔜 Próximas Semanas

- **Semana 3:** Dashboard com KPIs + Origem
- **Semana 4:** Status de Leads + Drag-Drop
- **Semana 5:** Testes + Deploy
