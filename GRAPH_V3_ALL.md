# 🧠 GRAPH_V3_ALL.md - Documentação Completa do Sistema IRIS

**Versão:** 3.0  
**Última Atualização:** Janeiro 2026  
**Autor:** Documentação Técnica Automatizada

---

## 📑 ÍNDICE

1. [Visão Geral](#1-visão-geral)
2. [Arquitetura do Grafo](#2-arquitetura-do-grafo)
3. [Fluxo de Processamento](#3-fluxo-de-processamento)
4. [Nós do Grafo](#4-nós-do-grafo)
5. [Executores](#5-executores)
6. [Agentes Especializados](#6-agentes-especializados)
7. [Sistema de Prompts](#7-sistema-de-prompts)
8. [Sistema de Memória](#8-sistema-de-memória)
9. [Sistema de Contexto](#9-sistema-de-contexto)
10. [Serviços Integrados](#10-serviços-integrados)
11. [Estado do Grafo](#11-estado-do-grafo)
12. [Integrações Externas](#12-integrações-externas)
13. [Configuração e LLMs](#13-configuração-e-llms)

---

## 1. VISÃO GERAL

### O que é IRIS?

**IRIS** (Intelligent Retrieval & Insight System) é uma assistente financeira pessoal inteligente que opera via WhatsApp. Ela é capaz de:

- 💰 Gerenciar finanças pessoais (receitas, despesas, resumos, agente especializado)
- ⏰ Criar e gerenciar lembretes
- 📅 Integrar com Google Calendar
- 📋 Gerenciar tarefas
- 🎯 Acompanhar metas financeiras
- 🔍 Pesquisar informações na web
- 📊 Analisar padrões de gastos
- 💡 Dar conselhos financeiros personalizados

### Arquitetura de Alto Nível

```
┌─────────────────────────────────────────────────────────────────┐
│                        WHATSAPP API (Twilio)                     │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                        app/api/webhooks.py                       │
│                     (Recebe mensagens do usuário)                │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                         IRISGraphV3                              │
│                    app/ai/graph_v3/core.py                       │
│                                                                  │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐     │
│  │Cognitive │ → │ Memory   │ → │ Executor │ → │Responder │     │
│  │  Node    │   │  Reader  │   │   Node   │   │  Node    │     │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘     │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                        PostgreSQL + Redis                        │
│                    (Dados do usuário + Cache)                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. ARQUITETURA DO GRAFO

### Localização: `app/ai/graph_v3/`

```
graph_v3/
├── core.py                 # Grafo principal (IRISGraphV3)
├── migration.py            # Compatibilidade com versões anteriores
├── __init__.py             # Exports do módulo
│
├── nodes/                  # Nós de processamento
│   ├── cognitive.py        # CognitiveNode (classificação + extração)
│   └── responder.py        # ResponderNode (geração de respostas)
│
├── executors/              # Executores de ações
│   ├── executor.py         # ExecutorNode (orquestrador)
│   ├── finance.py          # Ações financeiras
│   ├── reminder.py         # Ações de lembretes
│   ├── calendar.py         # Ações do Google Calendar
│   ├── task.py             # Ações de tarefas
│   ├── meeting.py          # Ações de reuniões
│   ├── message.py          # Mensagens agendadas
│   ├── integrations.py     # Web search, notícias, clima
│   └── specialized.py      # Dispatcher para agentes especializados
│
├── prompts/                # Prompts para LLMs
│   ├── cognitive_prompts.py
│   ├── responder_prompts.py
│   ├── financial_agent_prompts.py
│   └── meeting_transcription_prompts.py
│
├── state/                  # Definição do estado
│   └── types.py            # IRISStateV3, ExtractedAction, etc
│
└── templates/              # Templates de resposta
    └── responses.py
```

### Classe Principal: IRISGraphV3

**Arquivo:** `app/ai/graph_v3/core.py`

```python
class IRISGraphV3:
    """Grafo LangGraph v3 - Arquitetura otimizada."""

    def __init__(self, api_key: str = None):
        self._init_llms()      # Inicializa LLMs (Flash + Pro)
        self._init_nodes()     # Inicializa nós do grafo
        self.graph = self._build_graph()  # Compila o grafo
```

---

## 3. FLUXO DE PROCESSAMENTO

### Fluxo Completo (6 Nós)

```
┌─────────────┐
│   ENTRADA   │  Mensagem do usuário via WhatsApp
└─────┬───────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. COGNITIVE NODE                                            │
│    - Classifica intenção (finance, reminder, calendar, etc)  │
│    - Extrai entidades (valores, datas, descrições)           │
│    - Decide ação (create_finance, query_finance, etc)        │
│    - Define flags cognitivas (needs_user_data, needs_web)    │
│    LLM: Gemini 2.5 Pro (Flash)                               │
└─────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. MEMORY READER                                             │
│    - Busca memórias relevantes do usuário                    │
│    - Carrega preferências e fatos aprendidos                 │
│    LLM: Não usa (processamento local)                        │
└─────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. CONTEXT BUILDER                                           │
│    - Constrói contexto otimizado para o LLM                  │
│    - Combina memórias + dados do usuário                     │
│    LLM: Não usa (processamento local)                        │
└─────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. EXECUTOR NODE                                             │
│    - Despacha para executor específico (Finance, Reminder)   │
│    - Executa ação no banco de dados                          │
│    - Retorna dados para o ResponderNode                      │
│    LLM: Não usa (execução direta)                            │
└─────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. MEMORY WRITER                                             │
│    - Persiste memórias relevantes                            │
│    - Aprende preferências do usuário                         │
│    LLM: Não usa (processamento local)                        │
└─────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. RESPONDER NODE                                            │
│    - Gera resposta inteligente usando dados reais            │
│    - Formata para WhatsApp (markdown, emojis)                │
│    LLM: Gemini Pro (modelo principal)                        │
└─────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────┐
│    SAÍDA    │  Resposta enviada via WhatsApp
└─────────────┘
```

### Roteamento Condicional

```python
# Após CognitiveNode
if action in ["direct_response", "none"]:
    → responder (saudações, respostas diretas)
elif action == "needs_llm_response":
    → responder (precisa de LLM para responder)
else:
    → memory_reader (ações que precisam de execução)

# Após MemoryWriter
if early_exit and response_template:
    → end (template pronto)
else:
    → responder (precisa gerar resposta inteligente)
```

---

## 4. NÓS DO GRAFO

### 4.1 CognitiveNode

**Arquivo:** `app/ai/graph_v3/nodes/cognitive.py`

**Responsabilidades:**
1. Classificar a **intenção real** do usuário
2. Extrair **entidades** relevantes (valores, datas, descrições)
3. Decidir a **ação** a ser executada
4. Definir **flags cognitivas** para os próximos nós

**LLM Usado:** Gemini 2.5 Pro (Flash) - Rápido e preciso

**Intents Suportados:**

| Intent | Descrição | Exemplos |
|--------|-----------|----------|
| `finance` | Finanças pessoais | "gastei 50 reais", "quanto tenho?" |
| `reminder` | Lembretes | "me lembra às 15h", "meus lembretes" |
| `calendar` | Google Calendar | "agenda reunião amanhã" |
| `task` | Tarefas | "criar tarefa", "minhas tarefas" |
| `message` | Mensagens agendadas | "manda mensagem às 18h" |
| `search` | Pesquisa web | "cotação do dólar" |
| `goals` | Metas financeiras | "quero economizar 5000" |
| `advisor` | Análises complexas | "analise meus gastos" |
| `patterns` | Padrões de gastos | "detecte anomalias" |
| `general` | Conversas gerais | "oi", "obrigado" |

**Ações Extraídas:**

```python
# Finanças
"create_finance"    # Registrar gasto/receita
"query_finance"     # Consultar finanças
"delete_finance"    # Deletar transação
"update_finance"    # Atualizar transação

# Lembretes
"create_reminder"   # Criar lembrete
"list_reminders"    # Listar lembretes
"delete_reminder"   # Deletar lembrete

# Calendar (Google)
"create_event"      # Criar evento
"list_events"       # Listar eventos
"check_availability"# Verificar disponibilidade

# Tarefas
"create_task"       # Criar tarefa
"list_tasks"        # Listar tarefas
"complete_task"     # Completar tarefa
"delete_task"       # Deletar tarefa

# Pesquisa
"web_search"        # Pesquisa web
"search_news"       # Buscar notícias

# Especiais
"direct_response"   # Resposta direta (saudação)
"needs_llm_response"# Precisa de LLM para responder
```

**Flags Cognitivas:**

```python
needs_user_data: bool  # True = precisa buscar dados do usuário
needs_web: bool        # True = precisa buscar na web
needs_analysis: bool   # True = modo assessor financeiro ativo
```

**Early Exit (Otimização):**

O CognitiveNode detecta mensagens triviais e retorna imediatamente:
- Saudações: "oi", "olá", "bom dia"
- Agradecimentos: "obrigado", "valeu"

---

### 4.2 ResponderNode

**Arquivo:** `app/ai/graph_v3/nodes/responder.py`

**Responsabilidades:**
1. Gerar respostas **inteligentes** baseadas em dados reais
2. Usar modo **Assessor Financeiro Sênior** quando necessário
3. Formatar respostas para **WhatsApp** (markdown, emojis)
4. Limitar a **1200 caracteres** (exceto quando pedido)

**LLM Usado:** Gemini Pro (modelo principal)

**Modos de Resposta:**

| Modo | Quando Usar | Descrição |
|------|-------------|-----------|
| Template | `response_template` existe | Resposta pré-formatada |
| Contextual | `needs_user_data=True` | Usa dados do banco |
| General | Conversas gerais | Conhecimento financeiro geral |
| Assessor | `needs_analysis=True` | Análise profunda com riscos/trade-offs |

**Construção de Contexto:**

```python
def _build_data_context(self, state):
    # 1. Transações do usuário
    if "transactions" in data:
        # Lista até 20 transações com emoji, valor, descrição, categoria

    # 2. Resumo financeiro
    if "summary" in data:
        # Receitas, Gastos, Saldo, Total de transações

    # 3. Resultados de busca web
    if "web_search" in data:
        # Contexto da web para complementar resposta
```

---

## 5. EXECUTORES

### Localização: `app/ai/graph_v3/executors/`

### 5.1 ExecutorNode (Orquestrador)

**Arquivo:** `executor.py`

**Responsabilidade:** Despachar ações para o executor correto.

```python
ACTION_DISPATCHERS = {
    # Finanças
    "create_finance": FinanceExecutor.create,
    "query_finance": FinanceExecutor.query,
    "delete_finance": FinanceExecutor.delete,
    "update_finance": FinanceExecutor.update,

    # Lembretes
    "create_reminder": ReminderExecutor.create,
    "list_reminders": ReminderExecutor.list_all,
    ...

    # Calendar (Google)
    "create_event": CalendarExecutor.create_event,
    "list_events": CalendarExecutor.list_events,
    ...

    # Tarefas
    "create_task": TaskExecutor.create,
    ...

    # Pesquisa
    "web_search": IntegrationsExecutor.web_search,
    ...
}
```

---

### 5.2 FinanceExecutor

**Arquivo:** `finance.py`

**Ações:**

| Método | Ação | Descrição |
|--------|------|-----------|
| `create()` | `create_finance` | Cria transação financeira |
| `query()` | `query_finance` | Consulta finanças (resumo, top N, busca) |
| `delete()` | `delete_finance` | Deleta transação por filtros |
| `update()` | `update_finance` | Atualiza transação existente |

**Parâmetros de Query:**

```python
params = {
    "periodo": "mes",           # hoje, semana, mes, ano, mes_anterior
    "limite": 5,                # Top N transações
    "ordenacao": "maior",       # maior ou menor
    "tipo_filtro": "expense",   # expense, income, all
    "busca": "mercado",         # Filtro por descrição/categoria
}
```

**Exemplo de Retorno:**

```python
ExecutionResult(
    success=True,
    action_type="query_finance",
    data={
        "transactions": [...],   # Lista de transações
        "summary": {
            "total_income": 10000.00,
            "total_expenses": 5000.00,
            "balance": 5000.00,
            "count": 45
        },
        "by_category": [...]     # Gastos por categoria
    }
)
```

---

### 5.3 ReminderExecutor

**Arquivo:** `reminder.py`

**Ações:**

| Método | Ação | Descrição |
|--------|------|-----------|
| `create()` | `create_reminder` | Cria lembrete |
| `list_all()` | `list_reminders` | Lista lembretes ativos |
| `delete()` | `delete_reminder` | Deleta lembrete |
| `update()` | `update_reminder` | Atualiza lembrete |

---

### 5.4 CalendarExecutor

**Arquivo:** `calendar.py`

**Integração:** Google Calendar API

**Ações:**

| Método | Ação | Descrição |
|--------|------|-----------|
| `create_event()` | `create_event` | Cria evento no Google Calendar |
| `list_events()` | `list_events` | Lista próximos eventos |
| `check_availability()` | `check_availability` | Verifica disponibilidade |

**Extração de Entidades:**

```python
# O CognitiveNode extrai:
{
    "date": "2026-01-28",        # Data no formato YYYY-MM-DD
    "time": "14:00",             # Horário no formato HH:MM
    "title": "Reunião com João", # Título do evento
    "duration": 60,              # Duração em minutos
    "attendees": ["joao@email"]  # Participantes
}
```

---

### 5.5 TaskExecutor

**Arquivo:** `task.py`

**Ações:**

| Método | Ação | Descrição |
|--------|------|-----------|
| `create()` | `create_task` | Cria tarefa |
| `list_all()` | `list_tasks` | Lista tarefas |
| `complete()` | `complete_task` | Marca como concluída |
| `delete()` | `delete_task` | Deleta tarefa |
| `get_summary()` | `task_summary` | Resumo de tarefas |

**Prioridades:**

```python
🟢 low      # Baixa
🟡 medium   # Média
🟠 high     # Alta
🔴 urgent   # Urgente
```

---

### 5.6 IntegrationsExecutor

**Arquivo:** `integrations.py`

**Ações:**

| Método | Ação | API Externa |
|--------|------|-------------|
| `web_search()` | `web_search` | Tavily API |
| `search_news()` | `search_news` | Tavily API |
| `get_weather()` | `get_weather` | (Placeholder) |

**Exemplo de Web Search:**

```python
# Usa Tavily API para buscar informações
response = client.search(
    query="cotação dólar hoje",
    search_depth="basic",
    max_results=5,
    include_answer=True
)

# Retorna para o ResponderNode processar
ExecutionResult(
    success=True,
    data={
        "query": "cotação dólar hoje",
        "answer": "O dólar está cotado a R$5,12...",
        "results": [...],
        "needs_llm": True  # Indica que LLM deve processar
    }
)
```

---

### 5.7 SpecializedExecutor

**Arquivo:** `specialized.py`

**Responsabilidade:** Despacha para agentes especializados (assíncronos).

**Ações Especializadas:**

```python
SPECIALIZED_ACTIONS = {
    # Bills Agent
    "extract_invoice", "list_bills", "create_bill_reminder",

    # Memory Agent
    "save_preference", "read_memory", "delete_memory",

    # Patterns Agent
    "analyze_patterns", "detect_anomalies",

    # Goals Agent
    "create_goal", "list_goals", "goal_progress",

    # Subscriptions Agent
    "list_subscriptions", "analyze_subscriptions",

    # Advisor Agent
    "simulate_scenario", "run_projection", "financial_state",

    # Health Agent
    "create_health_reminder", "health_schedule",
}
```

---

## 6. AGENTES ESPECIALIZADOS

### Localização: `app/ai/agents/`

```
agents/
├── base.py              # SpecializedAgent (classe base)
├── base_agent.py        # BaseAgent (legado, usado pelo MeetingAgent)
├── registry.py          # AgentRegistry (registro centralizado)
├── dispatcher.py        # Dispatcher para agentes
│
├── bills/               # Extração de faturas/boletos
│   ├── agent.py
│   └── tools.py
│
├── memory/              # Preferências e memórias
│   └── agent.py
│
├── goals/               # Metas financeiras
│   └── agent.py
│
├── patterns/            # Análise de padrões
│   └── agent.py
│
├── advisor/             # Simulações e projeções
│   └── agent.py
│
├── health/              # Lembretes de saúde
│   └── agent.py
│
├── subscriptions/       # Assinaturas recorrentes
│   └── agent.py
│
└── meeting_agent.py     # Transcrição de áudio
```

### 6.1 Registro de Agentes

**Arquivo:** `registry.py`

```python
class AgentRegistry:
    """Registro centralizado de agentes especializados."""

    @classmethod
    def register(cls, agent_class):
        """Decorator para registrar um agente."""
        # Uso:
        @AgentRegistry.register
        class BillsAgent(SpecializedAgent):
            name = "bills"
            supported_intents = ["bills", "invoice", "fatura"]
```

### 6.2 GoalsAgent

**Arquivo:** `goals/agent.py`

**Funcionalidades:**
- Criar metas de economia
- Acompanhar progresso
- Analisar viabilidade com dados financeiros reais

```python
@AgentRegistry.register
class GoalsAgent(SpecializedAgent):
    name = "goals"
    supported_intents = ["goals", "meta", "objetivo", "economizar", "poupar"]
```

### 6.3 BillsAgent

**Arquivo:** `bills/agent.py`

**Funcionalidades:**
- Extrair dados de faturas/boletos de imagens
- Criar lembretes de pagamento
- Listar contas a pagar

### 6.4 MemoryAgent

**Arquivo:** `memory/agent.py`

**Funcionalidades:**
- Salvar preferências do usuário
- Ler memórias salvas
- Deletar memórias

### 6.5 MeetingAgent

**Arquivo:** `meeting_agent.py`

**Funcionalidades:**
- Processar transcrições de áudio
- Gerar resumos de reuniões
- Extrair action items

**Uso no chat.py:**

```python
# Quando usuário envia áudio
meeting_agent = MeetingAgent()
result = await meeting_agent.process(transcription, entities)
```

---

## 7. SISTEMA DE PROMPTS

### Localização: `app/ai/graph_v3/prompts/`

### 7.1 Cognitive Prompts

**Arquivo:** `cognitive_prompts.py`

**COGNITIVE_PROMPT:**

```
Você é um analisador semântico avançado...

## ANÁLISE SEMÂNTICA
- "quais foram os 5 maiores gastos" → query_finance com limite=5, ordenacao=maior
- "como estou para economizar 5000" → goal_progress com meta_valor=5000

## INTENTS DISPONÍVEIS
1. finance - Qualquer coisa sobre dinheiro
2. reminder - Lembretes
3. calendar - Google Calendar
4. task - Tarefas
...

## AÇÕES POR INTENT
### FINANCE:
- create_finance: Registrar gasto/receita
- query_finance: Consultar finanças
...

## FLAGS COGNITIVAS (OBRIGATÓRIO)
- needs_user_data: true SE pergunta sobre dados pessoais
- needs_web: true SE precisa buscar na web
- needs_analysis: true SE pede análise/conselho

## OUTPUT (JSON)
{"intent":"finance","action":"query_finance","needs_user_data":true,...}
```

### 7.2 Responder Prompts

**Arquivo:** `responder_prompts.py`

**RESPONSE_PROMPT:**

```
Você é **IRIS**, uma **Assistente Financeira SÊNIOR**...

## HIERARQUIA DE RACIOCÍNIO
1. ENTENDA A INTENÇÃO REAL
2. DECIDA AS FONTES NECESSÁRIAS
3. ANÁLISE COMO ASSESSORA FINANCEIRA SÊNIOR
4. COMUNICAÇÃO (FORMATO WHATSAPP)

## COMPORTAMENTO INTELIGENTE
- Se pergunta financeira sem dados → eduque e contextualize
- Se houver dados pessoais → analise e personalize
- Se pergunta vaga → faça 1 pergunta de esclarecimento

## REGRAS ABSOLUTAS
❌ Nunca invente valores do usuário
❌ Nunca force resumo financeiro
```

---

## 8. SISTEMA DE MEMÓRIA

### Localização: `app/ai/memory/`

### Arquitetura de Camadas

```
┌─────────────────────────────────────────┐
│ Camada 1: SESSÃO (volátil)              │
│ - Contexto da conversa atual            │
│ - TTL: Duração da sessão                │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│ Camada 2: TRABALHO (Redis)              │
│ - Contexto de trabalho temporário       │
│ - TTL: 24 horas                         │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│ Camada 3: LONGO PRAZO (PostgreSQL)      │
│ - Preferências, fatos aprendidos        │
│ - TTL: Permanente                       │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│ Camada 4: EPISÓDICA (PostgreSQL)        │
│ - Histórico de interações               │
│ - TTL: Rotacionado (30 dias)            │
└─────────────────────────────────────────┘
```

### 8.1 MemoryReaderNode

**Arquivo:** `reader.py`

- Busca memórias relevantes para o contexto atual
- Carrega preferências e fatos aprendidos

### 8.2 MemoryWriterNode

**Arquivo:** `writer.py`

- Persiste memórias relevantes após cada interação
- Aprende novas preferências do usuário

### 8.3 MemoryManager

**Arquivo:** `manager.py`

- Interface unificada para operações de memória
- Integra com AIContextCache (Redis)

---

## 9. SISTEMA DE CONTEXTO

### Localização: `app/ai/context/`

### 9.1 UserDataLoader

**Arquivo:** `user_data_loader.py`

**Responsabilidade:** Carregar TODOS os dados do usuário do PostgreSQL.

**Dados Carregados:**

```python
context = {
    "finance": {
        "current_month": {
            "transactions": [...],
            "summary": {...},
            "by_category": [...]
        },
        "previous_month": {...},
        "top_expenses": [...]
    },
    "reminders": [...],
    "meetings": [...],
    "scheduled_messages": [...],
    "goals": [...],
    "summary": {...}
}
```

### 9.2 ContextBuilder

**Arquivo:** `context_builder.py`

**Responsabilidade:** Formatar dados brutos em prompts otimizados para o LLM.

**Seções Construídas:**

```
═══════════════════════════════════════════
📊 CONTEXTO COMPLETO DO USUÁRIO
═══════════════════════════════════════════
👤 Usuário: João Silva
📅 Data/Hora: 28/01/2026 10:00
📆 Dia da semana: Terça-feira

💰 FINANÇAS
──────────────────────────────────
📅 Período atual: Janeiro 2026
💵 Receitas: R$ 10.000,00
💸 Gastos: R$ 5.000,00
🟢 Saldo: R$ 5.000,00
📈 Taxa de poupança: 50.0%

🔝 TOP 5 MAIORES GASTOS DO MÊS:
1. 🔴 R$ 1.500,00 - Aluguel (Moradia)
2. 🔴 R$ 800,00 - Supermercado (Alimentação)
...

⏰ LEMBRETES ATIVOS
──────────────────────────────────
• Pagar conta de luz - 30/01 10:00
...
```

---

## 10. SERVIÇOS INTEGRADOS

### Localização: `app/services/`

| Serviço | Arquivo | Descrição |
|---------|---------|-----------|
| `FinanceService` | `finance_service.py` | CRUD de transações financeiras |
| `ReminderService` | `reminder_service.py` | CRUD de lembretes |
| `MeetingService` | `meeting_service.py` | CRUD de reuniões |
| `TaskService` | `task_service.py` | CRUD de tarefas |
| `GoogleCalendarService` | `google_calendar_service.py` | Integração Google Calendar |
| `WhatsAppService` | `whatsapp_service.py` | Envio de mensagens via Twilio |
| `AuthService` | `auth_service.py` | Autenticação de usuários |
| `CacheService` | `cache_service.py` | Cache Redis |
| `EmailService` | `email/service.py` | Envio de emails |

---

## 11. ESTADO DO GRAFO

### Arquivo: `app/ai/graph_v3/state/types.py`

### IRISStateV3

```python
class IRISStateV3(MessagesState):
    # === Identificação ===
    user_id: int = 0
    session_id: str = ""
    user_name: str = ""

    # === Database ===
    db: Optional[Any] = None

    # === Classificação ===
    intent: IntentType = "general"
    confidence: float = 0.0

    # === Ação Extraída ===
    action: Optional[ExtractedAction] = None
    entities: Dict[str, Any] = {}

    # === Resultado da Execução ===
    execution_result: Optional[ExecutionResult] = None

    # === Controle de Fluxo ===
    early_exit: bool = False
    response_template: Optional[str] = None

    # === Flags Cognitivas ===
    needs_user_data: bool = False
    needs_web: bool = False
    needs_analysis: bool = False

    # === Contexto ===
    context_prompt: str = ""
    rag_context: str = ""

    # === Erro ===
    error: Optional[str] = None
```

### ExtractedAction

```python
@dataclass
class ExtractedAction:
    action_type: ActionType      # "create_finance", "query_finance", etc
    params: Dict[str, Any] = {}  # Entidades extraídas
    confidence: float = 0.0      # Confiança da classificação
    requires_confirmation: bool = False  # Ações perigosas
```

### ExecutionResult

```python
@dataclass
class ExecutionResult:
    success: bool
    action_type: ActionType
    data: Dict[str, Any] = {}
    error: Optional[str] = None
    response_template: Optional[str] = None  # Template pré-formatado
```

---

## 12. INTEGRAÇÕES EXTERNAS

### 12.1 Google Calendar

**Serviço:** `GoogleCalendarService`

**Endpoints:**
- Criar evento
- Listar eventos
- Verificar disponibilidade

**Autenticação:** OAuth2 (token por usuário)

### 12.2 Twilio (WhatsApp)

**Serviço:** `WhatsAppService`

**Funcionalidades:**
- Enviar mensagens de texto
- Enviar typing indicator
- Receber webhooks

### 12.3 Tavily (Web Search)

**Executor:** `IntegrationsExecutor.web_search()`

**Uso:** Pesquisas web para complementar respostas

### 12.4 Google Gemini

**LLMs Usados:**

| Modelo | Uso | Configuração |
|--------|-----|--------------|
| `gemini-2.5-pro` | CognitiveNode | temperature=0.1, fast |
| `gemini-pro` | ResponderNode | temperature=0.7, creative |

---

## 13. CONFIGURAÇÃO E LLMs

### Arquivo: `app/config.py`

```python
class Settings:
    # LLM
    GOOGLE_API_KEY: str
    GEMINI_MODEL: str = "gemini-pro"

    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str

    # Twilio (WhatsApp)
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
    TWILIO_WHATSAPP_NUMBER: str

    # Tavily (Web Search)
    TAVILY_API_KEY: str

    # Google Calendar
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
```

### Retry com Backoff Exponencial

**Arquivo:** `app/ai/llm/retry.py`

```python
def invoke_llm_with_retry(llm, prompt, operation_name, max_attempts=3):
    """Invoca LLM com retry e backoff exponencial."""
    for attempt in range(max_attempts):
        try:
            return llm.invoke(prompt)
        except Exception as e:
            if attempt < max_attempts - 1:
                wait_time = (2 ** attempt) + random.random()
                time.sleep(wait_time)
            else:
                raise
```

---

## 📊 RESUMO DE MÉTRICAS

| Métrica | Valor |
|---------|-------|
| Nós do Grafo | 6 |
| Executores | 8 |
| Agentes Especializados | 7 |
| Intents Suportados | 10 |
| Ações Disponíveis | 40+ |
| LLMs Usados | 2 (Flash + Pro) |
| Latência Média | 2-5 segundos |

---

## 🔧 COMO A IA RESPONDE

### Fluxo de Exemplo: "Quais foram minhas receitas desse mês?"

```
1. WEBHOOK recebe mensagem do WhatsApp

2. COGNITIVE NODE:
   - Input: "Quais foram minhas receitas desse mês?"
   - Análise: Usuário quer ver SUAS receitas → precisa de dados pessoais
   - Output:
     {
       "intent": "finance",
       "action": "query_finance",
       "needs_user_data": true,
       "entities": {
         "periodo": "mes",
         "tipo_filtro": "income"
       }
     }

3. MEMORY READER:
   - Busca memórias relevantes do usuário
   - Carrega preferências (ex: formato de moeda preferido)

4. EXECUTOR NODE:
   - Despacha para FinanceExecutor.query()
   - Busca no PostgreSQL: transações do mês com type=income
   - Retorna:
     {
       "transactions": [...],
       "summary": {
         "total_income": 10320.00,
         "count": 5
       }
     }

5. MEMORY WRITER:
   - Registra que usuário consultou receitas
   - Atualiza contexto de conversa

6. RESPONDER NODE:
   - Recebe needs_user_data=true
   - Constrói contexto com dados reais:
     "### TRANSAÇÕES (5):
      1. 🟢 R$ 8.000,00 - Salário (Receita)
      2. 🟢 R$ 1.500,00 - Freelance (Receita)
      ..."
   - Gera resposta inteligente usando LLM Pro:
     "Olá! 👋 Suas receitas de janeiro totalizam *R$ 10.320,00*:
      
      💰 *Salário:* R$ 8.000,00
      💼 *Freelance:* R$ 1.500,00
      📈 *Dividendos:* R$ 820,00
      
      Ótimo mês! Sua receita está 15% acima do mês anterior. 🚀"

7. WEBHOOK envia resposta via WhatsApp
```

---

**Documento gerado automaticamente para referência técnica.**
