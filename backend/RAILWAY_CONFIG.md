# Configuração Railway - Variáveis de Ambiente

## Variáveis Obrigatórias para as Novas Integrações

### 1. Tavily Web Search
```
TAVILY_API_KEY=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
```

### 2. Google Calendar OAuth (por Usuário)

Cada usuário conecta seu próprio calendário no dashboard. A IA acessa o calendário pessoal do usuário.

**Configuração no Google Cloud Console:**
1. Acesse: https://console.cloud.google.com/apis/credentials
2. Crie um "OAuth 2.0 Client ID" do tipo "Web application"
3. Adicione a URI de redirecionamento autorizada:
   - Production: `https://seu-backend.railway.app/api/v1/integrations/google-calendar/callback`
   - Local: `http://localhost:8005/api/v1/integrations/google-calendar/callback`

**Variáveis no Railway:**
```
GOOGLE_OAUTH_CLIENT_ID=seu_client_id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=seu_client_secret
BACKEND_URL=https://seu-backend.railway.app
FRONTEND_URL=https://seu-frontend.railway.app
```

### 3. SMTP (Email)
```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_SSL=false
SMTP_USER=seu_email@gmail.com
SMTP_PASSWORD=sua_app_password
SMTP_FROM_EMAIL=seu_email@gmail.com
SMTP_FROM_NAME=IRIS Assistant
```

**Nota:** Use "App Password" do Gmail, não a senha normal.

## Variáveis já configuradas (verificar se estão no Railway)

```
DATABASE_URL=<fornecido pelo Railway>
REDIS_URL=<fornecido pelo Railway>
GOOGLE_API_KEY=<sua chave Gemini>
SECRET_KEY=<sua chave secreta>
TWILIO_ACCOUNT_SID=<seu SID>
TWILIO_AUTH_TOKEN=<seu token>
TWILIO_WHATSAPP_NUMBER=<seu número>
```

## Novas Tools Disponíveis

### Tavily (Web Search)
- `_search_web`: Busca na internet
- `_search_news`: Busca notícias

### yFinance (Investimentos)
- `_get_stock_price`: Preço de ações (ex: PETR4.SA)
- `_get_stock_info`: Informações detalhadas
- `_get_crypto_price`: Preço de criptomoedas
- `_get_currency_rate`: Taxa de câmbio
- `_get_stock_history`: Histórico de preços

### Brasil API
- `_consultar_cep`: Endereço por CEP
- `_consultar_clima`: Previsão do tempo
- `_listar_feriados`: Feriados nacionais
- `_consultar_taxas`: Selic, CDI, IPCA
- `_listar_bancos` / `_consultar_banco`: Códigos bancários
- `_consultar_fipe`: Tabela FIPE

### Google Calendar
- `_listar_eventos`: Lista eventos
- `_criar_evento`: Cria evento com Meet
- `_verificar_disponibilidade`: Verifica horários livres
