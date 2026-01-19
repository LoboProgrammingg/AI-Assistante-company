# 🚀 Guia de Implementação

## Status Atual do Projeto

### ✅ Implementado
| Arquivo | Descrição | Status |
|---------|-----------|--------|
| `app/main.py` | Entry point FastAPI | ✅ Completo |
| `app/config.py` | Configurações | ✅ Completo |
| `app/models/models.py` | Todos os models | ✅ Completo |
| `app/ai/graph.py` | LangGraph básico | ✅ Funcional |
| `app/services/whatsapp_service.py` | Serviço WhatsApp | ✅ Completo |
| `app/workers/scheduler.py` | Scheduler lembretes | ✅ Funcional |

### ⏳ Pendente
| Arquivo | Descrição | Prioridade |
|---------|-----------|------------|
| `app/database.py` | Conexão DB | 🔴 Alta |
| `app/services/reminder_service.py` | Lógica lembretes | 🔴 Alta |
| `app/services/finance_service.py` | Lógica finanças | 🔴 Alta |
| `app/services/meeting_service.py` | Lógica reuniões | 🔴 Alta |
| `app/utils/audio_processor.py` | Transcrição | 🔴 Alta |
| `app/schemas/*.py` | Todos schemas | 🟡 Média |
| `app/api/*.py` | Endpoints REST | 🟡 Média |
| `app/ai/agents/*.py` | Agentes especializados | 🟡 Média |
| `app/ai/tools/*.py` | Tools dos agentes | 🟡 Média |
| `app/services/memory_service.py` | Memória | 🟡 Média |
| `app/utils/timezone_helper.py` | Timezone | 🟢 Baixa |

---

## Ordem de Implementação

### Fase 1: Infraestrutura Base (Prioridade Alta)

```
1.1 → app/database.py
1.2 → app/schemas/user.py
1.3 → app/schemas/reminder.py
1.4 → app/schemas/finance.py
1.5 → app/schemas/meeting.py
```

### Fase 2: Services Core (Prioridade Alta)

```
2.1 → app/services/reminder_service.py
2.2 → app/services/finance_service.py
2.3 → app/services/meeting_service.py
2.4 → app/utils/audio_processor.py
2.5 → app/utils/timezone_helper.py
```

### Fase 3: API REST (Prioridade Média)

```
3.1 → app/api/deps.py (dependencies)
3.2 → app/api/users.py
3.3 → app/api/reminders.py
3.4 → app/api/finances.py
3.5 → app/api/meetings.py
3.6 → Registrar routers no main.py
```

### Fase 4: Agentes Especializados (Prioridade Média)

```
4.1 → app/ai/agents/base_agent.py
4.2 → app/ai/agents/reminder_agent.py
4.3 → app/ai/agents/finance_agent.py
4.4 → app/ai/agents/meeting_agent.py
4.5 → app/ai/tools/reminder_tools.py
4.6 → app/ai/tools/finance_tools.py
4.7 → app/ai/tools/meeting_tools.py
4.8 → Refatorar app/ai/graph.py para usar agentes
```

### Fase 5: Sistema de Memória (Prioridade Média)

```
5.1 → app/services/memory_service.py
5.2 → app/ai/memory.py
5.3 → Integrar memória no graph.py
```

### Fase 6: Testes (Prioridade Alta após cada fase)

```
6.1 → tests/conftest.py
6.2 → tests/test_services/
6.3 → tests/test_api/
6.4 → tests/test_agents/
```

---

## Detalhamento por Fase

### Fase 1.1: database.py

```python
# app/database.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### Fase 2.1: reminder_service.py

Ver documento `05-SERVICES.md` para implementação completa.

**Métodos necessários:**
- `create(user_id, data)` → Criar lembrete
- `create_from_entities(user_id, entities)` → Criar via IA
- `get_by_id(reminder_id, user_id)` → Buscar por ID
- `list_by_user(user_id, status, limit)` → Listar
- `update(reminder_id, user_id, data)` → Atualizar
- `delete(reminder_id, user_id)` → Remover
- `complete(reminder_id, user_id)` → Marcar concluído
- `get_upcoming(user_id, hours)` → Próximos lembretes

### Fase 2.4: audio_processor.py

```python
# app/utils/audio_processor.py

from pathlib import Path
from typing import Optional
import google.generativeai as genai
from app.config import settings

class AudioProcessor:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)
    
    async def transcribe_audio(self, audio_path: Path) -> Optional[str]:
        """Transcreve áudio usando Gemini."""
        try:
            with open(audio_path, "rb") as f:
                audio_data = f.read()
            
            response = self.model.generate_content([
                "Transcreva este áudio em português brasileiro. "
                "Retorne apenas a transcrição, sem comentários:",
                {"mime_type": "audio/ogg", "data": audio_data}
            ])
            
            return response.text.strip()
        except Exception as e:
            logger.error(f"Erro na transcrição: {e}")
            return None
    
    def validate_audio(self, audio_path: Path) -> bool:
        """Valida formato e tamanho do áudio."""
        if not audio_path.exists():
            return False
        
        # Verificar extensão
        if audio_path.suffix.lower() not in settings.SUPPORTED_AUDIO_FORMATS:
            return False
        
        # Verificar tamanho (MB)
        size_mb = audio_path.stat().st_size / (1024 * 1024)
        if size_mb > settings.MAX_AUDIO_SIZE_MB:
            return False
        
        return True
```

### Fase 3.1: deps.py

```python
# app/api/deps.py

from typing import Generator
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from app.database import get_db
from app.config import settings
from app.models import User

security = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Obtém usuário atual do token JWT."""
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        user_id: int = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Token inválido")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    return user
```

---

## Checklist de Implementação

### Fase 1: Infraestrutura
- [ ] Criar `app/database.py`
- [ ] Criar `app/schemas/user.py`
- [ ] Criar `app/schemas/reminder.py`
- [ ] Criar `app/schemas/finance.py`
- [ ] Criar `app/schemas/meeting.py`
- [ ] Atualizar `app/models/__init__.py` com exports

### Fase 2: Services
- [ ] Criar `app/services/reminder_service.py`
- [ ] Criar `app/services/finance_service.py`
- [ ] Criar `app/services/meeting_service.py`
- [ ] Criar `app/utils/audio_processor.py`
- [ ] Criar `app/utils/timezone_helper.py`
- [ ] Testar services isoladamente

### Fase 3: API REST
- [ ] Criar `app/api/deps.py`
- [ ] Criar `app/api/users.py`
- [ ] Criar `app/api/reminders.py`
- [ ] Criar `app/api/finances.py`
- [ ] Criar `app/api/meetings.py`
- [ ] Registrar routers no `main.py`
- [ ] Testar endpoints via Swagger

### Fase 4: Agentes
- [ ] Criar `app/ai/agents/base_agent.py`
- [ ] Criar `app/ai/agents/reminder_agent.py`
- [ ] Criar `app/ai/agents/finance_agent.py`
- [ ] Criar `app/ai/agents/meeting_agent.py`
- [ ] Criar `app/ai/tools/reminder_tools.py`
- [ ] Criar `app/ai/tools/finance_tools.py`
- [ ] Criar `app/ai/tools/meeting_tools.py`
- [ ] Refatorar `app/ai/graph.py`
- [ ] Testar fluxo completo com IA

### Fase 5: Memória
- [ ] Criar `app/services/memory_service.py`
- [ ] Criar `app/ai/memory.py`
- [ ] Integrar memória no graph
- [ ] Testar persistência de contexto

### Fase 6: Testes
- [ ] Setup pytest em `tests/conftest.py`
- [ ] Testes de services
- [ ] Testes de API
- [ ] Testes de agentes
- [ ] Coverage > 80%

---

## Comandos Úteis

```bash
# Iniciar ambiente
cd backend
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Iniciar banco de dados
docker-compose up -d postgres redis

# Rodar migrations
alembic upgrade head

# Iniciar servidor dev
uvicorn app.main:app --reload --port 8005

# Iniciar scheduler (outro terminal)
python -m app.workers.scheduler

# Rodar testes
pytest tests/ -v

# Verificar coverage
pytest tests/ -v --cov=app --cov-report=html
```

---

## Próximos Passos Imediatos

1. **Criar `app/database.py`** - Necessário para services
2. **Criar schemas** - Validação de dados
3. **Implementar services** - Lógica de negócio
4. **Testar fluxo completo** - WhatsApp → IA → DB → Resposta

---

## Notas Importantes

1. **Não modificar estrutura existente** sem necessidade
2. **Seguir padrões estabelecidos** nos arquivos já implementados
3. **Manter arquivos < 300 linhas** - refatorar quando necessário
4. **Testes a cada fase** - não acumular débito técnico
5. **Commits semânticos** - feat:, fix:, refactor:, docs:
