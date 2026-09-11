# Conexão Supabase via DBeaver

## Dados de Conexão

| Campo | Valor |
|---|---|
| **Host** | `aws-1-sa-east-1.pooler.supabase.com` |
| **Port** | `5432` |
| **Database** | `postgres` |
| **Username** | `postgres.drtdctpwxkqqnhnikpwz` |
| **Password** | *(senha do banco de dados do projeto Supabase)* |

## Passo a Passo

### 1. Criar nova conexão

1. Abrir DBeaver
2. Menu **Database > New Database Connection** (ou atalho `Ctrl+Shift+N` / `Cmd+Shift+N`)
3. Selecionar **PostgreSQL** e clicar em **Next**

### 2. Preencher dados do servidor

1. **Connect by:** Host
2. Preencher **Host**, **Port**, **Database** e **Username** conforme tabela acima
3. Preencher o campo **Password**
4. Marcar **Save password**

### 3. Configurar SSL (obrigatório)

1. Clicar na aba **SSH, SSL, ...** (canto superior direito da tela de conexão)
2. Ir na sub-aba **SSL**
3. Marcar **Use SSL**
4. Em **SSL mode**, selecionar **require**
5. Deixar os campos de certificado em branco

### 4. Testar e finalizar

1. Clicar em **Test Connection**
2. Se aparecer "Connected", clicar em **Finish**

## Observações

- A senha do banco pode ser consultada ou resetada em: **Supabase Dashboard > Settings > Database > Database password**
- Resetar a senha do banco **não** afeta o n8n nem o Dashboard Streamlit (ambos usam API REST com service_role key)
- O host `aws-1-sa-east-1.pooler.supabase.com` usa o **Connection Pooler** do Supabase (Supavisor), recomendado para conexões externas
