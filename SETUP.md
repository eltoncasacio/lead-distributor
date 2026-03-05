# 🔧 Setup Rápido - Primeira Execução

## 1. Obter Service Key do Supabase Dev

A service key está configurada no MCP. Para rodar o app localmente, você precisa criá-la no arquivo `.env`.

### Opção A: Via Dashboard Supabase

1. Acesse: https://supabase.com/dashboard/project/iiiapbjzeruaqegotdvp/settings/api
2. Copie a `service_role` key (seção "Project API keys")
3. Cole no `.env` (veja passo 2)

### Opção B: Via Claude (você já tem acesso via MCP)

A key já está configurada no seu ambiente Claude. Se precisar, pode pedir para eu buscá-la.

## 2. Criar arquivo .env

```bash
cd streamlit-lead-distributor
cp .env.example .env
```

Edite o `.env` e cole a service key:

```
SUPABASE_URL=https://iiiapbjzeruaqegotdvp.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGci...  # Cole aqui a key real
```

## 3. Instalar e rodar

```bash
# Instalar dependências
pip install -r requirements.txt

# Rodar app
streamlit run Home.py
```

## 4. Testar login

Navegador abrirá em `http://localhost:8501`

Use um dos códigos:
- `AUT-20260304-X7Y2` (Auto Show SP)
- `MEG-20260304-K9L3` (Mega Veículos RJ)

## ✅ Resultado esperado

- Login funciona
- Nome da loja aparece no topo
- Dashboard placeholder carrega
- Botão "Sair" funciona

## 🐛 Troubleshooting

**Erro "Credenciais não encontradas":**
- Verifique se `.env` existe e está preenchido
- Verifique se `python-dotenv` está instalado

**Erro de conexão Supabase:**
- Confirme URL: `https://iiiapbjzeruaqegotdvp.supabase.co`
- Confirme que service key começa com `eyJ...`

**Página em branco após login:**
- Normal! Dashboard completo será implementado na Semana 3
- Por enquanto é só placeholder
