# Deploy no Railway

Este guia explica como fazer o deploy do WhatsApp AI Assistant no Railway.

## Pré-requisitos

1. Conta no [Railway](https://railway.app/)
2. Repositório Git configurado (GitHub, GitLab ou Bitbucket)
3. Credenciais das APIs externas (Twilio, Google Gemini, SMTP)

---

## Arquitetura no Railway

```
┌─────────────────────────────────────────────────────────────┐
│                     Railway Project                          │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  PostgreSQL │  │    Redis    │  │      Backend        │  │
│  │   (Plugin)  │  │   (Plugin)  │  │   (Dockerfile)      │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                      Frontend                            ││
│  │                   (Dockerfile)                           ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

---

## Passo 1: Criar Projeto no Railway

1. Acesse [railway.app](https://railway.app/) e faça login
2. Clique em **"New Project"**
3. Selecione **"Deploy from GitHub repo"**
4. Conecte seu repositório

---

## Passo 2: Adicionar PostgreSQL

1. No projeto, clique em **"+ New"** → **"Database"** → **"PostgreSQL"**
2. Aguarde a criação do banco
3. Clique no PostgreSQL e vá em **"Variables"**
4. Copie a variável `DATABASE_URL`

**Importante:** Após criar, execute a extensão pgvector:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

---

## Passo 3: Adicionar Redis

1. Clique em **"+ New"** → **"Database"** → **"Redis"**
2. Aguarde a criação
3. Copie a variável `REDIS_URL`

---

## Passo 4: Deploy do Backend

1. Clique em **"+ New"** → **"GitHub Repo"**
2. Selecione seu repositório
3. Configure o **Root Directory**: `backend`
4. O Railway detectará o `Dockerfile` automaticamente

### Variáveis de Ambiente do Backend

Vá em **"Variables"** e adicione:

```env
# Conexão com banco (Railway fornece automaticamente)
DATABASE_URL=${{Postgres.DATABASE_URL}}

# Conexão com Redis (Railway fornece automaticamente)
REDIS_URL=${{Redis.REDIS_URL}}

# API Settings
API_V1_STR=/api/v1
PROJECT_NAME=WhatsApp AI Assistant
DEBUG=false

# Twilio WhatsApp
TWILIO_ACCOUNT_SID=seu_account_sid
TWILIO_AUTH_TOKEN=seu_auth_token
TWILIO_WHATSAPP_NUMBER=+14155238886
WHATSAPP_WEBHOOK_URL=https://seu-backend.up.railway.app/api/v1/webhook/whatsapp

# Google Gemini
GOOGLE_API_KEY=sua_api_key
GEMINI_MODEL=gemini-2.5-flash
GEMINI_TEMPERATURE=0.7
GEMINI_MAX_OUTPUT_TOKENS=40000

# JWT Security (gere com: openssl rand -hex 32)
SECRET_KEY=sua_secret_key_gerada
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080

# CORS (adicione URL do frontend depois de criar)
BACKEND_CORS_ORIGINS=["https://seu-frontend.up.railway.app"]

# SMTP (Gmail)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seu_email@gmail.com
SMTP_PASSWORD=sua_app_password
SMTP_FROM_EMAIL=seu_email@gmail.com

# General
DEFAULT_TIMEZONE=America/Sao_Paulo
LANGGRAPH_MEMORY_STORE=postgres
```

### Configurar Porta

Em **"Settings"** → **"Networking"**:
- Gere um domínio público
- A porta será detectada automaticamente (8005)

---

## Passo 5: Deploy do Frontend

1. Clique em **"+ New"** → **"GitHub Repo"**
2. Selecione o mesmo repositório
3. Configure o **Root Directory**: `frontend`

### Variáveis de Ambiente do Frontend

```env
VITE_API_URL=https://seu-backend.up.railway.app/api/v1
```

### Build Arguments

Em **"Settings"** → **"Build"**, adicione:
```
VITE_API_URL=https://seu-backend.up.railway.app/api/v1
```

---

## Passo 6: Configurar Domínios

1. Backend: Em **"Settings"** → **"Networking"** → **"Generate Domain"**
2. Frontend: Mesmo processo
3. Atualize as variáveis de ambiente com os novos domínios

---

## Passo 7: Configurar Webhook do Twilio

1. Acesse o [Console do Twilio](https://console.twilio.com/)
2. Vá em **Messaging** → **Settings** → **WhatsApp Sandbox Settings**
3. Configure o webhook:
   ```
   https://seu-backend.up.railway.app/api/v1/webhook/whatsapp
   ```

---

## Passo 8: Verificar Deploy

1. Acesse o health check:
   ```
   https://seu-backend.up.railway.app/health
   ```

2. Deve retornar:
   ```json
   {"status": "healthy", "timestamp": "..."}
   ```

3. Para verificação detalhada:
   ```
   https://seu-backend.up.railway.app/health/detailed
   ```

---

## Troubleshooting

### Erro de Conexão com Banco

Verifique se `DATABASE_URL` está configurado corretamente usando a referência do Railway:
```
${{Postgres.DATABASE_URL}}
```

### Erro de CORS

Certifique-se de que `BACKEND_CORS_ORIGINS` inclui a URL exata do frontend.

### Build Falhou

Verifique os logs em **"Deployments"** → Clique no deploy → **"View Logs"**

### pgvector não instalado

Conecte ao PostgreSQL via Railway CLI ou psql e execute:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

---

## Comandos Úteis

### Railway CLI

Instalar:
```bash
npm install -g @railway/cli
```

Login:
```bash
railway login
```

Ver logs:
```bash
railway logs
```

Conectar ao banco:
```bash
railway connect postgres
```

---

## Custos Estimados

| Serviço | Plano Gratuito | Uso Estimado |
|---------|----------------|--------------|
| PostgreSQL | 500MB | ~100MB/mês |
| Redis | 100MB | ~10MB/mês |
| Backend | 500h/mês | ~720h/mês (precisa upgrade) |
| Frontend | 500h/mês | ~720h/mês (precisa upgrade) |

**Recomendação:** Para produção, considere o plano **Hobby ($5/mês)** ou **Pro ($20/mês)**.

---

## Checklist Pré-Deploy

- [ ] `.env` não está no repositório
- [ ] `.gitignore` inclui `.env`
- [ ] Todas as credenciais são via variáveis de ambiente
- [ ] CORS configurado para o domínio correto
- [ ] Webhook do Twilio atualizado
- [ ] Health check funcionando
- [ ] pgvector extension criada
