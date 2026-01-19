# 🤖 Especificação dos Agentes

## Visão Geral do Sistema de Agentes

O sistema utiliza **LangGraph** para orquestrar agentes especializados. Cada agente é um especialista em seu domínio e possui:

1. **Memória persistente** por usuário
2. **Tools** específicas para suas operações
3. **Prompts otimizados** para seu domínio
4. **Capacidade de manter contexto** entre conversas

---

## Arquitetura dos Agentes

```
┌─────────────────────────────────────────────────────────────┐
│                    LANGGRAPH ORCHESTRATOR                    │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                  Intent Classifier                      │ │
│  │         (Classifica intenção da mensagem)              │ │
│  └────────────────────────┬───────────────────────────────┘ │
│                           │                                  │
│           ┌───────────────┼───────────────┐                 │
│           ▼               ▼               ▼                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  REMINDER   │  │   FINANCE   │  │   MEETING   │         │
│  │   AGENT     │  │    AGENT    │  │    AGENT    │         │
│  │             │  │             │  │             │         │
│  │ ┌─────────┐ │  │ ┌─────────┐ │  │ ┌─────────┐ │         │
│  │ │  Tools  │ │  │ │  Tools  │ │  │ │  Tools  │ │         │
│  │ └─────────┘ │  │ └─────────┘ │  │ └─────────┘ │         │
│  │ ┌─────────┐ │  │ ┌─────────┐ │  │ ┌─────────┐ │         │
│  │ │ Memory  │ │  │ │ Memory  │ │  │ │ Memory  │ │         │
│  │ └─────────┘ │  │ └─────────┘ │  │ └─────────┘ │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│           │               │               │                 │
│           └───────────────┼───────────────┘                 │
│                           ▼                                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │               Response Generator                        │ │
│  │         (Gera resposta natural em PT-BR)               │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## 1. Reminder Agent (Agente de Lembretes)

### Responsabilidades
- Criar lembretes únicos e recorrentes
- Extrair data/hora da linguagem natural
- Configurar antecedência de notificação
- Listar lembretes pendentes
- Cancelar/editar lembretes

### Prompts de Extração

```python
REMINDER_EXTRACTION_PROMPT = """
Você é um especialista em extrair informações de lembretes.
Analise a mensagem do usuário e extraia TODAS as informações relevantes.

Contexto:
- Data/Hora atual: {current_datetime}
- Timezone do usuário: {user_timezone}

Mensagem do usuário: {message}

Extraia e retorne um JSON com:
{
    "title": "título claro e conciso",
    "description": "descrição adicional se houver",
    "scheduled_time": "ISO 8601 (YYYY-MM-DDTHH:MM:SS)",
    "remind_before_minutes": número (0 se não especificado),
    "recurrence_type": "once|daily|weekdays|weekends|weekly|monthly|yearly",
    "recurrence_config": {} // configurações adicionais
}

Regras:
1. "amanhã" = dia seguinte ao atual
2. "próxima semana" = 7 dias a partir de hoje
3. Se não especificar hora, usar 09:00
4. "me lembre antes" → extrair minutos de antecedência
5. "todo dia" → recurrence_type: "daily"
6. "de segunda a sexta" → recurrence_type: "weekdays"
"""
```

### Tools do Reminder Agent

```python
@tool
def create_reminder(
    user_id: int,
    title: str,
    scheduled_time: datetime,
    remind_before_minutes: int = 0,
    recurrence_type: str = "once",
    description: str = None
) -> dict:
    """Cria um novo lembrete no banco de dados."""
    pass

@tool
def list_reminders(
    user_id: int,
    status: str = "active",
    limit: int = 10
) -> List[dict]:
    """Lista lembretes do usuário."""
    pass

@tool
def cancel_reminder(
    user_id: int,
    reminder_id: int
) -> bool:
    """Cancela um lembrete."""
    pass

@tool
def edit_reminder(
    user_id: int,
    reminder_id: int,
    updates: dict
) -> dict:
    """Edita um lembrete existente."""
    pass
```

### Exemplos de Interação

| Entrada do Usuário | Extração | Ação |
|---|---|---|
| "Me lembre amanhã às 19h que tenho reunião" | title: "reunião", scheduled: amanhã 19:00 | create_reminder |
| "Quero um lembrete diário às 8h para tomar remédio" | title: "tomar remédio", recurrence: "daily" | create_reminder |
| "Me avise 1 hora antes" | remind_before_minutes: 60 | update_reminder |
| "Quais são meus lembretes?" | - | list_reminders |
| "Cancela o lembrete da reunião" | - | cancel_reminder |

---

## 2. Finance Agent (Agente Financeiro)

### Responsabilidades
- Registrar receitas e despesas
- Categorização automática de gastos
- Consultar histórico financeiro
- Gerar relatórios detalhados
- Análise de padrões de gastos

### Prompts de Extração

```python
FINANCE_EXTRACTION_PROMPT = """
Você é um especialista em finanças pessoais.
Analise a mensagem e extraia informações financeiras.

Mensagem do usuário: {message}
Data atual: {current_date}

Categorias disponíveis:
- Alimentação (ifood, restaurantes, mercado)
- Transporte (uber, gasolina, manutenção)
- Moradia (aluguel, condomínio, contas)
- Saúde (farmácia, consultas, plano)
- Lazer (streaming, viagens, entretenimento)
- Educação (cursos, livros)
- Vestuário (roupas, calçados)
- Outros

Retorne um JSON:
{
    "type": "income|expense",
    "amount": número,
    "description": "descrição",
    "category": "categoria apropriada",
    "transaction_date": "YYYY-MM-DD",
    "is_recurring": boolean,
    "tags": ["tag1", "tag2"]
}

Regras:
1. "gastei", "paguei", "comprei" → expense
2. "recebi", "ganhei", "entrou" → income
3. Se não especificar data, usar hoje
4. Detectar categoria automaticamente
"""
```

### Prompts de Consulta

```python
FINANCE_QUERY_PROMPT = """
O usuário está consultando informações financeiras.
Analise o que ele quer saber.

Mensagem: {message}
Período atual: {current_period}

Determine:
{
    "query_type": "summary|detailed|comparison|category|trend",
    "period": "today|week|month|year|custom",
    "start_date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD",
    "category_filter": "categoria ou null",
    "type_filter": "income|expense|all"
}

Exemplos:
- "quanto gastei esse mês" → summary, month
- "gastos com uber" → category, category_filter: "Transporte"
- "detalhes de ontem" → detailed, period: yesterday
"""
```

### Tools do Finance Agent

```python
@tool
def create_transaction(
    user_id: int,
    type: str,
    amount: float,
    category: str,
    description: str = None,
    transaction_date: date = None,
    tags: List[str] = None
) -> dict:
    """Registra uma nova transação financeira."""
    pass

@tool
def get_financial_summary(
    user_id: int,
    period: str,
    start_date: date = None,
    end_date: date = None
) -> dict:
    """Retorna resumo financeiro do período."""
    pass

@tool
def get_transactions_by_category(
    user_id: int,
    category: str,
    period: str = "month"
) -> List[dict]:
    """Lista transações por categoria."""
    pass

@tool
def get_spending_trend(
    user_id: int,
    months: int = 6
) -> dict:
    """Analisa tendência de gastos."""
    pass
```

### Exemplos de Interação

| Entrada | Ação | Resposta Esperada |
|---|---|---|
| "Gastei 100 reais com limpeza do carro" | create_transaction(expense, 100, Transporte) | "✅ Registrado: R$100,00 em Transporte" |
| "Quanto gastei esse mês?" | get_financial_summary(month) | "Este mês: Receitas R$X, Despesas R$Y, Saldo R$Z" |
| "Detalha meus gastos" | get_transactions_by_category(all) | Lista detalhada por categoria |
| "Gastei muito com Uber?" | get_spending_trend + análise | Comparativo e análise |

---

## 3. Meeting Agent (Agente de Reuniões)

### Responsabilidades
- Processar áudios de reuniões
- Gerar transcrição completa
- Criar resumo executivo
- Extrair tópicos principais
- Identificar action items
- Listar participantes e decisões

### Prompts de Análise

```python
MEETING_ANALYSIS_PROMPT = """
Você é um especialista em análise de reuniões corporativas.
Analise a transcrição e extraia TODAS as informações relevantes.

Transcrição da reunião:
{transcription}

Retorne um JSON completo:
{
    "title": "título sugerido para a reunião",
    "summary": "resumo executivo de 2-3 parágrafos",
    "duration_estimate": "duração estimada em minutos",
    "key_topics": [
        {
            "topic": "nome do tópico",
            "summary": "breve resumo",
            "discussed_by": ["participante1", "participante2"]
        }
    ],
    "action_items": [
        {
            "task": "descrição da tarefa",
            "responsible": "responsável",
            "deadline": "prazo se mencionado",
            "priority": "high|medium|low"
        }
    ],
    "participants": [
        {
            "name": "nome ou identificação",
            "role": "papel na reunião se identificável"
        }
    ],
    "decisions": [
        {
            "decision": "decisão tomada",
            "context": "contexto da decisão"
        }
    ],
    "sentiment": "positivo|neutro|negativo",
    "keywords": ["palavra1", "palavra2", ...],
    "follow_up_needed": boolean,
    "next_steps": ["próximo passo 1", "próximo passo 2"]
}

Diretrizes:
1. Seja objetivo e profissional
2. Action items devem ser acionáveis
3. Identifique todos os participantes mencionados
4. Capture TODAS as decisões importantes
5. Keywords devem ser termos técnicos/relevantes
"""
```

### Tools do Meeting Agent

```python
@tool
def transcribe_audio(
    audio_path: str
) -> str:
    """Transcreve áudio usando Google Speech-to-Text."""
    pass

@tool
def analyze_meeting(
    transcription: str
) -> dict:
    """Analisa transcrição e extrai informações."""
    pass

@tool
def save_meeting(
    user_id: int,
    meeting_data: dict,
    audio_url: str = None
) -> dict:
    """Salva reunião no banco de dados."""
    pass

@tool
def get_meeting_history(
    user_id: int,
    limit: int = 10
) -> List[dict]:
    """Lista reuniões anteriores."""
    pass

@tool
def search_meetings(
    user_id: int,
    query: str
) -> List[dict]:
    """Busca em reuniões por palavra-chave."""
    pass
```

### Fluxo de Processamento de Reunião

```
1. RECEBIMENTO DO ÁUDIO
   │
   ├─▶ Download do áudio via WhatsApp
   ├─▶ Validar formato e tamanho
   └─▶ Converter para formato compatível
   │
2. TRANSCRIÇÃO
   │
   ├─▶ Google Speech-to-Text
   ├─▶ Identificação de idioma
   └─▶ Transcrição completa
   │
3. ANÁLISE
   │
   ├─▶ Enviar para Gemini
   ├─▶ Extração de informações
   └─▶ Estruturação JSON
   │
4. ARMAZENAMENTO
   │
   ├─▶ Salvar Meeting no banco
   ├─▶ Vincular ao usuário
   └─▶ Indexar para busca
   │
5. RESPOSTA
   │
   └─▶ Resumo formatado para WhatsApp
```

### Formato de Resposta

```
📋 *Resumo da Reunião*

📌 *Título:* Alinhamento de Sprint Q1

*Resumo:*
Reunião de planejamento do primeiro sprint do trimestre...

📍 *Tópicos Principais:*
• Revisão de backlog
• Definição de prioridades
• Alocação de recursos

✅ *Action Items:*
• João: Finalizar documentação (até sexta)
• Maria: Revisar estimativas (amanhã)
• Carlos: Agendar follow-up com cliente

👥 *Participantes:* João, Maria, Carlos

💡 *Decisões:*
• Priorizar feature de exportação
• Adiar refatoração para próximo sprint

📊 *Sentimento:* Positivo
```

---

## Sistema de Memória dos Agentes

### Estrutura de Memória por Usuário

```python
class UserMemory:
    """Memória persistente por usuário."""
    
    # Preferências aprendidas
    preferences: dict = {
        "default_reminder_time": "09:00",
        "preferred_categories": ["Transporte", "Alimentação"],
        "communication_style": "informal",
        "timezone": "America/Sao_Paulo"
    }
    
    # Contexto de conversa
    conversation_context: list = [
        {"role": "user", "content": "...", "timestamp": "..."},
        {"role": "assistant", "content": "...", "timestamp": "..."}
    ]
    
    # Informações relevantes extraídas
    learned_facts: dict = {
        "name": "João",
        "work_schedule": "9h-18h",
        "recurring_expenses": ["aluguel", "netflix"]
    }
    
    # Histórico de interações
    interaction_history: dict = {
        "reminders_created": 15,
        "finances_registered": 42,
        "meetings_analyzed": 3
    }
```

### Recuperação de Contexto

```python
def get_context_for_agent(user_id: int, agent_type: str) -> dict:
    """Recupera contexto relevante para o agente."""
    
    memory = get_user_memory(user_id)
    
    context = {
        "user_name": memory.learned_facts.get("name"),
        "timezone": memory.preferences.get("timezone"),
        "last_messages": memory.conversation_context[-5:],
        "relevant_history": get_relevant_history(agent_type)
    }
    
    return context
```

---

## Configuração do LangGraph

### Estado do Grafo

```python
class AgentState(TypedDict):
    """Estado compartilhado entre nós do grafo."""
    
    # Mensagens da conversa
    messages: Annotated[Sequence[BaseMessage], operator.add]
    
    # Identificação
    user_id: int
    session_id: str
    
    # Classificação
    intent: str
    confidence: float
    
    # Dados extraídos
    entities: dict
    
    # Contexto do usuário
    context: dict
    
    # Próxima ação
    next_action: str
    
    # Memória da conversa
    memory: dict
```

### Nós do Grafo

```python
def create_agent_graph():
    workflow = StateGraph(AgentState)
    
    # Nós principais
    workflow.add_node("classifier", classify_intent)
    workflow.add_node("reminder_agent", handle_reminder)
    workflow.add_node("finance_agent", handle_finance)
    workflow.add_node("meeting_agent", handle_meeting)
    workflow.add_node("general_chat", handle_general)
    workflow.add_node("response_generator", generate_response)
    workflow.add_node("memory_updater", update_memory)
    
    # Entry point
    workflow.set_entry_point("classifier")
    
    # Routing condicional
    workflow.add_conditional_edges(
        "classifier",
        route_by_intent,
        {
            "reminder": "reminder_agent",
            "finance": "finance_agent",
            "meeting": "meeting_agent",
            "general": "general_chat"
        }
    )
    
    # Todos passam pelo gerador de resposta
    for agent in ["reminder_agent", "finance_agent", "meeting_agent", "general_chat"]:
        workflow.add_edge(agent, "response_generator")
    
    # Atualiza memória antes de finalizar
    workflow.add_edge("response_generator", "memory_updater")
    workflow.add_edge("memory_updater", END)
    
    return workflow.compile()
```
