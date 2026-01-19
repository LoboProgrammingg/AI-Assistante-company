# 🌐 API Endpoints

## Visão Geral da API

Base URL: `/api/v1`

A API segue os princípios REST e utiliza:
- **JSON** para requests/responses
- **JWT** para autenticação
- **Paginação** para listagens
- **Códigos HTTP** padronizados

---

## Autenticação

### Headers Obrigatórios
```
Authorization: Bearer <jwt_token>
Content-Type: application/json
```

### Fluxo de Autenticação
1. Usuário se autentica via WhatsApp
2. Sistema gera session_id único
3. Frontend solicita token JWT usando session_id
4. Token usado em todas as requisições

---

## Webhooks (Sem autenticação - Validação Twilio)

### POST `/webhook/whatsapp`
Recebe mensagens do WhatsApp via Twilio.

**Request (form-data):**
```
MessageSid: SMxxxxxxxx
From: whatsapp:+5511999999999
To: whatsapp:+14155238886
Body: Texto da mensagem
NumMedia: 0
MediaContentType0: audio/ogg
MediaUrl0: https://api.twilio.com/...
ProfileName: Nome do Usuário
```

**Response:**
```
Status: 200 OK
```

### POST `/webhook/whatsapp/status`
Recebe callbacks de status de mensagens.

**Request (form-data):**
```
MessageSid: SMxxxxxxxx
MessageStatus: delivered|read|failed
ErrorCode: (opcional)
ErrorMessage: (opcional)
```

---

## Endpoints de Usuários

### GET `/api/v1/users/me`
Retorna dados do usuário autenticado.

**Response:**
```json
{
    "id": 1,
    "phone_number": "+5511999999999",
    "session_id": "wa_+5511999999999_1234567890",
    "name": "João Silva",
    "timezone": "America/Sao_Paulo",
    "language": "pt-BR",
    "preferences": {
        "default_reminder_time": "09:00",
        "notification_sound": true
    },
    "created_at": "2024-01-15T10:00:00Z",
    "last_interaction": "2024-01-20T15:30:00Z"
}
```

### PUT `/api/v1/users/me`
Atualiza dados do usuário.

**Request:**
```json
{
    "name": "João Silva",
    "timezone": "America/Sao_Paulo",
    "preferences": {
        "default_reminder_time": "08:00"
    }
}
```

### GET `/api/v1/users/me/stats`
Retorna estatísticas do usuário.

**Response:**
```json
{
    "total_reminders": 45,
    "active_reminders": 12,
    "total_transactions": 156,
    "total_meetings": 8,
    "member_since": "2024-01-15",
    "last_activity": "2024-01-20T15:30:00Z"
}
```

---

## Endpoints de Lembretes

### GET `/api/v1/reminders`
Lista lembretes do usuário.

**Query Parameters:**
| Param | Tipo | Default | Descrição |
|-------|------|---------|-----------|
| status | string | "active" | active, completed, all |
| recurrence | string | null | once, daily, weekly, etc |
| from_date | date | null | Data inicial |
| to_date | date | null | Data final |
| page | int | 1 | Página |
| limit | int | 20 | Itens por página |

**Response:**
```json
{
    "items": [
        {
            "id": 1,
            "title": "Reunião com cliente",
            "description": "Discutir proposta comercial",
            "scheduled_time": "2024-01-20T19:00:00-03:00",
            "remind_before_minutes": 60,
            "actual_reminder_time": "2024-01-20T18:00:00-03:00",
            "recurrence_type": "once",
            "is_active": true,
            "is_completed": false,
            "notified": false,
            "created_at": "2024-01-15T10:00:00Z"
        }
    ],
    "total": 45,
    "page": 1,
    "pages": 3,
    "has_next": true
}
```

### POST `/api/v1/reminders`
Cria novo lembrete.

**Request:**
```json
{
    "title": "Reunião com cliente",
    "description": "Discutir proposta comercial",
    "scheduled_time": "2024-01-20T19:00:00",
    "remind_before_minutes": 60,
    "recurrence_type": "once",
    "recurrence_config": null
}
```

**Response:**
```json
{
    "id": 1,
    "title": "Reunião com cliente",
    "scheduled_time": "2024-01-20T19:00:00-03:00",
    "actual_reminder_time": "2024-01-20T18:00:00-03:00",
    "recurrence_type": "once",
    "is_active": true,
    "created_at": "2024-01-15T10:00:00Z"
}
```

### GET `/api/v1/reminders/{reminder_id}`
Retorna detalhes de um lembrete.

### PUT `/api/v1/reminders/{reminder_id}`
Atualiza um lembrete.

**Request:**
```json
{
    "title": "Reunião com cliente - URGENTE",
    "remind_before_minutes": 30
}
```

### DELETE `/api/v1/reminders/{reminder_id}`
Remove um lembrete (soft delete - marca como inativo).

### POST `/api/v1/reminders/{reminder_id}/complete`
Marca lembrete como concluído.

### GET `/api/v1/reminders/upcoming`
Retorna lembretes das próximas 24 horas.

---

## Endpoints Financeiros

### GET `/api/v1/finances`
Lista transações financeiras.

**Query Parameters:**
| Param | Tipo | Default | Descrição |
|-------|------|---------|-----------|
| type | string | "all" | income, expense, all |
| category | string | null | Categoria específica |
| from_date | date | null | Data inicial |
| to_date | date | null | Data final |
| min_amount | float | null | Valor mínimo |
| max_amount | float | null | Valor máximo |
| page | int | 1 | Página |
| limit | int | 50 | Itens por página |

**Response:**
```json
{
    "items": [
        {
            "id": 1,
            "type": "expense",
            "amount": 100.00,
            "description": "Limpeza do carro",
            "category": {
                "id": 5,
                "name": "Transporte",
                "icon": "🚗",
                "color": "#3498db"
            },
            "transaction_date": "2024-01-20",
            "is_recurring": false,
            "tags": ["carro", "manutenção"],
            "created_at": "2024-01-20T10:00:00Z"
        }
    ],
    "total": 156,
    "page": 1,
    "pages": 4
}
```

### POST `/api/v1/finances`
Registra nova transação.

**Request:**
```json
{
    "type": "expense",
    "amount": 100.00,
    "description": "Limpeza do carro",
    "category_id": 5,
    "transaction_date": "2024-01-20",
    "is_recurring": false,
    "tags": ["carro", "manutenção"]
}
```

### GET `/api/v1/finances/summary`
Retorna resumo financeiro.

**Query Parameters:**
| Param | Tipo | Default | Descrição |
|-------|------|---------|-----------|
| period | string | "month" | today, week, month, year, custom |
| from_date | date | null | Para period=custom |
| to_date | date | null | Para period=custom |

**Response:**
```json
{
    "period": {
        "start": "2024-01-01",
        "end": "2024-01-31",
        "label": "Janeiro 2024"
    },
    "summary": {
        "total_income": 13000.00,
        "total_expenses": 8000.00,
        "balance": 5000.00,
        "savings_rate": 38.46
    },
    "by_category": [
        {
            "category": "Moradia",
            "total": 3000.00,
            "percentage": 37.5,
            "transactions_count": 1
        },
        {
            "category": "Transporte",
            "total": 860.00,
            "percentage": 10.75,
            "transactions_count": 15
        }
    ],
    "comparison": {
        "previous_period_expenses": 7500.00,
        "change_percentage": 6.67,
        "trend": "up"
    }
}
```

### GET `/api/v1/finances/categories`
Lista categorias disponíveis.

**Response:**
```json
{
    "expense_categories": [
        {"id": 1, "name": "Alimentação", "icon": "🍔", "color": "#e74c3c"},
        {"id": 2, "name": "Transporte", "icon": "🚗", "color": "#3498db"}
    ],
    "income_categories": [
        {"id": 10, "name": "Salário", "icon": "💰", "color": "#27ae60"},
        {"id": 11, "name": "Freelance", "icon": "💻", "color": "#9b59b6"}
    ]
}
```

### GET `/api/v1/finances/trends`
Retorna tendências de gastos.

**Query Parameters:**
| Param | Tipo | Default | Descrição |
|-------|------|---------|-----------|
| months | int | 6 | Número de meses para análise |
| category | string | null | Categoria específica |

**Response:**
```json
{
    "monthly_data": [
        {"month": "2024-01", "income": 13000, "expenses": 8000},
        {"month": "2023-12", "income": 13000, "expenses": 7500}
    ],
    "average_monthly_expense": 7750.00,
    "highest_expense_month": "2024-01",
    "category_trends": [
        {
            "category": "Transporte",
            "trend": "increasing",
            "average": 850.00,
            "last_month": 920.00
        }
    ]
}
```

### PUT `/api/v1/finances/{finance_id}`
Atualiza transação.

### DELETE `/api/v1/finances/{finance_id}`
Remove transação.

---

## Endpoints de Reuniões

### GET `/api/v1/meetings`
Lista reuniões do usuário.

**Query Parameters:**
| Param | Tipo | Default | Descrição |
|-------|------|---------|-----------|
| from_date | date | null | Data inicial |
| to_date | date | null | Data final |
| search | string | null | Busca em título/conteúdo |
| page | int | 1 | Página |
| limit | int | 20 | Itens por página |

**Response:**
```json
{
    "items": [
        {
            "id": 1,
            "title": "Sprint Planning Q1",
            "date": "2024-01-15T14:00:00Z",
            "duration_minutes": 45,
            "summary": "Reunião de planejamento do sprint...",
            "key_topics": ["backlog", "prioridades", "estimativas"],
            "action_items_count": 5,
            "participants_count": 3,
            "sentiment": "positivo",
            "created_at": "2024-01-15T15:00:00Z"
        }
    ],
    "total": 8,
    "page": 1,
    "pages": 1
}
```

### GET `/api/v1/meetings/{meeting_id}`
Retorna detalhes completos de uma reunião.

**Response:**
```json
{
    "id": 1,
    "title": "Sprint Planning Q1",
    "date": "2024-01-15T14:00:00Z",
    "duration_minutes": 45,
    "transcription": "Transcrição completa da reunião...",
    "summary": "Resumo executivo...",
    "key_topics": [
        {
            "topic": "Revisão de backlog",
            "summary": "Foram revisados 15 itens...",
            "discussed_by": ["João", "Maria"]
        }
    ],
    "action_items": [
        {
            "task": "Finalizar documentação",
            "responsible": "João",
            "deadline": "2024-01-20",
            "priority": "high",
            "status": "pending"
        }
    ],
    "participants": [
        {"name": "João", "role": "Tech Lead"},
        {"name": "Maria", "role": "Product Owner"}
    ],
    "decisions": [
        {
            "decision": "Priorizar feature de exportação",
            "context": "Cliente solicitou urgência"
        }
    ],
    "sentiment": "positivo",
    "keywords": ["sprint", "backlog", "exportação"],
    "audio_url": "https://...",
    "created_at": "2024-01-15T15:00:00Z"
}
```

### POST `/api/v1/meetings`
Cria nova reunião manualmente.

**Request:**
```json
{
    "title": "Reunião de alinhamento",
    "date": "2024-01-20T10:00:00",
    "summary": "Resumo manual...",
    "key_topics": ["tema1", "tema2"],
    "action_items": [
        {
            "task": "Fazer X",
            "responsible": "João"
        }
    ]
}
```

### POST `/api/v1/meetings/analyze`
Envia áudio para análise (via API, não WhatsApp).

**Request (multipart/form-data):**
```
audio: <arquivo de áudio>
```

**Response:**
```json
{
    "id": 2,
    "title": "Reunião Analisada",
    "summary": "Resumo gerado pela IA...",
    "status": "completed"
}
```

### PUT `/api/v1/meetings/{meeting_id}/action-items/{item_id}`
Atualiza status de action item.

**Request:**
```json
{
    "status": "completed"
}
```

### GET `/api/v1/meetings/search`
Busca em todas as reuniões.

**Query Parameters:**
| Param | Tipo | Descrição |
|-------|------|-----------|
| q | string | Termo de busca |

**Response:**
```json
{
    "results": [
        {
            "meeting_id": 1,
            "title": "Sprint Planning",
            "highlights": ["...termo buscado..."],
            "relevance_score": 0.95
        }
    ],
    "total": 3
}
```

---

## Endpoints de Mensagens

### GET `/api/v1/messages`
Lista histórico de mensagens.

**Query Parameters:**
| Param | Tipo | Default |
|-------|------|---------|
| from_date | date | null |
| to_date | date | null |
| intent | string | null |
| page | int | 1 |
| limit | int | 50 |

**Response:**
```json
{
    "items": [
        {
            "id": 1,
            "message_type": "text",
            "content": "Me lembre amanhã às 19h",
            "direction": "incoming",
            "intent": "reminder",
            "ai_response": "Lembrete agendado!",
            "created_at": "2024-01-20T10:00:00Z"
        }
    ],
    "total": 200,
    "page": 1
}
```

---

## Códigos de Erro

| Código | Descrição |
|--------|-----------|
| 400 | Bad Request - Dados inválidos |
| 401 | Unauthorized - Token inválido/expirado |
| 403 | Forbidden - Sem permissão |
| 404 | Not Found - Recurso não encontrado |
| 422 | Unprocessable Entity - Erro de validação |
| 429 | Too Many Requests - Rate limit excedido |
| 500 | Internal Server Error |

**Formato de Erro:**
```json
{
    "detail": {
        "code": "VALIDATION_ERROR",
        "message": "Descrição do erro",
        "field": "campo_com_erro"
    }
}
```

---

## Rate Limiting

| Endpoint | Limite |
|----------|--------|
| Webhooks | Sem limite (Twilio) |
| API REST | 100 req/min por usuário |
| Análise de áudio | 10 req/hora por usuário |

---

## Paginação

Todos os endpoints de listagem seguem o padrão:

**Request:**
```
GET /api/v1/reminders?page=2&limit=20
```

**Response:**
```json
{
    "items": [...],
    "total": 100,
    "page": 2,
    "pages": 5,
    "has_next": true,
    "has_prev": true
}
```
