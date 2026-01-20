# IRIS - Changelog Consolidado

## Janeiro 2025

Este documento consolida todas as melhorias implementadas na IRIS.

---

## 1. Visão Geral da IRIS

**I.R.I.S** (Intelligent Retrieval & Insight System) é uma assistente pessoal inteligente via WhatsApp.

### Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                         I.R.I.S                                  │
│              Intelligent Retrieval & Insight System              │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │  Classifier  │───▶│   Router     │───▶│   Agents     │      │
│  │   (Intent)   │    │  (LangGraph) │    │ Especializados│     │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                                       │               │
│         │         ┌─────────────────┐           │               │
│         └────────▶│  Memory Manager │◀──────────┘               │
│                   │  (Long-term)    │                           │
│                   └─────────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
```

### Agentes Especializados

| Agente | Função |
|--------|--------|
| ReminderAgent ⏰ | Lembretes e notificações |
| FinanceAgent 💰 | Gastos, receitas, análises |
| MeetingAgent 📋 | Reuniões e transcrições |
| ContactAgent 👥 | Contatos e grupos |

---

## 2. Estrutura do Projeto

```
app/
├── ai/
│   ├── agents/
│   │   ├── prompts/          # Prompts centralizados
│   │   ├── constants/        # Configurações
│   │   └── *_agent.py        # Agentes especializados
│   ├── tools/                # Tools com Pydantic schemas
│   ├── graph.py              # Grafo v1 (legado)
│   ├── graph_v2.py           # Grafo v2 (atual)
│   ├── state.py              # Estado tipado
│   ├── checkpointer.py       # Persistência PostgreSQL
│   └── memory.py             # Gerenciador de memória
├── core/
│   ├── security.py           # Módulo de segurança
│   ├── rate_limiter.py       # Rate limiting
│   ├── input_sanitizer.py    # Sanitização de inputs
│   ├── cache_manager.py      # Cache unificado
│   └── exceptions.py         # Exceções personalizadas
├── middleware/
│   └── security_middleware.py # Headers de segurança
└── services/                 # Serviços de negócio
```

---

## 3. Melhorias de Segurança

### Implementadas

| Recurso | Status | Descrição |
|---------|--------|-----------|
| Rate Limiting | ✅ | 60 req/min, 1000 req/hora |
| Input Sanitization | ✅ | Proteção XSS, SQL Injection |
| Security Headers | ✅ | X-Frame-Options, CSP, etc |
| Password Validation | ✅ | Força mínima de senha |
| Login Lockout | ✅ | Bloqueio após 5 tentativas |
| JWT com Refresh Token | ✅ | Tokens seguros |

### Headers de Segurança

```python
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}
```

---

## 4. LangGraph v2 - Melhores Práticas

### Melhorias Implementadas

| Prática | v1 | v2 |
|---------|----|----|
| Estado tipado | TypedDict básico | IRISState (MessagesState) |
| Tools | JSON parsing manual | Pydantic schemas |
| Persistência | Nenhuma | PostgreSQL Checkpointer |
| Proteção loops | Não | max_steps=15 |
| Separação | Tudo junto | LLM decide → ToolNode executa |
| Observabilidade | Logs | LangSmith |

### Tools com Pydantic

```python
class RegistrarTransacaoSchema(BaseModel):
    valor: float = Field(gt=0, le=1000000)
    descricao: str = Field(min_length=2, max_length=200)
    categoria: str = Field(default="Outros")
    tipo: Literal["expense", "income"]

@tool(args_schema=RegistrarTransacaoSchema)
def registrar_transacao(valor, descricao, categoria, tipo):
    ...
```

### Persistência

```python
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

checkpointer = AsyncPostgresSaver.from_conn_string(DATABASE_URL)
graph = workflow.compile(checkpointer=checkpointer)
```

---

## 5. Otimizações de Performance

### Cache Unificado

- Redis como backend principal
- Fallback para memória local
- TTL configurável por namespace
- Estatísticas de uso

### Classificação Rápida

- Detecção de intenção sem LLM para padrões comuns
- Cache de classificações recentes
- Redução de 30-50% em chamadas LLM

---

## 6. Configurações

### Variáveis de Ambiente

```env
# LangGraph
LANGGRAPH_MEMORY_STORE=postgres
LANGGRAPH_RECURSION_LIMIT=15

# LangSmith
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_key
LANGCHAIN_PROJECT=iris-whatsapp

# SMTP
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_SSL=false
SMTP_USER=email@gmail.com
SMTP_PASSWORD=app_password
```

---

## 7. Comandos Make

```bash
make help          # Lista comandos
make dev           # Servidor de desenvolvimento
make docker-up     # Sobe containers
make test          # Executa testes
make lint          # Verifica código
make format        # Formata código
make deploy        # Push para origin
```

---

## 8. Próximos Passos

- [ ] Human-in-the-Loop para ações críticas
- [ ] Streaming de respostas
- [ ] Testes automatizados abrangentes
- [ ] Dashboard de métricas LangSmith

---

*Última atualização: Janeiro 2025*
