# Implementação LangGraph v2 - IRIS

## Data: Janeiro 2025

---

## Resumo

Refatoração completa do sistema de IA seguindo as melhores práticas do LangGraph. Esta implementação traz melhorias significativas em robustez, manutenibilidade e inteligência.

---

## Arquivos Criados

| Arquivo | Linhas | Descrição |
|---------|--------|-----------|
| `app/ai/state.py` | 140 | Estado tipado com Pydantic |
| `app/ai/checkpointer.py` | 100 | Persistência PostgreSQL |
| `app/ai/graph_v2.py` | 400 | Grafo refatorado |
| `app/ai/tools/__init__.py` | 45 | Agregador de tools |
| `app/ai/tools/finance_tools.py` | 195 | Tools de finanças |
| `app/ai/tools/reminder_tools.py` | 165 | Tools de lembretes |
| `app/ai/tools/meeting_tools.py` | 121 | Tools de reuniões |
| `app/ai/tools/contact_tools.py` | 120 | Tools de contatos |

---

## Melhorias Implementadas

### 1. Estado Tipado (IRISState)

```python
from langgraph.graph import MessagesState

class IRISState(MessagesState):
    user_id: int = 0
    session_id: str = ""
    intent: Literal["reminder", "finance", "meeting", "contact", "general", ""] = ""
    confidence: float = 0.0
    entities: Dict[str, Any] = {}
    # ... campos tipados
```

**Benefícios:**
- Validação automática de tipos
- Autocompletar no IDE
- Reducer `add_messages` nativo

---

### 2. Tools com Pydantic Schemas

```python
class RegistrarTransacaoSchema(BaseModel):
    valor: float = Field(gt=0, le=1000000)
    descricao: str = Field(min_length=2, max_length=200)
    categoria: str = Field(default="Outros")
    tipo: Literal["expense", "income"] = Field(default="expense")

@tool(args_schema=RegistrarTransacaoSchema)
def registrar_transacao(valor, descricao, categoria, tipo):
    """Registra uma transação financeira."""
    ...
```

**Benefícios:**
- Validação automática de parâmetros
- Descrições claras para o LLM
- Menos erros de parsing

---

### 3. Persistência PostgreSQL

```python
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

checkpointer = AsyncPostgresSaver.from_conn_string(DATABASE_URL)
graph = workflow.compile(checkpointer=checkpointer)
```

**Benefícios:**
- Conversas persistem entre reinícios
- Pode retomar conversa de dias atrás
- Histórico completo do fluxo

---

### 4. Proteção contra Loops

```python
def _router_node(self, state):
    state["step_count"] += 1
    if state["step_count"] > state["max_steps"]:
        state["error"] = "Limite de passos atingido"
        return state
    # ...
```

**Configuração:**
```python
LANGGRAPH_RECURSION_LIMIT = 15
```

---

### 5. Separação LLM / Execução

```
[Router] -> [Agent Node] -> [Tool Executor] -> [Response]
              (LLM decide)    (Python executa)
```

O LLM apenas decide qual tool chamar. A execução real é feita separadamente, permitindo:
- Validação antes da execução
- Logging detalhado
- Rollback em caso de erro

---

### 6. LangSmith Observabilidade

```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_key
LANGCHAIN_PROJECT=iris-whatsapp
```

**Visibilidade:**
- Qual caminho o grafo tomou
- Input/output de cada nó
- Custo de cada chamada LLM
- Tempo de execução

---

## Como Usar

### Grafo v2 (Novo)

```python
from app.ai.graph_v2 import get_iris_graph

graph = get_iris_graph()
result = await graph.process_message(
    user_id=1,
    session_id="abc",
    message="Gastei 50 reais no almoço",
    context={"user_name": "João"},
    db=db_session
)
```

### Grafo v1 (Legado)

O `graph.py` original ainda funciona e pode ser usado como fallback.

---

## Migração

### Fase 1: Teste Paralelo
1. Manter `graph.py` original funcionando
2. Testar `graph_v2.py` em ambiente de dev
3. Comparar resultados

### Fase 2: Migração Gradual
1. Alterar `webhooks.py` para usar `graph_v2`
2. Monitorar LangSmith para erros
3. Rollback se necessário

### Fase 3: Deprecar v1
1. Após validação, remover `graph.py`
2. Renomear `graph_v2.py` para `graph.py`

---

## Dependências Adicionadas

```txt
langgraph-checkpoint-postgres==2.0.0
```

**Instalação:**
```bash
pip install langgraph-checkpoint-postgres
```

---

## Configurações Adicionadas

```python
# config.py
LANGGRAPH_RECURSION_LIMIT: int = 15

# LangSmith
LANGCHAIN_TRACING_V2: bool = True
LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"
LANGCHAIN_API_KEY: str = ""
LANGCHAIN_PROJECT: str = "iris-whatsapp"
```

---

## Próximos Passos

1. **Testar em dev** - Validar todas as tools
2. **Migrar webhooks.py** - Usar graph_v2
3. **Human-in-the-Loop** - Adicionar confirmação para ações críticas
4. **Streaming** - Implementar resposta em tempo real

---

## Scorecard Atualizado

| Prática | Antes | Depois |
|---------|-------|--------|
| Estado tipado | 🟡 Parcial | 🟢 Completo |
| MessagesState | 🔴 Não | 🟢 Sim |
| Tools Pydantic | 🔴 Não | 🟢 Sim |
| Persistência | 🔴 Não | 🟢 PostgreSQL |
| Proteção loops | 🔴 Não | 🟢 Sim |
| LangSmith | 🔴 Não | 🟢 Configurado |
| Separação LLM/exec | 🔴 Não | 🟢 Sim |
