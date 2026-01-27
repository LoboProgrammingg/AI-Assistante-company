# 🔌 Integrações Externas

## 1. Twilio (WhatsApp API)

### Configuração

```env
TWILIO_ACCOUNT_SID=ACxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxx
TWILIO_WHATSAPP_NUMBER=+14155238886
```

### Obter Credenciais

1. Criar conta: https://console.twilio.com/
2. Ativar WhatsApp Sandbox ou Business
3. Configurar webhook URL

### Webhook URL

```
POST https://seu-dominio.com/webhook/whatsapp
```

### Desenvolvimento Local (ngrok)

```bash
# Iniciar ngrok
ngrok http 8000

# Usar URL gerada no Twilio Console
# Ex: https://abc123.ngrok.io/webhook/whatsapp
```

### Implementação

```python
# app/services/whatsapp_service.py

from twilio.rest import Client

class WhatsAppService:
    def __init__(self, account_sid: str, auth_token: str, whatsapp_number: str):
        self.client = Client(account_sid, auth_token)
        self.from_number = f"whatsapp:{whatsapp_number}"
    
    def send_message(self, to_number: str, message: str) -> Dict:
        """Envia mensagem via WhatsApp."""
        try:
            msg = self.client.messages.create(
                from_=self.from_number,
                to=f"whatsapp:{to_number}",
                body=message
            )
            return {"success": True, "message_sid": msg.sid}
        except TwilioRestException as e:
            return {"success": False, "error": str(e)}
    
    async def download_audio(self, media_url: str, save_path: Path) -> Optional[Path]:
        """Baixa áudio do WhatsApp."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                media_url,
                auth=(self.client.username, self.client.password)
            )
            with open(save_path, "wb") as f:
                f.write(response.content)
            return save_path
```

---

## 2. Google Gemini AI

### Configuração

```env
GOOGLE_API_KEY=AIzaSyxxxxxxxxx
GEMINI_MODEL=gemini-2.5-flash
```

### Obter API Key

1. Acessar: https://makersuite.google.com/app/apikey
2. Criar nova API Key
3. Adicionar ao .env

### Uso com LangChain

```python
from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-pro",
    google_api_key=settings.GOOGLE_API_KEY,
    temperature=0.7,
    max_output_tokens=4000
)

response = llm.invoke("Sua mensagem aqui")
```

### Limites da API

| Modelo | RPM (Requests) | TPM (Tokens) |
|--------|----------------|--------------|
| gemini-2.5-flash | 60 | 1.000.000 |
| gemini-2.5-pro | 60 | 1.000.000 |

---

## 3. Google Speech-to-Text

### Configuração

```python
# Requer credenciais de serviço do Google Cloud
# ou usar API Key direta do Gemini para transcrição
```

### Implementação

```python
# app/utils/audio_processor.py

from google.cloud import speech
import io

class AudioProcessor:
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    async def transcribe_audio(self, audio_path: Path) -> str:
        """Transcreve áudio usando Google Speech-to-Text."""
        
        client = speech.SpeechClient()
        
        with open(audio_path, "rb") as f:
            content = f.read()
        
        audio = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.OGG_OPUS,
            sample_rate_hertz=16000,
            language_code="pt-BR",
            enable_automatic_punctuation=True
        )
        
        response = client.recognize(config=config, audio=audio)
        
        transcript = ""
        for result in response.results:
            transcript += result.alternatives[0].transcript + " "
        
        return transcript.strip()
```

### Alternativa: Usar Gemini para Transcrição

```python
async def transcribe_with_gemini(self, audio_path: Path) -> str:
    """Transcreve áudio usando Gemini (multimodal)."""
    
    import google.generativeai as genai
    
    genai.configure(api_key=self.api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")
    
    with open(audio_path, "rb") as f:
        audio_data = f.read()
    
    response = model.generate_content([
        "Transcreva este áudio em português:",
        {"mime_type": "audio/ogg", "data": audio_data}
    ])
    
    return response.text
```

---

## 4. PostgreSQL

### Configuração

```env
POSTGRES_SERVER=localhost
POSTGRES_USER=postgres
POSTGRES_PASSWORD=senha_segura
POSTGRES_DB=whatsapp_ai
POSTGRES_PORT=5432
```

### Conexão

```python
# app/database.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

---

## 5. Redis

### Configuração

```env
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

### Uso

```python
import redis
from app.config import settings

redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    decode_responses=True
)

# Cache de contexto
redis_client.setex(f"context:{user_id}", 3600, json.dumps(context))

# Rate limiting
redis_client.incr(f"rate:{user_id}")
redis_client.expire(f"rate:{user_id}", 60)
```

---

## 6. Diagrama de Integrações

```
┌─────────────────────────────────────────────────────────────┐
│                     WHATSAPP USER                            │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │    TWILIO    │ ◄─── WhatsApp Business API
                    └──────┬───────┘
                           │
                           ▼
              ┌────────────────────────┐
              │   FASTAPI BACKEND      │
              └───┬────────────────┬───┘
                  │                │
         ┌────────┴─────┐    ┌────┴────────┐
         ▼              ▼    ▼             ▼
   ┌──────────┐   ┌──────────┐   ┌──────────────┐
   │ POSTGRES │   │  REDIS   │   │    GEMINI    │
   │    DB    │   │  CACHE   │   │      AI      │
   └──────────┘   └──────────┘   └──────────────┘
                                        │
                                        ▼
                                 ┌──────────────┐
                                 │   GOOGLE     │
                                 │ SPEECH-TO-   │
                                 │    TEXT      │
                                 └──────────────┘
```

---

## 7. Variáveis de Ambiente Completas

```env
# API Settings
API_V1_STR=/api/v1
PROJECT_NAME=WhatsApp AI Assistant
DEBUG=True

# Database
POSTGRES_SERVER=localhost
POSTGRES_USER=postgres
POSTGRES_PASSWORD=senha_segura
POSTGRES_DB=whatsapp_ai
POSTGRES_PORT=5432

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Twilio
TWILIO_ACCOUNT_SID=ACxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxx
TWILIO_WHATSAPP_NUMBER=+14155238886
WHATSAPP_WEBHOOK_URL=https://seu-dominio.com/webhook/whatsapp

# Google Gemini
GOOGLE_API_KEY=AIzaSyxxxxxxxxx
GEMINI_MODEL=gemini-2.5-flash
GEMINI_TEMPERATURE=0.7
GEMINI_MAX_OUTPUT_TOKENS=4000

# JWT Security
SECRET_KEY=chave_super_secreta
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080

# CORS
BACKEND_CORS_ORIGINS=["http://localhost:3000"]

# Timezone
DEFAULT_TIMEZONE=America/Sao_Paulo

# Audio
MAX_AUDIO_SIZE_MB=25
SUPPORTED_AUDIO_FORMATS=[".mp3",".wav",".ogg",".m4a",".opus"]

# Scheduler
SCHEDULER_CHECK_INTERVAL_SECONDS=30
```
