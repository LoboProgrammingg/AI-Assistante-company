# 🧠 Sistema de Memória

## Visão Geral

O sistema de memória é crucial para que a IA seja personalizada para cada usuário. Cada usuário possui:

1. **Memória de Conversa** - Últimas N mensagens
2. **Preferências Aprendidas** - Padrões detectados
3. **Fatos Conhecidos** - Informações explícitas
4. **Histórico de Interações** - Estatísticas de uso

---

## Arquitetura de Memória

```
┌─────────────────────────────────────────────────────────────┐
│                      USER MEMORY                             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────┐  ┌─────────────────┐                   │
│  │   SHORT-TERM    │  │    LONG-TERM    │                   │
│  │     MEMORY      │  │     MEMORY      │                   │
│  ├─────────────────┤  ├─────────────────┤                   │
│  │ • Últimas 10    │  │ • Preferências  │                   │
│  │   mensagens     │  │ • Fatos         │                   │
│  │ • Contexto      │  │ • Padrões       │                   │
│  │   atual         │  │ • Estatísticas  │                   │
│  └────────┬────────┘  └────────┬────────┘                   │
│           │                    │                             │
│           ▼                    ▼                             │
│  ┌─────────────────────────────────────────┐                │
│  │           CONTEXT BUILDER               │                │
│  │  (Monta contexto para cada requisição)  │                │
│  └─────────────────────────────────────────┘                │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Estrutura de Dados da Memória

### 1. Conversation Memory (Banco de Dados)

```python
class ConversationMemory(Base):
    __tablename__ = "conversation_memory"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    key = Column(String(100))      # Tipo de memória
    value = Column(JSON)           # Dados
    context_window = Column(Integer, default=10)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    accessed_at = Column(DateTime)
```

### 2. Tipos de Memória (Keys)

| Key | Descrição | Exemplo |
|-----|-----------|---------|
| `preferences` | Preferências aprendidas | `{"default_time": "09:00"}` |
| `learned_facts` | Fatos sobre o usuário | `{"name": "João", "work": "developer"}` |
| `interaction_stats` | Estatísticas | `{"reminders_created": 15}` |
| `category_preferences` | Categorias mais usadas | `{"top": ["Transporte", "Alimentação"]}` |
| `communication_style` | Estilo de comunicação | `{"formality": "informal"}` |

---

## Preferências Aprendidas

### Detecção Automática

```python
class PreferenceLearner:
    """Aprende preferências do usuário automaticamente."""
    
    def analyze_reminders(self, user_id: int) -> Dict:
        """Analisa padrões em lembretes."""
        reminders = self.get_user_reminders(user_id)
        
        # Horário mais comum
        times = [r.scheduled_time.hour for r in reminders]
        most_common_hour = Counter(times).most_common(1)[0][0]
        
        # Tipo de recorrência mais usado
        recurrences = [r.recurrence_type for r in reminders]
        preferred_recurrence = Counter(recurrences).most_common(1)[0][0]
        
        return {
            "default_reminder_time": f"{most_common_hour:02d}:00",
            "preferred_recurrence": preferred_recurrence.value
        }
    
    def analyze_finances(self, user_id: int) -> Dict:
        """Analisa padrões financeiros."""
        transactions = self.get_user_transactions(user_id)
        
        # Categorias mais usadas
        categories = [t.category.name for t in transactions if t.category]
        top_categories = [c[0] for c in Counter(categories).most_common(5)]
        
        # Dia do mês com mais gastos
        days = [t.transaction_date.day for t in transactions]
        spending_peak_day = Counter(days).most_common(1)[0][0]
        
        return {
            "top_categories": top_categories,
            "spending_peak_day": spending_peak_day
        }
```

### Preferências Armazenadas

```json
{
    "preferences": {
        "default_reminder_time": "09:00",
        "remind_before_default": 60,
        "preferred_recurrence": "once",
        "notification_style": "detailed",
        "currency_format": "BRL",
        "week_start": "monday"
    }
}
```

---

## Fatos Aprendidos

### Extração de Fatos

```python
FACT_EXTRACTION_PROMPT = """
Analise a conversa e extraia fatos sobre o usuário.

Conversa:
{conversation}

Fatos já conhecidos:
{existing_facts}

Extraia NOVOS fatos relevantes como:
- Nome do usuário
- Profissão/trabalho
- Horários de rotina
- Preferências explícitas
- Compromissos recorrentes

Retorne JSON:
{
    "new_facts": {
        "key": "valor"
    },
    "updated_facts": {
        "key": "novo_valor"
    }
}

IMPORTANTE: Apenas fatos EXPLÍCITOS mencionados pelo usuário.
"""
```

### Exemplos de Fatos

```json
{
    "learned_facts": {
        "name": "João",
        "work_type": "desenvolvedor",
        "work_schedule": "9h às 18h",
        "gym_days": ["segunda", "quarta", "sexta"],
        "has_car": true,
        "favorite_food": "pizza",
        "partner_name": "Maria"
    }
}
```

---

## Contexto de Conversa

### Janela de Contexto

```python
def get_conversation_context(user_id: int, limit: int = 10) -> List[Dict]:
    """Recupera últimas mensagens para contexto."""
    
    messages = db.query(Message).filter(
        Message.user_id == user_id
    ).order_by(
        Message.created_at.desc()
    ).limit(limit).all()
    
    return [
        {
            "role": "user" if m.direction == "incoming" else "assistant",
            "content": m.content or m.audio_transcription,
            "intent": m.intent,
            "timestamp": m.created_at.isoformat()
        }
        for m in reversed(messages)
    ]
```

### Uso no Prompt

```python
def build_context_prompt(user_id: int) -> str:
    """Constrói prompt com contexto completo."""
    
    memory = MemoryService(db)
    
    context = memory.get_conversation_context(user_id)
    preferences = memory.get_user_preferences(user_id)
    facts = memory.get_learned_facts(user_id)
    
    return f"""
    CONTEXTO DO USUÁRIO:
    
    Nome: {facts.get('name', 'usuário')}
    Timezone: {preferences.get('timezone', 'America/Sao_Paulo')}
    
    Fatos conhecidos:
    {json.dumps(facts, ensure_ascii=False, indent=2)}
    
    Preferências:
    {json.dumps(preferences, ensure_ascii=False, indent=2)}
    
    Últimas mensagens:
    {format_conversation(context)}
    """
```

---

## Atualização de Memória

### Quando Atualizar

1. **Após cada interação** - Salvar mensagem
2. **Quando detectar novo fato** - Atualizar learned_facts
3. **Periodicamente** - Recalcular preferências
4. **Quando usuário explicitar** - "Meu nome é João"

### Fluxo de Atualização

```
Mensagem Processada
        │
        ▼
┌───────────────────┐
│  Salvar Message   │
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│ Extrair Fatos?    │──▶ Atualizar learned_facts
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│ Detectar Padrão?  │──▶ Atualizar preferences
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│ Atualizar Stats   │
└───────────────────┘
```

---

## Implementação do Memory Manager

```python
# app/ai/memory.py

class MemoryManager:
    """Gerenciador central de memória do usuário."""
    
    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self.service = MemoryService(db)
    
    def get_full_context(self) -> Dict[str, Any]:
        """Retorna contexto completo para o agente."""
        return {
            "conversation": self.service.get_conversation_context(self.user_id),
            "preferences": self.service.get_user_preferences(self.user_id),
            "facts": self.service.get_learned_facts(self.user_id),
            "stats": self._get_interaction_stats()
        }
    
    def _get_interaction_stats(self) -> Dict[str, int]:
        """Retorna estatísticas de interação."""
        return self.service.get_memory(self.user_id, "interaction_stats") or {
            "total_messages": 0,
            "reminders_created": 0,
            "transactions_logged": 0,
            "meetings_analyzed": 0
        }
    
    def update_after_action(self, action: str, entities: Dict) -> None:
        """Atualiza memória após uma ação."""
        stats = self._get_interaction_stats()
        
        if action == "create_reminder":
            stats["reminders_created"] = stats.get("reminders_created", 0) + 1
        elif action == "create_finance":
            stats["transactions_logged"] = stats.get("transactions_logged", 0) + 1
        elif action == "create_meeting":
            stats["meetings_analyzed"] = stats.get("meetings_analyzed", 0) + 1
        
        stats["total_messages"] = stats.get("total_messages", 0) + 1
        
        self.service.set_memory(self.user_id, "interaction_stats", stats)
    
    def learn_from_interaction(self, message: str, intent: str, entities: Dict) -> None:
        """Aprende com a interação."""
        # Detectar nome
        if "meu nome é" in message.lower():
            name = self._extract_name(message)
            if name:
                self.service.add_learned_fact(self.user_id, "name", name)
        
        # Detectar horários de preferência
        if intent == "reminder" and "scheduled_time" in entities:
            self._learn_time_preference(entities["scheduled_time"])
    
    def _extract_name(self, message: str) -> Optional[str]:
        """Extrai nome da mensagem."""
        patterns = [
            r"meu nome (?:é|e) (\w+)",
            r"pode me chamar de (\w+)",
            r"sou (?:o|a) (\w+)"
        ]
        for pattern in patterns:
            match = re.search(pattern, message.lower())
            if match:
                return match.group(1).capitalize()
        return None
```

---

## Redis para Cache de Contexto

```python
# app/utils/cache.py

import redis
import json
from app.config import settings

redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB
)

class ContextCache:
    """Cache de contexto em Redis para acesso rápido."""
    
    TTL = 3600  # 1 hora
    
    @staticmethod
    def get_context(user_id: int) -> Optional[Dict]:
        """Recupera contexto do cache."""
        key = f"context:{user_id}"
        data = redis_client.get(key)
        return json.loads(data) if data else None
    
    @staticmethod
    def set_context(user_id: int, context: Dict) -> None:
        """Armazena contexto no cache."""
        key = f"context:{user_id}"
        redis_client.setex(key, ContextCache.TTL, json.dumps(context))
    
    @staticmethod
    def invalidate(user_id: int) -> None:
        """Invalida cache do usuário."""
        key = f"context:{user_id}"
        redis_client.delete(key)
```
