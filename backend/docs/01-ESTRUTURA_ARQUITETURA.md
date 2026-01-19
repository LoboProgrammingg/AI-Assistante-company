# 🏗️ Estrutura e Arquitetura

## Arquitetura em Camadas

```
┌─────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Webhooks  │  │  REST API   │  │  WebSocket (futuro) │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
└─────────┼────────────────┼────────────────────┼─────────────┘
          │                │                    │
          ▼                ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                         │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              LangGraph Orchestrator                 │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐          │    │
│  │  │ Reminder │  │ Finance  │  │ Meeting  │          │    │
│  │  │  Agent   │  │  Agent   │  │  Agent   │          │    │
│  │  └──────────┘  └──────────┘  └──────────┘          │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                    SERVICES                          │   │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐       │   │
│  │  │  Reminder  │ │  Finance   │ │  Meeting   │       │   │
│  │  │  Service   │ │  Service   │ │  Service   │       │   │
│  │  └────────────┘ └────────────┘ └────────────┘       │   │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐       │   │
│  │  │  WhatsApp  │ │    AI      │ │   Memory   │       │   │
│  │  │  Service   │ │  Service   │ │  Service   │       │   │
│  │  └────────────┘ └────────────┘ └────────────┘       │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
          │                │                    │
          ▼                ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│                    DOMAIN LAYER                              │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐             │
│  │   Models   │  │  Schemas   │  │ Validators │             │
│  └────────────┘  └────────────┘  └────────────┘             │
└─────────────────────────────────────────────────────────────┘
          │                │                    │
          ▼                ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│                    INFRASTRUCTURE LAYER                      │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐             │
│  │ PostgreSQL │  │   Redis    │  │  External  │             │
│  │            │  │            │  │   APIs     │             │
│  └────────────┘  └────────────┘  └────────────┘             │
└─────────────────────────────────────────────────────────────┘
```

---

## Estrutura de Diretórios Detalhada

```
backend/
├── app/
│   ├── __init__.py
│   │
│   ├── ai/                          # Camada de IA
│   │   ├── __init__.py
│   │   ├── graph.py                 # ✅ Orquestrador LangGraph
│   │   ├── prompts.py               # 📝 Templates de prompts
│   │   ├── memory.py                # 📝 Gerenciador de memória
│   │   │
│   │   ├── agents/                  # Agentes especializados
│   │   │   ├── __init__.py
│   │   │   ├── base_agent.py        # 📝 Classe base
│   │   │   ├── reminder_agent.py    # 📝 Agente de lembretes
│   │   │   ├── finance_agent.py     # 📝 Agente financeiro
│   │   │   └── meeting_agent.py     # 📝 Agente de reuniões
│   │   │
│   │   └── tools/                   # Ferramentas dos agentes
│   │       ├── __init__.py
│   │       ├── reminder_tools.py    # 📝 Tools de lembrete
│   │       ├── finance_tools.py     # 📝 Tools financeiras
│   │       └── meeting_tools.py     # 📝 Tools de reunião
│   │
│   ├── api/                         # Endpoints REST
│   │   ├── __init__.py
│   │   ├── deps.py                  # 📝 Dependencies
│   │   ├── webhooks.py              # 📝 Webhooks WhatsApp
│   │   ├── users.py                 # 📝 CRUD usuários
│   │   ├── reminders.py             # 📝 CRUD lembretes
│   │   ├── finances.py              # 📝 CRUD finanças
│   │   └── meetings.py              # 📝 CRUD reuniões
│   │
│   ├── models/                      # SQLAlchemy Models
│   │   ├── __init__.py
│   │   ├── models.py                # ✅ Todos os modelos
│   │   ├── user.py                  # 📝 Refatorar
│   │   ├── message.py               # 📝 Refatorar
│   │   ├── reminder.py              # 📝 Refatorar
│   │   ├── finance.py               # 📝 Refatorar
│   │   └── meeting.py               # 📝 Refatorar
│   │
│   ├── schemas/                     # Pydantic Schemas
│   │   ├── __init__.py
│   │   ├── user.py                  # 📝 Schemas de usuário
│   │   ├── reminder.py              # 📝 Schemas de lembrete
│   │   ├── finance.py               # 📝 Schemas financeiros
│   │   └── meeting.py               # 📝 Schemas de reunião
│   │
│   ├── services/                    # Lógica de Negócio
│   │   ├── __init__.py
│   │   ├── whatsapp_service.py      # ✅ Comunicação WhatsApp
│   │   ├── ai_service.py            # 📝 Orquestração IA
│   │   ├── reminder_service.py      # 📝 Lógica de lembretes
│   │   ├── finance_service.py       # 📝 Lógica financeira
│   │   ├── meeting_service.py       # 📝 Lógica de reuniões
│   │   └── memory_service.py        # 📝 Gerenciamento memória
│   │
│   ├── utils/                       # Utilitários
│   │   ├── __init__.py
│   │   ├── audio_processor.py       # 📝 Transcrição de áudio
│   │   ├── timezone_helper.py       # 📝 Conversão de timezones
│   │   └── validators.py            # 📝 Validadores
│   │
│   ├── workers/                     # Background Workers
│   │   ├── __init__.py
│   │   └── scheduler.py             # ✅ Scheduler de lembretes
│   │
│   ├── config.py                    # ✅ Configurações
│   ├── database.py                  # 📝 Conexão com banco
│   └── main.py                      # ✅ Entry point
│
├── alembic/                         # Migrations
│   ├── versions/
│   └── alembic.ini
│
├── docs/                            # Documentação
│   ├── 00-VISAO_GERAL.md
│   ├── 01-ESTRUTURA_ARQUITETURA.md
│   └── ...
│
├── tests/                           # Testes
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_agents/
│   ├── test_services/
│   └── test_api/
│
├── .env.example
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

**Legenda:**
- ✅ Implementado
- 📝 Pendente

---

## Padrões de Projeto Utilizados

### 1. Repository Pattern
Abstração do acesso a dados através dos Services.

```python
class ReminderService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_user(self, user_id: int) -> List[Reminder]:
        return self.db.query(Reminder).filter(...).all()
```

### 2. Factory Pattern
Criação de agentes especializados.

```python
class AgentFactory:
    @staticmethod
    def create(intent: str) -> BaseAgent:
        agents = {
            "reminder": ReminderAgent,
            "finance": FinanceAgent,
            "meeting": MeetingAgent,
        }
        return agents.get(intent, GeneralAgent)()
```

### 3. Strategy Pattern
Handlers diferentes baseados na intenção.

```python
class IntentHandler:
    def __init__(self, strategy: BaseStrategy):
        self.strategy = strategy
    
    def execute(self, data: dict):
        return self.strategy.process(data)
```

### 4. Observer Pattern
Notificações e eventos do scheduler.

```python
class ReminderObserver:
    def on_reminder_due(self, reminder: Reminder):
        self.notify_user(reminder)
```

---

## Fluxo de Mensagem Detalhado

```
1. RECEBIMENTO
   │
   ├─▶ Twilio Webhook POST /webhook/whatsapp
   │   └─▶ Parse form data
   │       └─▶ Extract: from, body, media_url, etc.
   │
2. IDENTIFICAÇÃO DO USUÁRIO
   │
   ├─▶ get_or_create_user(phone_number)
   │   ├─▶ Busca usuário existente
   │   └─▶ Cria novo com session_id único
   │
3. PROCESSAMENTO EM BACKGROUND
   │
   ├─▶ BackgroundTask: process_incoming_message()
   │   │
   │   ├─▶ [Se áudio] Download e Transcrição
   │   │
   │   ├─▶ Salvar Message no banco
   │   │
   │   └─▶ AI Processing
   │       │
   │       ├─▶ Intent Classifier
   │       │   └─▶ Determina: reminder | finance | meeting | general
   │       │
   │       ├─▶ Route para Agent específico
   │       │   ├─▶ ReminderAgent.extract_entities()
   │       │   ├─▶ FinanceAgent.extract_entities()
   │       │   └─▶ MeetingAgent.analyze()
   │       │
   │       └─▶ Response Generator
   │           └─▶ Gera resposta em português
   │
4. EXECUÇÃO DA AÇÃO
   │
   ├─▶ [reminder] ReminderService.create()
   ├─▶ [finance] FinanceService.create()
   └─▶ [meeting] MeetingService.create()
   │
5. RESPOSTA
   │
   └─▶ WhatsAppService.send_message()
       └─▶ Twilio API → User
```

---

## Configuração de Ambiente

### Variáveis Obrigatórias

```env
# Database
POSTGRES_SERVER=localhost
POSTGRES_USER=postgres
POSTGRES_PASSWORD=senha_segura
POSTGRES_DB=whatsapp_ai
POSTGRES_PORT=5432

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# WhatsApp/Twilio
TWILIO_ACCOUNT_SID=ACxxxxxxxxx
TWILIO_AUTH_TOKEN=token_aqui
TWILIO_WHATSAPP_NUMBER=+14155238886

# Google Gemini
GOOGLE_API_KEY=AIzaSyxxxxxxx
GEMINI_MODEL=gemini-2.5-flash

# Security
SECRET_KEY=chave_super_secreta
```

---

## Convenções de Código

### Nomenclatura
- **Classes**: PascalCase (`ReminderService`)
- **Funções/Métodos**: snake_case (`create_reminder`)
- **Constantes**: UPPER_SNAKE_CASE (`MAX_RETRIES`)
- **Arquivos**: snake_case (`reminder_service.py`)

### Estrutura de Arquivos
```python
# 1. Imports padrão
from datetime import datetime
from typing import List, Optional

# 2. Imports de terceiros
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

# 3. Imports locais
from app.models import Reminder
from app.schemas import ReminderCreate

# 4. Constantes
DEFAULT_LIMIT = 100

# 5. Classes/Funções
class ReminderService:
    ...
```

### Documentação
```python
def create_reminder(
    self,
    user_id: int,
    data: ReminderCreate
) -> Reminder:
    """
    Cria um novo lembrete para o usuário.
    
    Args:
        user_id: ID do usuário
        data: Dados do lembrete
        
    Returns:
        Reminder: Lembrete criado
        
    Raises:
        ValueError: Se dados inválidos
    """
```
