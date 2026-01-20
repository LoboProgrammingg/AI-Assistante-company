# I.R.I.S - Intelligent Retrieval & Insight System

## Visão Geral

**I.R.I.S** (Intelligent Retrieval & Insight System) é uma assistente pessoal inteligente projetada para ajudar usuários a gerenciar suas atividades diárias através de uma interface conversacional natural via WhatsApp.

## Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                         I.R.I.S                                  │
│              Intelligent Retrieval & Insight System              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │  Classifier  │───▶│   Router     │───▶│   Agents     │      │
│  │   (Intent)   │    │  (LangGraph) │    │ Especializados│     │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                                       │               │
│         │         ┌─────────────────┐           │               │
│         └────────▶│  Memory Manager │◀──────────┘               │
│                   │  (Long-term)    │                           │
│                   └─────────────────┘                           │
│                           │                                     │
│                   ┌───────┴───────┐                            │
│                   ▼               ▼                            │
│            ┌──────────┐    ┌──────────┐                        │
│            │   RAG    │    │  Cache   │                        │
│            │ Embeddings│   │ Service  │                        │
│            └──────────┘    └──────────┘                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Agentes Especializados

### 1. ReminderAgent ⏰
- Criação e gerenciamento de lembretes
- Suporte a múltiplos lembretes em uma mensagem
- Recorrência (diário, semanal, mensal)
- Notificações com antecedência configurável

### 2. FinanceAgent 💰
- Registro de gastos e receitas
- Categorização automática inteligente
- Consultas por período e categoria
- Análise de padrões de gastos

### 3. MeetingAgent 📋
- Agendamento de reuniões
- Análise de transcrições de áudio
- Extração de action items
- Identificação de participantes e decisões

### 4. ContactAgent 👥
- Gerenciamento de contatos por grupos
- Envio de mensagens agendadas
- Broadcast para grupos
- Organização flexível de grupos

## Memória e Contexto

### Memória de Curto Prazo
- Histórico de conversa (últimas 15-20 mensagens)
- Contexto pendente (lembretes/contatos aguardando confirmação)
- Cache de classificação de intenções

### Memória de Longo Prazo
- Fatos aprendidos (nome, profissão, família)
- Preferências de comunicação
- Análise comportamental do usuário
- Histórico de ações confirmadas

### RAG (Retrieval-Augmented Generation)
- Embeddings de documentos do usuário
- Busca semântica por contexto relevante
- Enriquecimento de respostas com dados históricos

## Integração WhatsApp

- Twilio API para envio/recebimento
- Suporte a mensagens de texto e áudio
- Transcrição de áudio via Whisper
- Formatação específica para WhatsApp (*negrito*, _itálico_)

## Tecnologias

| Componente | Tecnologia |
|------------|------------|
| Backend | FastAPI + Python 3.11 |
| IA | LangGraph + Google Gemini |
| Banco de Dados | PostgreSQL |
| Cache | Redis (opcional) |
| Embeddings | Google Generative AI |
| WhatsApp | Twilio API |
| Deploy | Railway |

## Estrutura de Arquivos (Reorganizada)

```
app/ai/
├── agents/
│   ├── prompts/           # Prompts centralizados
│   │   ├── classifier_prompts.py
│   │   ├── response_prompts.py
│   │   ├── reminder_prompts.py
│   │   ├── finance_prompts.py
│   │   ├── meeting_prompts.py
│   │   └── contact_prompts.py
│   ├── constants/         # Constantes e configurações
│   │   ├── finance_constants.py
│   │   └── reminder_constants.py
│   ├── base_agent.py      # Classe base
│   ├── reminder_agent.py  # Agente de lembretes
│   ├── finance_agent.py   # Agente financeiro
│   ├── meeting_agent.py   # Agente de reuniões
│   └── contact_agent.py   # Agente de contatos
├── graph.py               # Orquestrador LangGraph
├── memory.py              # Gerenciador de memória
├── iris_identity.py       # Identidade da IRIS
└── tools/                 # Ferramentas auxiliares
```
