# Deploy do Frontend no Railway

## Repositório
```
https://github.com/LoboProgrammingg/AI-Assistant-company-frontend
```

## Backend URL
```
https://ai-assistante-company-production.up.railway.app
```

---

## Passo 1: Criar Serviço no Railway

1. Acesse [railway.app](https://railway.app/)
2. Abra o projeto **AI-Assistante-company** (mesmo projeto do backend)
3. Clique em **"+ New"** → **"GitHub Repo"**
4. Selecione o repositório: `AI-Assistant-company-frontend`
5. O Railway detectará automaticamente o `Dockerfile`

---

## Passo 2: Configurar Variáveis de Ambiente

Vá em **Settings** → **Variables** e adicione:

### Build Arguments (importante!)
```env
VITE_API_URL=https://ai-assistante-company-production.up.railway.app/api/v1
```

**IMPORTANTE:** Esta variável precisa ser configurada como **Build Argument** porque o Vite embute as variáveis no build.

### Como configurar Build Arguments:
1. Vá em **Settings** → **Variables**
2. Clique em **"+ New Variable"**
3. Nome: `VITE_API_URL`
4. Valor: `https://ai-assistante-company-production.up.railway.app/api/v1`
5. ✅ Marque a opção **"Build Variable"** ou **"Build Argument"**

---

## Passo 3: Configurar Domínio Público

1. Vá em **Settings** → **Networking**
2. Clique em **"Generate Domain"**
3. Copie a URL gerada (ex: `https://seu-frontend.up.railway.app`)

---

## Passo 4: Atualizar CORS no Backend

Depois de gerar o domínio do frontend, atualize a variável `BACKEND_CORS_ORIGINS` no backend:

1. Vá no serviço do **backend** no Railway
2. **Settings** → **Variables**
3. Edite `BACKEND_CORS_ORIGINS`:
```json
["https://seu-frontend.up.railway.app","https://ai-assistante-company-production.up.railway.app"]
```

---

## Passo 5: Verificar Deploy

Após o deploy completar:

### 1. Testar Frontend
```
https://seu-frontend.up.railway.app
```

### 2. Verificar Logs
- Vá em **"Deployments"** → Clique no deploy → **"View Logs"**
- Verifique se não há erros

### 3. Testar Conexão com Backend
- Abra o frontend no navegador
- Abra o DevTools (F12) → Console
- Tente fazer login ou acessar qualquer página
- Verifique se as requisições para o backend estão funcionando

---

## Arquivos de Configuração

### Dockerfile ✅
```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### railway.toml ✅
```toml
[build]
builder = "dockerfile"
dockerfilePath = "Dockerfile"

[deploy]
healthcheckPath = "/"
healthcheckTimeout = 100
```

### nginx.conf ✅
Já configurado para SPA routing e cache de assets.

---

## Troubleshooting

### Erro: "Failed to fetch" ou CORS
- Verifique se `BACKEND_CORS_ORIGINS` no backend inclui a URL do frontend
- Certifique-se de que a URL está exata (com https://)

### Erro: API retorna 404
- Verifique se `VITE_API_URL` está correto
- Deve terminar com `/api/v1` (sem barra final)

### Build falhou
- Verifique os logs em **Deployments**
- Certifique-se de que `VITE_API_URL` está configurado como Build Variable

### Página em branco
- Abra DevTools → Console
- Verifique erros de JavaScript
- Verifique se o build foi feito corretamente

---

## Checklist de Deploy

- [ ] Repositório criado e código enviado
- [ ] Serviço criado no Railway
- [ ] `VITE_API_URL` configurado como Build Variable
- [ ] Deploy completou com sucesso
- [ ] Domínio público gerado
- [ ] CORS atualizado no backend
- [ ] Frontend acessível via navegador
- [ ] Login/Autenticação funcionando
- [ ] Requisições ao backend funcionando

---

## URLs Finais

**Backend:**
```
https://ai-assistante-company-production.up.railway.app
```

**Frontend:**
```
https://[SEU-DOMINIO].up.railway.app
```

**Webhook Twilio:**
```
https://ai-assistante-company-production.up.railway.app/api/v1/webhook/whatsapp
```
