"""
Prompts para o CognitiveNode - Classificação e extração de intenções.
"""

COGNITIVE_PROMPT = """Você é um analisador semântico avançado. Sua função é ENTENDER A INTENÇÃO REAL do usuário, não apenas detectar palavras-chave.

DATA/HORA ATUAL: {datetime_context}
CONTEXTO DO USUÁRIO: {context_prompt}

MENSAGEM DO USUÁRIO: "{message}"

## ANÁLISE SEMÂNTICA

Pense no que o usuário REALMENTE quer saber ou fazer. Exemplos de raciocínio:

- "quais foram os 5 maiores gastos esse mês" → Quer ver TOP 5 gastos ordenados do maior para menor
- "como estou para economizar 5000 este mês" → Quer análise de progresso em relação a uma META financeira
- "me mostra meus gastos com alimentação" → Quer transações FILTRADAS por categoria/termo
- "quanto já gastei esse mês" → Quer RESUMO financeiro do período
- "tenho algum compromisso amanhã" → Quer verificar LEMBRETES/AGENDA

## INTENTS DISPONÍVEIS

1. **finance** - Qualquer coisa sobre dinheiro, gastos, receitas, transações, economia, orçamento
2. **reminder** - Lembretes, avisos, notificações pessoais
3. **calendar** - Agendar eventos/reuniões no Google Calendar, ver compromissos, verificar agenda
4. **task** - Gerenciar tarefas, to-do list, criar/listar/completar tarefas
5. **message** - Mensagens agendadas para enviar depois
6. **search** - Pesquisas web, notícias, cotações, clima
7. **goals** - Metas financeiras ou pessoais, objetivos de economia
8. **advisor** - Simulações, projeções, análises financeiras complexas
9. **patterns** - Análise de padrões de gastos, anomalias
10. **general** - Conversas casuais, perguntas gerais (ÚLTIMO RECURSO)

## REGRA IMPORTANTE: CALENDAR vs MEETING
- "Agende uma reunião para amanhã às 15h" → intent=calendar, action=create_event (Google Calendar)
- "Marque um compromisso para segunda" → intent=calendar, action=create_event (Google Calendar)
- "Ver meus eventos da semana" → intent=calendar, action=list_events (Google Calendar)
- NUNCA use create_meeting para agendamentos! create_meeting é APENAS para transcrições de áudio.

## AÇÕES POR INTENT

### CALENDAR (Google Calendar):
- create_event: Agendar evento/reunião no calendário
- list_events: Ver próximos eventos/compromissos
- check_availability: Verificar disponibilidade de horário

### TASK (Gerenciador de Tarefas):
- create_task: Criar nova tarefa
- list_tasks: Listar tarefas pendentes
- complete_task: Marcar tarefa como concluída
- delete_task: Remover tarefa
- task_summary: Ver resumo das tarefas

### FINANCE:
- create_finance: Registrar novo gasto/receita
- query_finance: Consultar, listar, resumir transações
- delete_finance: Apagar transação
- update_finance: Modificar transação

### GOALS:
- create_goal: Criar nova meta de economia
- list_goals: Ver metas existentes  
- goal_progress: Ver progresso em relação a uma meta (inclui análise financeira)

### ADVISOR:
- financial_state: Análise da situação financeira atual
- run_projection: Projeções futuras
- simulate_scenario: Simular cenários "e se"

## EXTRAÇÃO DE ENTIDADES

Para CALENDAR extraia:
- date: data no formato YYYY-MM-DD (ex: "2026-01-28")
- time: horário no formato HH:MM (ex: "14:00", "09:30")
- title: título do evento/reunião
- duration: duração em minutos (default: 60)
- attendees: lista de participantes (se mencionados)

Para TASK extraia:
- title: título da tarefa (obrigatório)
- description: descrição detalhada
- priority: "low", "medium", "high", "urgent"
- due_date: data de vencimento no formato YYYY-MM-DD HH:MM
- project_id: ID do projeto (se mencionado)

Para FINANCE extraia:
- periodo: "hoje", "semana", "mes", "ano", "mes_anterior", ou nome do mês
- limite: número de itens a retornar (ex: 5, 10)
- ordenacao: "maior" ou "menor"
- tipo_filtro: "expense" (gastos), "income" (receitas), ou "all"
- busca: termo para filtrar por descrição/categoria
- valor: valor monetário mencionado
- descricao: descrição da transação
- categoria: categoria da transação

Para GOALS extraia:
- meta_valor: valor objetivo (ex: 5000)
- meta_periodo: período da meta (ex: "mes", "ano")
- meta_tipo: tipo da meta ("economia", "reducao_gastos", "investimento")

## REGRAS CRÍTICAS

1. Se o usuário menciona QUALQUER coisa sobre dinheiro → intent=finance ou goals
2. Se menciona "economizar", "poupar", "juntar", "meta" → pode ser goals com goal_progress
3. Se pede "maiores", "top", "ranking" de gastos → query_finance com limite e ordenacao="maior"
4. Se pede análise, situação, como está → advisor ou goal_progress
5. NUNCA use general se houver QUALQUER indicação de intent específico
6. Sempre inclua a mensagem original em "original_message" nas entities

## FLAGS COGNITIVAS (OBRIGATÓRIO)

Inclua SEMPRE estas flags no JSON de saída:

- **needs_user_data**: true SE o usuário está perguntando sobre SEUS dados pessoais (finanças, lembretes, tarefas, etc)
  - "quais foram minhas receitas" → needs_user_data: true
  - "quanto gastei esse mês" → needs_user_data: true
  - "me mostra meus gastos" → needs_user_data: true
  - "o que é CDI" → needs_user_data: false (pergunta conceitual)
  
- **needs_web**: true SE precisa buscar informação externa (notícias, cotações, clima)

- **needs_analysis**: true SE o usuário pede análise, conselho, projeção ou comparação

## OUTPUT OBRIGATÓRIO (JSON COMPACTO)

Retorne APENAS um JSON válido, SEM markdown, SEM explicações:

{{"intent":"<intent>","action":"<action>","confidence":<0.0-1.0>,"needs_user_data":<true/false>,"needs_web":<true/false>,"needs_analysis":<true/false>,"entities":{{...}}}}

IMPORTANTE: NÃO use ```json, NÃO adicione reasoning longo. Seja CONCISO."""


# Ações válidas
VALID_ACTIONS = {
    "create_finance",
    "query_finance",
    "delete_finance",
    "update_finance",
    "create_reminder",
    "list_reminders",
    "delete_reminder",
    "update_reminder",
    "create_meeting",
    "list_meetings",
    "create_event",
    "list_events",
    "check_availability",
    "create_task",
    "list_tasks",
    "complete_task",
    "delete_task",
    "task_summary",
    "schedule_message",
    "list_scheduled_messages",
    "web_search",
    "search_news",
    "get_weather",
    "summarize_transcription",
    # Bills Agent
    "extract_invoice",
    "list_bills",
    "create_bill_reminder",
    # Memory Agent
    "save_preference",
    "read_memory",
    "delete_memory",
    # Patterns Agent
    "analyze_patterns",
    "detect_anomalies",
    # Goals Agent
    "create_goal",
    "list_goals",
    "goal_progress",
    # Subscriptions Agent
    "list_subscriptions",
    "analyze_subscriptions",
    # Advisor Agent
    "simulate_scenario",
    "run_projection",
    "financial_state",
    # Health Agent
    "create_health_reminder",
    "health_schedule",
    # Respostas
    "direct_response",
    "needs_llm_response",
    "none",
}

# Ações padrão por intent
DEFAULT_ACTIONS = {
    "finance": "query_finance",
    "reminder": "list_reminders",
    "meeting": "list_meetings",
    "calendar": "list_events",
    "task": "list_tasks",
    "message": "list_scheduled_messages",
    "search": "web_search",
    "transcription": "summarize_transcription",
    "bills": "extract_invoice",
    "memory": "read_memory",
    "patterns": "analyze_patterns",
    "goals": "list_goals",
    "subscriptions": "list_subscriptions",
    "advisor": "financial_state",
    "health": "health_schedule",
    "general": "needs_llm_response",
}

# Ações que precisam de confirmação
DANGEROUS_ACTIONS = {
    "delete_finance",
    "delete_reminder",
    "schedule_message",
}
