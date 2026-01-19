# Arquitetura dos Agentes de IA

## Visão Geral

O sistema utiliza **LangGraph** para orquestrar múltiplos agentes especializados que processam mensagens do usuário. A arquitetura segue o padrão de **classificação → roteamento → execução → resposta**.

```
┌─────────────────────────────────────────────────────────────────┐
│                     WhatsAppAIAgent                             │
│                   (Orquestrador Principal)                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Classifier Node                            │
│         (Classifica intenção com cache inteligente)             │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
    ┌──────────┐       ┌──────────┐       ┌──────────┐
    │ Reminder │       │ Finance  │       │ Meeting  │
    │  Agent   │       │  Agent   │       │  Agent   │
    └──────────┘       └──────────┘       └──────────┘
          │                   │                   │
          ▼                   ▼                   ▼
    ┌──────────┐       ┌──────────┐       ┌──────────┐
    │ Contact  │       │ General  │       │ Response │
    │  Agent   │       │  Chat    │       │Generator │
    └──────────┘       └──────────┘       └──────────┘
```

---

## Fluxo de Processamento

### 1. Entrada da Mensagem
```python
async def process_message(user_id, session_id, message, context, db):
    # 1. Carrega memória do usuário
    memory_manager = MemoryManager(db, user_id)
    
    # 2. Busca contexto RAG (documentos relevantes)
    embedding_service = EmbeddingService(db)
    rag_context = embedding_service.get_relevant_context(user_id, message)
    
    # 3. Verifica pending states (lembretes, contatos, reuniões pendentes)
    pending_reminder = memory_manager.service.get_memory(user_id, "pending_reminder")
    
    # 4. Executa o grafo LangGraph
    result = await self.graph.ainvoke(initial_state)
```

### 2. Classificação de Intenção
O sistema primeiro verifica o **cache de classificações** antes de chamar a LLM:

```python
def _classify_intent(state):
    # Verifica cache (confiança >= 80%)
    cached = cache_service.get_cached(message)
    if cached and cached["confidence"] >= 0.8:
        return cached
    
    # Se há pending state, roteia diretamente
    if context.get("pending_reminder"):
        return "reminder"
    
    # Caso contrário, usa LLM para classificar
    classification = llm.invoke(classification_prompt)
    
    # Salva no cache se confiança >= 70%
    if confidence >= 0.7:
        cache_service.cache_classification(message, intent, confidence)
```

### 3. Roteamento
Baseado na intenção classificada:

| Intent | Handler | Descrição |
|--------|---------|-----------|
| `reminder` | `_handle_reminder` | Lembretes e compromissos |
| `finance` | `_handle_finance` | Finanças pessoais |
| `meeting` | `_handle_meeting` | Reuniões e transcrições |
| `contact` | `_handle_contact` | Contatos e broadcasts |
| `general` | `_handle_general_chat` | Conversa geral |

---

## Agentes Especializados

### 1. ReminderAgent

**Arquivo:** `app/ai/agents/reminder_agent.py`

**Responsabilidades:**
- Criar lembretes únicos e recorrentes
- Extrair data/hora de linguagem natural
- Gerenciar tipos de recorrência (diário, semanal, mensal, dias úteis)
- Deletar lembretes existentes

**Intenções Reconhecidas:**
- `create_single` - Lembrete único
- `create_multiple` - Múltiplos lembretes
- `delete` - Remoção de lembrete
- `list` - Listagem de lembretes
- `clarify_time` - Solicitar horário específico

**Fluxo de Criação:**
```
Usuário: "Me lembra de ligar pro João amanhã às 14h"
    │
    ▼
┌─────────────────────────────────┐
│ Extrai: título, data, hora      │
│ - título: "Ligar pro João"      │
│ - scheduled_time: amanhã 14:00  │
│ - recurrence_type: "once"       │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│ Verifica remind_before_minutes  │
│ Se não informado → pending_state│
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│ Cria lembrete no banco          │
│ Retorna confirmação             │
└─────────────────────────────────┘
```

**Possíveis Falhas:**
| Falha | Causa | Mitigação |
|-------|-------|-----------|
| Data inválida | Parsing incorreto de linguagem natural | Usar biblioteca robusta (dateparser) |
| Timezone incorreto | Servidor em UTC, usuário em BRT | Sempre converter com timezone do usuário |
| Lembrete duplicado | Usuário envia mensagem repetida | Verificar lembretes similares recentes |
| Pending state perdido | Timeout ou erro de sessão | Persistir em `conversation_memory` |

---

### 2. FinanceAgent

**Arquivo:** `app/ai/agents/finance_agent.py`

**Responsabilidades:**
- Registrar receitas e despesas
- Categorizar transações automaticamente
- Gerar resumos financeiros
- Responder perguntas sobre histórico

**Categorias de Despesa:**
```python
EXPENSE_CATEGORIES = {
    "Alimentação": ["mercado", "supermercado", "restaurante", "ifood", ...],
    "Transporte": ["uber", "99", "gasolina", "combustível", ...],
    "Moradia": ["aluguel", "condomínio", "luz", "água", ...],
    "Saúde": ["farmácia", "médico", "hospital", ...],
    # ...
}
```

**Fluxo de Registro:**
```
Usuário: "Gastei 150 reais no mercado hoje"
    │
    ▼
┌─────────────────────────────────┐
│ Extrai: valor, descrição, tipo  │
│ - amount: 150.00                │
│ - description: "mercado"        │
│ - type: "expense"               │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│ Categoriza automaticamente      │
│ "mercado" → "Alimentação"       │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│ Salva no banco + confirma       │
│ "Registrei R$ 150 em Alimentação│
└─────────────────────────────────┘
```

**Possíveis Falhas:**
| Falha | Causa | Mitigação |
|-------|-------|-----------|
| Valor incorreto | "150 reais" vs "R$150,00" | Regex robusto para extração |
| Categoria errada | Palavra-chave ambígua | Permitir correção manual |
| Transação duplicada | Retry ou mensagem repetida | Verificar hash da mensagem |
| Moeda incorreta | Usuário menciona dólares | Converter ou perguntar |

---

### 3. MeetingAgent

**Arquivo:** `app/ai/agents/meeting_agent.py`

**Responsabilidades:**
- Agendar reuniões
- Analisar transcrições
- Extrair action items
- Gerar resumos de reuniões

**Intenções Reconhecidas:**
- `schedule` - Agendar nova reunião
- `confirm` - Confirmar detalhes pendentes
- `analyze` - Analisar transcrição
- `summarize` - Resumir reunião
- `action_items` - Extrair tarefas

**Fluxo de Análise:**
```
Usuário: [Envia transcrição de reunião]
    │
    ▼
┌─────────────────────────────────┐
│ Detecta que é transcrição       │
│ intent: "analyze"               │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│ LLM processa transcrição:       │
│ - Resumo executivo              │
│ - Participantes                 │
│ - Decisões tomadas              │
│ - Action items                  │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│ Salva meeting + action_items    │
│ Retorna resumo formatado        │
└─────────────────────────────────┘
```

**Possíveis Falhas:**
| Falha | Causa | Mitigação |
|-------|-------|-----------|
| Transcrição muito longa | Excede limite de tokens | Chunking + sumarização |
| Participantes incorretos | Nomes mal transcritos | Pedir confirmação |
| Data ambígua | "Próxima terça" sem referência | Usar data atual como base |
| Action items genéricos | LLM não específica bem | Prompt engineering |

---

### 4. ContactAgent

**Arquivo:** `app/ai/agents/contact_agent.py`

**Responsabilidades:**
- Criar e gerenciar contatos
- Agendar mensagens para envio
- Enviar broadcasts para grupos
- Listar grupos e contatos

**Intenções Reconhecidas:**
- `create_contact` - Novo contato
- `schedule_message` - Agendar envio
- `broadcast` - Mensagem para grupo
- `list_groups` - Listar grupos
- `list_contacts` - Listar contatos

**Fluxo de Broadcast:**
```
Usuário: "Manda 'Reunião amanhã' para o grupo Família"
    │
    ▼
┌─────────────────────────────────┐
│ Extrai: mensagem, grupo         │
│ - message: "Reunião amanhã"     │
│ - group: "Família"              │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│ Busca contatos do grupo         │
│ Família: [João, Maria, Pedro]   │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│ pending_broadcast = True        │
│ Pede confirmação ao usuário     │
└─────────────────────────────────┘
    │
    ▼ (após confirmação)
┌─────────────────────────────────┐
│ Envia via WhatsAppService       │
│ Confirma: "Enviado para 3"      │
└─────────────────────────────────┘
```

**Possíveis Falhas:**
| Falha | Causa | Mitigação |
|-------|-------|-----------|
| Contato duplicado | Mesmo nome/telefone | Verificar antes de criar |
| Grupo não encontrado | Nome digitado errado | Busca fuzzy |
| Telefone inválido | Formato incorreto | Validação + formatação |
| Broadcast não confirmado | Usuário não responde | Timeout + limpeza |

---

## Sistema de Memória

### MemoryManager

**Arquivo:** `app/ai/memory.py`

**Tipos de Memória:**

1. **Long-term Memory (Fatos)**
   - Nome do usuário
   - Profissão
   - Família
   - Preferências
   - Objetivos

2. **Short-term Memory (Conversa)**
   - Últimas 15 mensagens
   - Intent de cada mensagem
   - Entidades extraídas

3. **Pending States**
   - `pending_reminder` - Lembrete aguardando confirmação
   - `pending_contact` - Contato aguardando dados
   - `pending_meeting` - Reunião aguardando confirmação
   - `pending_broadcast` - Broadcast aguardando confirmação

### Contexto Enriquecido

O `build_context_prompt()` monta um prompt com:

```
CONTEXTO DO USUÁRIO (MEMÓRIA DE LONGO PRAZO):
Nome: João Silva
Profissão: Desenvolvedor
Timezone: America/Sao_Paulo

RESUMO FINANCEIRO DO MÊS:
  • Gastos: R$ 3.500,00
  • Receitas: R$ 8.000,00
  • Saldo: R$ 4.500,00
  • Maiores gastos: Alimentação: R$800, Transporte: R$500

LEMBRETES PRÓXIMOS:
  • Reunião com cliente - Amanhã às 10:00
  • Pagar conta de luz - 15/01 às 09:00

CONTATOS (45 total):
  • Família: João, Maria, Pedro (+5 mais)
  • Trabalho: Carlos, Ana, Lucas

DOCUMENTOS DO USUÁRIO (3 para contexto IA):
  📄 Contrato de Aluguel [Jurídico]
     Conteúdo: Contrato de locação residencial...

CONTEXTO DOS DOCUMENTOS (RAG Semântico):
  📄 Manual do Produto (relevância: 85%)
     [Conteúdo relevante encontrado via embeddings]

AÇÕES RECENTES CONFIRMADAS:
  ✅ Transação registrada: Mercado - R$150 (10:30)
  ✅ Lembrete criado: Ligar para João (10:25)
```

---

## Sistema de RAG (Retrieval-Augmented Generation)

### EmbeddingService

**Arquivo:** `app/services/embedding_service.py`

**Funcionamento:**

1. **Indexação de Documentos:**
   ```python
   def index_document(document_id, content):
       chunks = chunk_text(content)  # 1000 chars, 200 overlap
       for chunk in chunks:
           embedding = genai.embed_content(
               model="text-embedding-004",
               content=chunk,
               task_type="retrieval_document"
           )
           # Salva no pgvector
           INSERT INTO document_embeddings (embedding) VALUES (embedding::vector)
   ```

2. **Busca Semântica:**
   ```python
   def search_similar(user_id, query, limit=5, threshold=0.7):
       query_embedding = genai.embed_content(query, task_type="retrieval_query")
       
       # Busca por similaridade de cosseno
       SELECT chunk_text, 1 - (embedding <=> query_embedding) as similarity
       FROM document_embeddings
       WHERE similarity >= threshold
       ORDER BY embedding <=> query_embedding
       LIMIT 5
   ```

**Possíveis Falhas:**
| Falha | Causa | Mitigação |
|-------|-------|-----------|
| Embedding vazio | API do Gemini falhou | Retry com backoff |
| Chunks muito grandes | Token limit excedido | Reduzir CHUNK_SIZE |
| Busca lenta | Muitos documentos | Criar índice HNSW |
| Resultados irrelevantes | Threshold muito baixo | Ajustar threshold |

---

## Sistema de Cache

### ClassificationCacheService

**Tabela:** `classification_cache`

```sql
CREATE TABLE classification_cache (
    message_hash VARCHAR(64) UNIQUE,
    intent VARCHAR(50),
    confidence FLOAT,
    entities JSONB,
    hit_count INTEGER DEFAULT 1,
    last_used_at TIMESTAMP
);
```

**Funcionamento:**
- Hash SHA-256 da mensagem normalizada
- Cache hit se confiança >= 80%
- Atualiza `hit_count` e `last_used_at` a cada uso
- Cleanup automático de entradas antigas (30 dias)

**Benefícios:**
- Reduz chamadas à LLM em ~40%
- Latência < 10ms para cache hits
- Aprende padrões do usuário

---

## Sistema de Métricas

### AgentMetricsService

**Tabela:** `agent_metrics`

```sql
CREATE TABLE agent_metrics (
    user_id INTEGER,
    agent_name VARCHAR(50),
    action_type VARCHAR(50),
    success BOOLEAN,
    confidence FLOAT,
    response_time_ms INTEGER,
    created_at TIMESTAMP
);
```

**Métricas Coletadas:**
- Accuracy por agente
- Tempo médio de resposta
- Taxa de sucesso por tipo de ação
- Distribuição de uso por usuário

**API de Métricas:**
- `GET /api/metrics/agents` - Accuracy por agente
- `GET /api/metrics/user` - Stats do usuário
- `GET /api/metrics/feedback/summary` - Resumo de feedbacks

---

## Sistema de Feedback

### FeedbackService

**Tabela:** `user_feedback`

```sql
CREATE TABLE user_feedback (
    user_id INTEGER,
    message_id INTEGER,
    agent_name VARCHAR(50),
    rating INTEGER CHECK (1-5),
    feedback_type VARCHAR(20),  -- "positive", "negative", "correction"
    comment TEXT,
    context JSONB
);
```

**Uso:**
- Usuário pode avaliar respostas (1-5 estrelas)
- Tipos: positivo, negativo, correção
- Comentários opcionais para contexto

---

## Possíveis Falhas Gerais

### 1. Problemas de Classificação

| Problema | Causa | Solução |
|----------|-------|---------|
| Intent errado | Mensagem ambígua | Pedir clarificação |
| Confidence baixa | Vocabulário novo | Treinar com mais exemplos |
| Fallback excessivo | Keywords insuficientes | Expandir lista de palavras-chave |

### 2. Problemas de Memória

| Problema | Causa | Solução |
|----------|-------|---------|
| Contexto perdido | Sessão expirada | Persistir em DB |
| Memória muito grande | Muitas mensagens | Limitar a 15 mensagens |
| Fatos incorretos | Extração errada | Validar antes de salvar |

### 3. Problemas de Performance

| Problema | Causa | Solução |
|----------|-------|---------|
| Resposta lenta | LLM demorada | Cache de classificações |
| Timeout | Processamento longo | Async + timeout |
| Memória alta | Embeddings grandes | Limitar documentos |

### 4. Problemas de Integração

| Problema | Causa | Solução |
|----------|-------|---------|
| WhatsApp offline | API indisponível | Retry + notificação |
| Gemini rate limit | Muitas requisições | Rate limiter |
| DB connection | Pool esgotado | Aumentar pool size |

---

## Recomendações de Melhoria

1. **Treinar modelo de classificação** - Fine-tune para reduzir dependência de keywords
2. **Adicionar fallback graceful** - Se um agente falha, tentar outro
3. **Implementar A/B testing** - Testar diferentes prompts
4. **Monitoramento em tempo real** - Dashboard de métricas
5. **Testes automatizados** - Unit tests para cada agente
6. **Rate limiting por usuário** - Evitar abuso
7. **Logs estruturados** - Para debugging e análise

---

## Arquivos Principais

```
backend/
├── app/
│   ├── ai/
│   │   ├── graph.py              # Orquestrador LangGraph
│   │   ├── memory.py             # Gerenciador de memória
│   │   └── agents/
│   │       ├── base_agent.py     # Classe base
│   │       ├── reminder_agent.py # Agente de lembretes
│   │       ├── finance_agent.py  # Agente financeiro
│   │       ├── meeting_agent.py  # Agente de reuniões
│   │       └── contact_agent.py  # Agente de contatos
│   ├── services/
│   │   ├── embedding_service.py  # RAG + Cache + Métricas
│   │   └── memory_service.py     # Persistência de memória
│   └── api/
│       ├── chat.py               # Endpoint de chat
│       └── metrics.py            # Endpoints de métricas
```
