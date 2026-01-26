# IRIS Graph v3 - Documentação Completa

**Versão:** 3.0.0  
**Data:** Janeiro 2026  
**Status:** Produção  
**Padrão:** Ativo (`IRIS_GRAPH_VERSION=v3`)

---

## Sumário Executivo

O **IRIS Graph v3** é uma arquitetura de IA conversacional enterprise-grade construída com LangGraph, projetada para gerenciar aspectos críticos da vida do usuário (finanças, tarefas, lembretes, decisões) com máxima confiabilidade, segurança e performance.

### Características Principais

- **8 Agentes Especializados** com isolamento de ferramentas
- **Sistema de Memória em 4 Camadas** (sessão, trabalho, longo prazo, episódica)
- **Confidence Scoring** para decisões seguras
- **16 Intents** suportados
- **22 Ações** mapeadas
- **Fluxo de 6 Nós** otimizado

---

## 1. Arquitetura Geral

### 1.1 Diagrama do Fluxo

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           IRIS GRAPH v3                                      │
│                                                                              │
│   USER INPUT                                                                 │
│       │                                                                      │
│       ▼                                                                      │
│   ┌──────────────────┐                                                       │
│   │  1. COGNITIVE    │ ◄─── Gemini Flash (rápido)                            │
│   │     NODE         │      Classifica intent + extrai entidades             │
│   └────────┬─────────┘                                                       │
│            │                                                                 │
│       ┌────┴────┐                                                            │
│       ▼         ▼                                                            │
│  [direct]   [action]                                                         │
│       │         │                                                            │
│       │    ┌────▼────────────┐                                               │
│       │    │  2. MEMORY      │ ◄─── Sem LLM (determinístico)                 │
│       │    │     READER      │      Busca memórias relevantes                │
│       │    └────────┬────────┘                                               │
│       │             │                                                        │
│       │    ┌────────▼────────┐                                               │
│       │    │  3. CONTEXT     │ ◄─── Sem LLM (determinístico)                 │
│       │    │     BUILDER     │      Comprime contexto (máx 500 tokens)       │
│       │    └────────┬────────┘                                               │
│       │             │                                                        │
│       │    ┌────────▼────────┐                                               │
│       │    │  4. EXECUTOR    │ ◄─── Sem LLM (execução direta)                │
│       │    │     NODE        │      Despacha para agentes/executores         │
│       │    └────────┬────────┘                                               │
│       │             │                                                        │
│       │    ┌────────▼────────┐                                               │
│       │    │  5. MEMORY      │ ◄─── Sem LLM (regras determinísticas)         │
│       │    │     WRITER      │      Persiste memórias relevantes             │
│       │    └────────┬────────┘                                               │
│       │             │                                                        │
│       └─────┬───────┘                                                        │
│             ▼                                                                │
│   ┌──────────────────┐                                                       │
│   │  6. RESPONDER    │ ◄─── Gemini Pro (quando necessário)                   │
│   │     NODE         │      Gera respostas complexas                         │
│   └────────┬─────────┘                                                       │
│            │                                                                 │
│       ┌────▼────┐                                                            │
│       │ FINALIZE│                                                            │
│       └────┬────┘                                                            │
│            │                                                                 │
│            ▼                                                                 │
│       RESPONSE                                                               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Estrutura de Diretórios

```
app/ai/
├── graph_v3/                          # Grafo principal
│   ├── __init__.py                    # Exports
│   ├── core.py                        # IRISGraphV3 (classe principal)
│   ├── migration.py                   # Alterna v2 ↔ v3
│   │
│   ├── state/                         # Estado do grafo
│   │   ├── __init__.py
│   │   └── types.py                   # IRISStateV3, ExtractedAction
│   │
│   ├── nodes/                         # Nós de processamento
│   │   ├── __init__.py
│   │   ├── cognitive.py               # CognitiveNode (classificação)
│   │   └── responder.py               # ResponderNode (geração)
│   │
│   ├── executors/                     # Executores de ações
│   │   ├── __init__.py
│   │   ├── executor.py                # ExecutorNode (orquestrador)
│   │   ├── specialized.py             # SpecializedExecutor (agentes)
│   │   ├── finance.py                 # FinanceExecutor
│   │   ├── reminder.py                # ReminderExecutor
│   │   ├── calendar.py                # CalendarExecutor
│   │   ├── contact.py                 # ContactExecutor
│   │   ├── meeting.py                 # MeetingExecutor
│   │   ├── message.py                 # MessageExecutor
│   │   ├── todoist.py                 # TodoistExecutor
│   │   └── integrations.py            # IntegrationsExecutor
│   │
│   └── templates/                     # Templates de resposta
│       ├── __init__.py
│       └── responses.py               # ResponseTemplates
│
├── memory/                            # Sistema de memória
│   ├── __init__.py
│   ├── MEMORY_ARCHITECTURE.md         # Documentação da arquitetura
│   ├── types.py                       # MemoryItem, MemoryType, etc
│   ├── reader.py                      # MemoryReaderNode
│   ├── writer.py                      # MemoryWriterNode
│   ├── context_builder.py             # WorkingContextBuilder
│   └── redis_working.py               # RedisWorkingMemory
│
├── memory_legacy.py                   # MemoryManager (compatibilidade)
│
├── jobs/                              # Jobs de manutenção
│   ├── __init__.py
│   └── memory_decay.py                # Decay, Expiration, Cleanup
│
└── agents/                            # Agentes especializados
    ├── __init__.py
    ├── ARCHITECTURE.md                # Documentação dos agentes
    ├── base.py                        # SpecializedAgent (base)
    ├── registry.py                    # AgentRegistry
    ├── dispatcher.py                  # Dispatcher para agentes
    │
    ├── bills/                         # 🧾 Agente de Faturas
    │   ├── __init__.py
    │   ├── agent.py                   # BillsAgent
    │   └── tools.py                   # extract_invoice_data, etc
    │
    ├── memory/                        # 🧠 Agente de Memória
    │   ├── __init__.py
    │   └── agent.py                   # MemoryAgent
    │
    ├── patterns/                      # 🔮 Agente de Padrões
    │   ├── __init__.py
    │   └── agent.py                   # PatternsAgent
    │
    ├── goals/                         # 🧭 Agente de Metas
    │   ├── __init__.py
    │   └── agent.py                   # GoalsAgent
    │
    ├── subscriptions/                 # 🛒 Agente de Assinaturas
    │   ├── __init__.py
    │   └── agent.py                   # SubscriptionsAgent
    │
    ├── advisor/                       # 🧠 Agente Consultor
    │   ├── __init__.py
    │   └── agent.py                   # AdvisorAgent
    │
    ├── health/                        # 🏥 Agente de Saúde
    │   ├── __init__.py
    │   └── agent.py                   # HealthAgent
    │
    └── confidence/                    # 📊 Confidence Scoring
        ├── __init__.py
        └── scorer.py                  # ConfidenceScorer
```

---

## 2. Sistema de Memória

### 2.1 Arquitetura em 4 Camadas

| Camada | Storage | TTL | Função |
|--------|---------|-----|--------|
| **Sessão** | State (RAM) | Conversa atual | Contexto imediato |
| **Trabalho** | Redis | 24 horas | Contexto ativo |
| **Longo Prazo** | PostgreSQL | Indefinido | Preferências, hábitos |
| **Episódica** | PostgreSQL | 90-365 dias | Eventos, decisões |

### 2.2 Estrutura de Dados

```python
@dataclass
class MemoryItem:
    memory_id: str           # UUID único
    user_id: int             # Isolamento por usuário
    memory_type: MemoryType  # preference | habit | constraint | etc
    layer: MemoryLayer       # session | working | longterm | episodic
    category: str            # finance | health | work | personal
    key: str                 # Chave semântica
    value: Any               # Valor estruturado
    summary: str             # Resumo legível (máx 100 chars)
    confidence: float        # 0.0 - 1.0
    importance: Importance   # low | medium | high | critical
    source: MemorySource     # user_explicit | user_implicit | inference
    created_at: datetime
    updated_at: datetime
    last_accessed: datetime
    access_count: int
    expires_at: Optional[datetime]
```

### 2.3 Tipos de Memória

| Tipo | Descrição | Exemplo |
|------|-----------|---------|
| `PREFERENCE` | Preferências do usuário | "Prefiro ser chamado de João" |
| `HABIT` | Hábitos recorrentes | "Sempre pago contas dia 5" |
| `RECURRENCE` | Eventos recorrentes | "Academia segundas e quartas" |
| `CONSTRAINT` | Restrições/limitações | "Alérgico a frutos do mar" |
| `IDENTITY` | Dados de identidade | "Trabalho como engenheiro" |
| `EVENT` | Eventos passados | "Viajou para SP em janeiro" |
| `DECISION` | Decisões tomadas | "Decidiu investir em X" |
| `ACTION` | Ações executadas | "Criou lembrete para Y" |

### 2.4 Fluxo de Memória

```
┌────────────────┐    ┌────────────────┐    ┌────────────────┐
│ MEMORY READER  │───▶│ CONTEXT BUILDER│───▶│   EXECUTOR     │
│                │    │                │    │                │
│ - Busca por    │    │ - Comprime     │    │ - Usa contexto │
│   user_id      │    │   máx 500 tok  │    │   nas decisões │
│ - Filtra tipo  │    │ - Prioriza     │    │                │
│ - Filtra conf. │    │   constraints  │    │                │
│ - Máx 10 itens │    │ - Formata      │    │                │
└────────────────┘    └────────────────┘    └────────────────┘
                                                    │
                                                    ▼
                                           ┌────────────────┐
                                           │ MEMORY WRITER  │
                                           │                │
                                           │ - Detecta se   │
                                           │   deve salvar  │
                                           │ - Classifica   │
                                           │   tipo         │
                                           │ - Define conf. │
                                           │ - Persiste     │
                                           └────────────────┘
```

### 2.5 Regras de Escrita

**O que SALVAR:**
- ✅ Preferências explícitas ("gosto de X")
- ✅ Hábitos recorrentes (3+ menções)
- ✅ Restrições ("alérgico a X")
- ✅ Informações de identidade
- ✅ Decisões importantes executadas

**O que NÃO SALVAR:**
- ❌ Emoções momentâneas ("estou triste")
- ❌ Opiniões vagas ("acho que talvez")
- ❌ Ruído conversacional ("ok", "beleza")
- ❌ Dados sensíveis sem confirmação

---

## 3. Agentes Especializados

### 3.1 Visão Geral

| Agente | Intents | Descrição |
|--------|---------|-----------|
| 🧾 **Bills** | bills, fatura, boleto | OCR + extração de faturas |
| 🧠 **Memory** | memory, preference | Preferências e memórias |
| 🔮 **Patterns** | patterns, analise | Detecção de anomalias |
| 🧭 **Goals** | goals, meta, economizar | Metas financeiras |
| 🛒 **Subscriptions** | subscriptions, assinatura | Cobranças recorrentes |
| 🧠 **Advisor** | advisor, simular | Simulações e projeções |
| 🏥 **Health** | health, remédio | Lembretes de saúde |
| 📊 **Confidence** | (transversal) | Scoring de segurança |

### 3.2 Isolamento de Ferramentas

Cada agente tem acesso APENAS às suas ferramentas:

```python
# BillsAgent - Ferramentas permitidas
BILLS_TOOLS = [
    "extract_invoice_data",
    "create_financial_reminder",
    "list_pending_bills",
]

# MemoryAgent - Ferramentas permitidas
MEMORY_TOOLS = [
    "write_memory",
    "read_memory",
    "update_memory",
    "delete_memory",
]

# NUNCA compartilhar ferramentas entre agentes
```

### 3.3 Confidence Scoring

```python
# Regras de decisão baseadas em confiança
if confidence >= 0.9:
    # Auto-execução permitida
    execute_action()
elif confidence >= 0.5:
    # Requer confirmação do usuário
    request_confirmation()
else:
    # Apenas sugestão
    suggest_action()
```

### 3.4 Dispatcher de Agentes

```python
SPECIALIZED_INTENTS = {
    # Bills Agent
    "bills": "bills",
    "fatura": "bills",
    "boleto": "bills",
    
    # Memory Agent
    "memory": "memory",
    "preference": "memory",
    
    # Patterns Agent
    "patterns": "patterns",
    "analise": "patterns",
    
    # Goals Agent
    "goals": "goals",
    "meta": "goals",
    "economizar": "goals",
    
    # Subscriptions Agent
    "subscriptions": "subscriptions",
    "assinatura": "subscriptions",
    
    # Advisor Agent
    "advisor": "advisor",
    "simular": "advisor",
    
    # Health Agent
    "health": "health",
    "remédio": "health",
}
```

---

## 4. Nós do LangGraph

### 4.1 CognitiveNode

**Responsabilidade:** Classificar intent, extrair entidades, decidir ação.

**LLM:** Gemini Flash (rápido, barato)

**Intents Suportados (16):**
- finance, reminder, meeting, contact, message
- todoist, search, transcription
- bills, memory, patterns, goals
- subscriptions, advisor, health, general

**Ações Suportadas (22):**
- Finanças: create_finance, query_finance, delete_finance, update_finance
- Lembretes: create_reminder, list_reminders, delete_reminder, update_reminder
- Agenda: create_event, list_events, check_availability
- Contatos: create_contact, list_contacts, delete_contact, update_contact
- Mensagens: schedule_message, list_scheduled_messages
- Todoist: create_todoist_task, list_todoist_tasks, complete_todoist_task, etc
- Agentes: extract_invoice, save_preference, analyze_patterns, etc

### 4.2 MemoryReaderNode

**Responsabilidade:** Buscar memórias relevantes para o contexto atual.

**LLM:** Nenhum (100% determinístico)

**Regras:**
- Sempre filtra por `user_id` (isolamento)
- Máximo 10 memórias por query
- Filtra por tipo, confiança, recência
- NUNCA inventa memória

### 4.3 WorkingContextBuilder

**Responsabilidade:** Comprimir memórias em contexto otimizado.

**LLM:** Nenhum (100% determinístico)

**Regras:**
- Máximo 500 tokens de contexto
- Constraints (⚠️) sempre incluídos primeiro
- Campos de auditoria NUNCA incluídos

### 4.4 ExecutorNode

**Responsabilidade:** Despachar ações para executores/agentes.

**LLM:** Nenhum (execução direta)

**Executores:**
- FinanceExecutor, ReminderExecutor, CalendarExecutor
- ContactExecutor, MeetingExecutor, MessageExecutor
- TodoistExecutor, IntegrationsExecutor
- SpecializedExecutor (para agentes)

### 4.5 MemoryWriterNode

**Responsabilidade:** Persistir memórias relevantes.

**LLM:** Nenhum (regras determinísticas)

**Regras:**
- Detecta padrões de preferência/hábito via regex
- Descarta ruído e emoções momentâneas
- Dados sensíveis requerem confirmação
- Auditoria completa de todas as operações

### 4.6 ResponderNode

**Responsabilidade:** Gerar respostas complexas quando necessário.

**LLM:** Gemini Pro (poderoso)

**Quando é usado:**
- Perguntas complexas que precisam de elaboração
- Respostas que precisam de contexto de memória
- Quando não há template de resposta disponível

---

## 5. Configuração e Deploy

### 5.1 Variáveis de Ambiente

```bash
# Versão do grafo
IRIS_GRAPH_VERSION=v3

# APIs
GOOGLE_API_KEY=your_key
GEMINI_MODEL=gemini-1.5-pro

# Database
DATABASE_URL=postgresql://...

# Redis (para working memory)
REDIS_URL=redis://...
```

### 5.2 Migração v2 → v3

```python
# app/ai/graph_v3/migration.py

async def process_message(
    user_id: int,
    session_id: str,
    message: str,
    context: dict = None,
    db: Optional[Session] = None,
) -> dict:
    """
    Processa mensagem usando a versão configurada.
    Env: IRIS_GRAPH_VERSION = "v2" | "v3"
    """
    if GRAPH_VERSION == "v3":
        return await _process_v3(user_id, session_id, message, context, db)
    else:
        return await _process_v2(user_id, session_id, message, context, db)
```

### 5.3 Endpoints

```python
# /api/chat.py - POST /message
from app.ai.graph_v3.migration import process_message

result = await process_message(
    user_id=current_user.id,
    session_id=current_user.session_id,
    message=data.message,
    context={"user_name": current_user.name},
    db=db,
)

# /api/webhooks.py - WhatsApp webhook
from app.ai.graph_v3.migration import process_message

result = await process_message(
    user_id=user.id,
    session_id=session_id,
    message=message_text,
    db=db,
)
```

---

## 6. Segurança e Privacidade

### 6.1 Isolamento por Usuário

```python
# TODAS as queries DEVEM incluir user_id
class MemoryRepository:
    async def get_memories(
        self,
        user_id: int,  # OBRIGATÓRIO
        **filters,
    ) -> List[MemoryItem]:
        query = select(Memory).where(Memory.user_id == user_id)
        # ...
```

### 6.2 LGPD Compliance

```python
# Exclusão seletiva de memória
async def delete_user_memory(
    user_id: int,
    memory_id: str = None,
    delete_all: bool = False,
):
    # 1. Criar log de auditoria ANTES de deletar
    audit_log = AuditLog(
        user_id=user_id,
        action="memory_delete",
        data_snapshot=memory_to_dict(memory),
    )
    
    # 2. Deletar
    await db.delete(memory)
```

### 6.3 Dados Sensíveis

```python
# Padrões que requerem confirmação
SENSITIVE_PATTERNS = [
    r"(?:cpf|rg|identidade|cnh)",
    r"(?:senha|password|pin)",
    r"(?:cartão|conta bancária)",
    r"(?:doença|diagnóstico|medicamento)",
    r"(?:salário|renda)",
]
```

---

## 7. Performance

### 7.1 Métricas Alvo

| Métrica | Alvo | Crítico |
|---------|------|---------|
| Latência (p50) | < 500ms | < 1s |
| Latência (p95) | < 1s | < 2s |
| Memórias por usuário | < 500 | < 1000 |
| Contexto para LLM | < 500 tokens | < 1000 |
| Cache hit ratio | > 80% | > 60% |

### 7.2 Índices de Banco

```sql
-- Índice principal para busca por usuário
CREATE INDEX idx_memory_user_type 
ON memories(user_id, memory_type, confidence DESC);

-- Índice para decay/cleanup
CREATE INDEX idx_memory_last_accessed 
ON memories(last_accessed, confidence);

-- Índice para expiração
CREATE INDEX idx_memory_expires 
ON memories(expires_at) WHERE expires_at IS NOT NULL;
```

### 7.3 Limites por Tipo

```python
MEMORY_LIMITS = {
    MemoryType.PREFERENCE: 50,
    MemoryType.HABIT: 30,
    MemoryType.CONSTRAINT: 20,
    MemoryType.IDENTITY: 10,
    MemoryType.RECURRENCE: 30,
    MemoryType.EVENT: 100,
    MemoryType.ACTION: 500,
    MemoryType.DECISION: 200,
}
```

---

## 8. Exemplos de Uso

### 8.1 Fluxo Financeiro

```
Usuário: "gastei 150 no mercado"

1. CognitiveNode:
   - intent: "finance"
   - action: "create_finance"
   - entities: {amount: 150, category: "mercado"}

2. MemoryReader:
   - Busca preferências financeiras
   - Encontra: "categoria mercado = Alimentação"

3. ContextBuilder:
   - context: "👤 Categoria padrão mercado: Alimentação"

4. Executor:
   - Cria transação: R$ 150, categoria "Alimentação"

5. MemoryWriter:
   - Detecta padrão: gasto em mercado
   - Reforça memória de categoria

6. Responder (template):
   - "💰 Registrado: R$ 150 em Alimentação"
```

### 8.2 Fluxo com Agente Especializado

```
Usuário: "analise meus gastos"

1. CognitiveNode:
   - intent: "patterns"
   - action: "analyze_patterns"

2. MemoryReader:
   - Busca hábitos financeiros
   - Busca eventos recentes

3. ContextBuilder:
   - context: "🔄 Hábitos: paga contas dia 5"

4. Executor → SpecializedExecutor → PatternsAgent:
   - Analisa histórico financeiro
   - Detecta anomalias
   - Gera insights

5. MemoryWriter:
   - Registra análise como evento episódico

6. Responder:
   - "📈 Análise de Padrões Financeiros:
     - Maior categoria: Alimentação (35%)
     - Alerta: gastos 20% acima da média"
```

### 8.3 Fluxo de Memória

```
Usuário: "gosto de café sem açúcar"

1. CognitiveNode:
   - intent: "memory"
   - action: "save_preference"

2. MemoryReader:
   - Busca preferências existentes

3. ContextBuilder:
   - context: (nenhuma preferência de café ainda)

4. Executor → MemoryAgent:
   - Detecta preferência
   - Classifica: PREFERENCE, category: "food"

5. MemoryWriter:
   - Salva: "café sem açúcar"
   - confidence: 0.7 (implícito)

6. Responder:
   - "✅ Entendido! Vou lembrar que você prefere café sem açúcar."
```

---

## 9. Monitoramento

### 9.1 Logs Estruturados

```python
# Formato de log padrão
logger.info(
    f"[IRIS v3] ▶️ user={user_id} | "
    f"intent={intent} | "
    f"action={action} | "
    f"latency={latency}ms"
)

# Logs de memória
logger.info(
    f"[MEMORY_READER] user={user_id} | "
    f"intent={intent} | "
    f"found={len(memories)} | "
    f"relevant={len(filtered)}"
)
```

### 9.2 Métricas Prometheus

```python
GRAPH_METRICS = {
    "iris_request_total": Counter,
    "iris_request_latency_seconds": Histogram,
    "iris_memory_operations_total": Counter,
    "iris_agent_calls_total": Counter,
    "iris_confidence_score": Histogram,
}
```

---

## 10. Próximos Passos

### 10.1 Roadmap

| Fase | Descrição | Status |
|------|-----------|--------|
| 1 | Graph v3 base | ✅ Completo |
| 2 | Agentes especializados | ✅ Completo |
| 3 | Sistema de memória | ✅ Completo |
| 4 | Testes em produção | 🔄 Pendente |
| 5 | Agentes adicionais | 📋 Backlog |

### 10.2 Status das Melhorias

- [x] Cache Redis para working memory (`redis_working.py`)
- [x] Modelo de UserMemory no banco (`user_memory.py`)
- [x] Jobs de decay de confiança (`memory_decay.py`)
- [ ] Dashboard de auditoria (design pronto, implementação pendente)
- [ ] A/B testing v2 vs v3
- [ ] Métricas de qualidade de memória

---

## 11. Modelo de Dados - UserMemory

### 11.1 Tabela `user_memories`

```sql
CREATE TABLE user_memories (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Classificação
    memory_type memorytypeenum NOT NULL,
    layer memorylayerenum NOT NULL,
    category VARCHAR(50) DEFAULT 'general',
    
    -- Conteúdo
    key VARCHAR(255) NOT NULL,
    value JSON NOT NULL,
    summary VARCHAR(200),
    
    -- Confiança
    confidence FLOAT DEFAULT 0.5,
    importance importanceenum DEFAULT 'medium',
    source memorysourceenum DEFAULT 'user_implicit',
    
    -- Temporalidade
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    last_accessed TIMESTAMP,
    last_confirmed TIMESTAMP,
    expires_at TIMESTAMP,
    access_count INTEGER DEFAULT 0,
    
    -- Auditoria
    origin_session_id VARCHAR(100),
    origin_message_id VARCHAR(100),
    
    -- Flags
    requires_confirmation BOOLEAN DEFAULT FALSE,
    is_sensitive BOOLEAN DEFAULT FALSE,
    is_archived BOOLEAN DEFAULT FALSE
);
```

### 11.2 Tabela `memory_audit_logs`

```sql
CREATE TABLE memory_audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    memory_id INTEGER REFERENCES user_memories(id) ON DELETE SET NULL,
    
    operation VARCHAR(50) NOT NULL,  -- create, update, delete, decay, expire, override
    old_value JSON,
    new_value JSON,
    old_confidence FLOAT,
    new_confidence FLOAT,
    reason VARCHAR(255),
    session_id VARCHAR(100),
    
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 11.3 Índices

```sql
-- Queries principais
CREATE INDEX idx_um_user_type_conf ON user_memories(user_id, memory_type, confidence);
CREATE INDEX idx_um_user_category ON user_memories(user_id, category);
CREATE INDEX idx_um_user_layer ON user_memories(user_id, layer);

-- Jobs
CREATE INDEX idx_um_expires ON user_memories(expires_at, is_archived);
CREATE INDEX idx_um_decay ON user_memories(last_accessed, confidence, is_archived);

-- Unique constraint
CREATE UNIQUE INDEX idx_um_user_key ON user_memories(user_id, key);
```

---

## 12. Redis Working Memory

### 12.1 Estrutura de Keys

```
iris:user:{user_id}:session:{session_id}  → Contexto de sessão (TTL: 4h)
iris:user:{user_id}:working               → Working memory (TTL: 24h)
iris:user:{user_id}:memory_cache          → Cache PostgreSQL (TTL: 1h)
iris:user:{user_id}:context               → Contexto LLM (TTL: 5min)
```

### 12.2 TTL Dinâmico por Risco

| Risco | TTL | Operações |
|-------|-----|----------|
| Low | 30 min | greeting, direct_response |
| Medium | 2 horas | list_reminders, search |
| High | 4 horas | create_finance, create_reminder |
| Critical | 24 horas | delete_finance, create_goal |

---

## 13. Jobs de Manutenção

### 13.1 MemoryDecayJob

**Frequência:** Diariamente às 03:00 UTC

**Função:** Reduz confiança de memórias não acessadas

**Regras de Decay:**

| Tipo | Taxa/Dia | Mín. Confiança | Nunca Decai |
|------|----------|----------------|-------------|
| CONSTRAINT | 0% | 0.5 | ✅ Sim |
| IDENTITY | 0.2% | 0.3 | Não |
| PREFERENCE | 0.5% | 0.3 | Não |
| HABIT | 1% | 0.3 | Não |
| CONTEXT | 10% | 0.0 | Não |
| INFERENCE | 10% | 0.0 | Não |

### 13.2 MemoryExpirationJob

**Frequência:** A cada 6 horas

**Função:** Arquiva memórias com `expires_at` ultrapassado

### 13.3 MemoryCleanupJob

**Frequência:** Semanalmente (domingos)

**Função:** Remove permanentemente memórias arquivadas há mais de 90 dias

### 13.4 MemoryReinforcementJob

**Frequência:** Diariamente

**Função:** Aumenta confiança de memórias frequentemente acessadas

---

## 14. Endpoints Conectados

### 14.1 Chat API

```python
# POST /api/v1/chat/message
from app.ai.graph_v3.migration import process_message

result = await process_message(
    user_id=current_user.id,
    session_id=current_user.session_id,
    message=data.message,
    context={"user_name": current_user.name},
    db=db,
)
```

### 14.2 Audio API

```python
# POST /api/v1/chat/audio
from app.ai.graph_v3.migration import process_message

result = await process_message(
    user_id=current_user.id,
    session_id=current_user.session_id,
    message=transcription,
    context={"user_name": current_user.name},
    db=db,
)
```

### 14.3 WhatsApp Webhook

```python
# POST /api/v1/webhook/whatsapp
from app.ai.graph_v3.migration import process_message, GRAPH_VERSION

logger.info(f"[WEBHOOK] Processando com Graph {GRAPH_VERSION}")
result = await process_message(
    user_id=user.id,
    session_id=user.session_id,
    message=message_text,
    context={
        "user_name": user.name,
        "timezone": user.timezone,
        "source": "whatsapp",
    },
    db=db,
)
```

---

## 15. Guia de Hardening

Para informações detalhadas sobre preparação para produção, consulte:

📄 **`app/ai/HARDENING_GUIDE.md`**

Conteúdo:
- Checklist de staging
- Estratégia de rollback
- Feature flags
- Métricas de sucesso
- Riscos e mitigação

---

## Contato

Para dúvidas sobre a arquitetura, consulte:
- `MEMORY_ARCHITECTURE.md` - Detalhes do sistema de memória
- `agents/ARCHITECTURE.md` - Detalhes dos agentes especializados

---

*Documento gerado em Janeiro 2026*
