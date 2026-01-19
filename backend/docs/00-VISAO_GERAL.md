# 🎯 Visão Geral do Projeto - WhatsApp AI Assistant

## Objetivo

Criar um sistema profissional de assistente pessoal via WhatsApp com IA, focado em três funcionalidades principais:

1. **Agenda/Lembretes Inteligentes**
2. **Controle Financeiro Completo**
3. **Análise de Reuniões**

---

## Stack Tecnológica

### Backend
- **Framework**: FastAPI 0.109
- **IA/LLM**: LangGraph + Google Gemini 2.5 Flash
- **Database**: PostgreSQL 16
- **Cache**: Redis 7
- **ORM**: SQLAlchemy 2.0
- **WhatsApp**: Twilio API
- **Scheduler**: APScheduler / Asyncio

### Frontend (Futuro)
- **Framework**: React 18 + TypeScript
- **Styling**: TailwindCSS 3
- **Charts**: Recharts
- **Icons**: Lucide React
- **Build**: Vite

---

## Arquitetura Geral

```
┌─────────────────────────────────────────────────────────────┐
│                     WhatsApp User                            │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │    Twilio    │
                    │  (WhatsApp   │
                    │   Business)  │
                    └──────┬───────┘
                           │
                           ▼
              ┌────────────────────────┐
              │    FastAPI Backend     │
              │  - Webhooks Handler    │
              │  - Background Tasks    │
              │  - REST API            │
              └────────┬───────────────┘
                       │
           ┌───────────┴───────────┐
           ▼                       ▼
    ┌─────────────┐         ┌──────────────┐
    │  LangGraph  │         │  PostgreSQL  │
    │  Orchestrator│◄───────┤   Database   │
    │             │         │              │
    └──────┬──────┘         └──────────────┘
           │
    ┌──────┴──────┐
    ▼      ▼      ▼
┌───────┬───────┬───────┐
│Reminder│Finance│Meeting│   ← Agentes Especializados
│ Agent  │ Agent │ Agent │
└───────┴───────┴───────┘
           │
           ▼
    ┌─────────────┐
    │  Scheduler  │
    │   Worker    │
    └─────────────┘
```

---

## Fluxo de Dados

### 1. Recebimento de Mensagem
```
User → WhatsApp → Twilio → Webhook → FastAPI → Background Task
```

### 2. Processamento
```
Message → Intent Classifier → Agent Específico → Action Handler
```

### 3. Resposta
```
Response Generator → WhatsApp Service → Twilio → User
```

---

## Princípios de Design

1. **Clean Architecture** - Separação clara entre camadas
2. **DDD (Domain-Driven Design)** - Domínios bem definidos
3. **SOLID** - Princípios aplicados em todo o código
4. **Event-Driven** - Processamento assíncrono
5. **Memory-First** - Memória persistente por usuário

---

## Casos de Uso Principais

### 1. Lembretes
- Criar lembrete único ou recorrente
- Configurar antecedência de notificação
- Receber notificação automática no horário

### 2. Finanças
- Registrar gastos e receitas
- Categorização automática
- Consultar histórico (diário/semanal/mensal/anual)
- Relatórios detalhados

### 3. Reuniões
- Enviar áudio de reunião
- Receber transcrição e resumo
- Extração de tópicos e action items
- Identificação de participantes

---

## Estrutura de Diretórios

```
backend/
├── app/
│   ├── ai/                    # Agentes e LangGraph
│   │   ├── agents/            # Agentes especializados
│   │   ├── tools/             # Ferramentas dos agentes
│   │   └── graph.py           # Orquestrador principal
│   ├── api/                   # Endpoints REST
│   ├── models/                # SQLAlchemy models
│   ├── schemas/               # Pydantic schemas
│   ├── services/              # Lógica de negócio
│   ├── utils/                 # Utilitários
│   ├── workers/               # Background workers
│   ├── config.py              # Configurações
│   ├── database.py            # Conexão DB
│   └── main.py                # Entry point
├── alembic/                   # Migrations
├── docs/                      # Documentação
├── tests/                     # Testes
├── requirements.txt
└── Dockerfile
```

---

## Status Atual do Projeto

### ✅ Implementado
- Estrutura base do projeto
- Configuração (`config.py`)
- Modelos do banco de dados (`models.py`)
- WhatsApp Service (`whatsapp_service.py`)
- LangGraph básico (`graph.py`)
- Scheduler de lembretes (`scheduler.py`)
- Main com webhooks (`main.py`)

### ⏳ Pendente
- Agentes especializados (Reminder, Finance, Meeting)
- Ferramentas dos agentes
- Services completos
- Schemas Pydantic
- Endpoints REST API
- Utils (Audio Processor, Timezone Helper)
- Testes
- Frontend Dashboard

---

## Próximos Passos

Ver documentos específicos:
- `01-ESTRUTURA_ARQUITETURA.md` - Arquitetura detalhada
- `02-AGENTES.md` - Especificação dos agentes
- `03-ENDPOINTS.md` - API REST
- `04-MODELOS.md` - Modelos e schemas
- `05-SERVICES.md` - Camada de serviços
- `06-MEMORIA.md` - Sistema de memória
- `07-SCHEDULER.md` - Agendador de tarefas
- `08-INTEGRAÇÕES.md` - APIs externas
- `09-IMPLEMENTACAO.md` - Ordem de implementação
