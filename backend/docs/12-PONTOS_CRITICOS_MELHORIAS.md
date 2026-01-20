# Análise de Pontos Críticos e Melhorias - IRIS

## 1. Segurança 🔒

### 1.1 Problemas Identificados

#### ❌ Exposição de Credenciais
```python
# Problema: API keys podem ser expostas em logs
logger.error(f"Erro ao invocar LLM no agente {self.name}: {e}")
```

**Recomendação:** Sanitizar logs para não expor informações sensíveis.

#### ❌ Falta de Rate Limiting por Usuário
O sistema não possui controle de rate limiting por usuário, permitindo abuso da API.

**Recomendação:**
```python
# Implementar rate limiter
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter

@app.post("/message")
@limiter.limit("30/minute")
async def process_message(request: MessageRequest):
    pass
```

#### ❌ Validação de Entrada Insuficiente
Mensagens não são sanitizadas antes do processamento.

**Recomendação:**
```python
def sanitize_message(message: str) -> str:
    """Remove caracteres potencialmente perigosos."""
    # Limitar tamanho
    message = message[:5000]
    # Remover caracteres de controle
    message = ''.join(c for c in message if c.isprintable() or c in '\n\t')
    return message.strip()
```

#### ❌ SQL Injection Potencial
Uso de `.filter()` com strings concatenadas em alguns lugares.

**Recomendação:** Sempre usar parâmetros bindados:
```python
# ❌ Evitar
query.filter(Finance.description.ilike(f"%{user_input}%"))

# ✅ Preferir
query.filter(Finance.description.ilike(bindparam('desc'))).params(desc=f"%{user_input}%")
```

### 1.2 Melhorias Sugeridas

| Prioridade | Melhoria | Esforço |
|------------|----------|---------|
| ALTA | Implementar rate limiting | Médio |
| ALTA | Sanitização de inputs | Baixo |
| MÉDIA | Audit logging de ações | Médio |
| MÉDIA | Criptografia de dados sensíveis | Alto |
| BAIXA | Tokens JWT com expiração curta | Baixo |

---

## 2. Performance 🚀

### 2.1 Problemas Identificados

#### ❌ Múltiplas Chamadas LLM por Requisição
Uma mensagem pode gerar 2-3 chamadas ao LLM (classificação + processamento + resposta).

**Impacto:** Latência alta (~2-5s por mensagem)

**Recomendação:**
```python
# Combinar classificação e extração em uma única chamada
combined_prompt = f"""
Analise a mensagem e retorne:
1. Intenção (intent)
2. Entidades extraídas
3. Resposta sugerida

Mensagem: {message}
"""
```

#### ❌ Cache de Classificação Subutilizado
O cache só é usado quando confidence >= 0.8.

**Recomendação:** Usar cache probabilístico ou reduzir threshold para 0.7.

#### ❌ N+1 Queries no MemoryManager
```python
# Problema: Múltiplas queries separadas
facts = self.service.get_learned_facts(user_id)
preferences = self.service.get_user_preferences(user_id)
stats = self.service.get_stats(user_id)
```

**Recomendação:** Consolidar em uma única query ou usar eager loading.

### 2.2 Métricas Sugeridas

```python
# Adicionar métricas de performance
import time

class PerformanceMetrics:
    @staticmethod
    def track_latency(func):
        async def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = await func(*args, **kwargs)
            duration = time.perf_counter() - start
            logger.info(f"{func.__name__} executado em {duration:.2f}s")
            return result
        return wrapper
```

---

## 3. Qualidade das Respostas da IA 🤖

### 3.1 Problemas Identificados

#### ❌ Alucinações em Dados Financeiros
A IA pode inventar valores ou transações não existentes.

**Recomendação:**
```python
# Adicionar verificação pós-resposta
def validate_financial_response(response: str, actual_data: dict) -> str:
    """Verifica se valores mencionados existem nos dados reais."""
    mentioned_values = extract_monetary_values(response)
    for value in mentioned_values:
        if value not in actual_data['amounts']:
            response = add_disclaimer(response, value)
    return response
```

#### ❌ Contexto Truncado
Histórico limitado a 15-20 mensagens pode perder contexto importante.

**Recomendação:**
- Implementar resumo automático de conversas longas
- Usar embeddings para recuperar contexto relevante

#### ❌ Falta de Validação de Datas
Datas extraídas não são validadas (pode gerar datas no passado).

**Recomendação:**
```python
def validate_reminder_date(scheduled_time: datetime, current_time: datetime) -> bool:
    """Valida se a data do lembrete é futura."""
    if scheduled_time <= current_time:
        raise ValueError("Data do lembrete deve ser no futuro")
    if scheduled_time > current_time + timedelta(days=365):
        raise ValueError("Data muito distante (máximo 1 ano)")
    return True
```

### 3.2 Melhorias no Prompt Engineering

```python
# Adicionar instruções de grounding
GROUNDING_INSTRUCTIONS = """
REGRAS DE PRECISÃO:
1. Só mencione dados que estejam EXPLICITAMENTE no contexto
2. Se não tiver certeza, diga "Não encontrei essa informação"
3. Nunca invente nomes de contatos ou valores
4. Use EXATAMENTE os números do contexto
"""
```

---

## 4. Tratamento de Erros 🐛

### 4.1 Problemas Identificados

#### ❌ Exceções Genéricas
```python
except Exception as e:
    logger.error(f"Erro: {e}")
    return {"error": "Erro genérico"}
```

**Recomendação:**
```python
class IRISException(Exception):
    """Base exception para IRIS."""
    pass

class LLMTimeoutException(IRISException):
    """LLM demorou muito para responder."""
    pass

class EntityExtractionException(IRISException):
    """Falha ao extrair entidades."""
    pass

# Tratamento específico
try:
    result = await self.llm.ainvoke(prompt)
except asyncio.TimeoutError:
    raise LLMTimeoutException("LLM timeout após 30s")
except json.JSONDecodeError as e:
    raise EntityExtractionException(f"JSON inválido: {e}")
```

#### ❌ Rollback Inconsistente
Em alguns lugares, `db.rollback()` não é chamado após erros.

**Recomendação:** Usar context managers:
```python
from contextlib import contextmanager

@contextmanager
def safe_db_operation(db: Session):
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
```

### 4.2 Fallback Strategies

```python
class FallbackHandler:
    """Estratégias de fallback para erros."""
    
    @staticmethod
    async def handle_llm_failure(message: str, error: Exception) -> str:
        """Resposta de fallback quando LLM falha."""
        logger.error(f"LLM falhou: {error}")
        return (
            "Desculpe, estou com dificuldades técnicas no momento. "
            "Pode tentar novamente em alguns instantes? 🙏"
        )
    
    @staticmethod
    async def handle_timeout(message: str) -> str:
        """Resposta para timeout."""
        return (
            "Sua mensagem é um pouco complexa e estou processando. "
            "Aguarde um momento..."
        )
```

---

## 5. Escalabilidade 📈

### 5.1 Problemas Identificados

#### ❌ Sessão de DB por Request
Cada request cria uma nova conexão.

**Recomendação:** Connection pooling configurado:
```python
engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600
)
```

#### ❌ Memória em Banco Relacional
`UserMemory` em PostgreSQL pode ficar lento com muitos usuários.

**Recomendação:** Migrar para Redis para dados de sessão:
```python
class RedisMemoryService:
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def get_context(self, user_id: int) -> dict:
        key = f"user:{user_id}:context"
        data = await self.redis.get(key)
        return json.loads(data) if data else {}
    
    async def set_context(self, user_id: int, context: dict, ttl: int = 3600):
        key = f"user:{user_id}:context"
        await self.redis.setex(key, ttl, json.dumps(context))
```

### 5.2 Arquitetura Sugerida para Escala

```
┌─────────────────┐
│   Load Balancer │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───┴───┐ ┌───┴───┐
│ API 1 │ │ API 2 │  (Horizontal scaling)
└───┬───┘ └───┬───┘
    │         │
    └────┬────┘
         │
    ┌────┴────┐
    │  Redis  │  (Cache + Session)
    └────┬────┘
         │
    ┌────┴────┐
    │PostgreSQL│ (Dados persistentes)
    └─────────┘
```

---

## 6. Observabilidade 📊

### 6.1 Melhorias Sugeridas

#### Logging Estruturado
```python
import structlog

logger = structlog.get_logger()

logger.info(
    "message_processed",
    user_id=user_id,
    intent=intent,
    confidence=confidence,
    latency_ms=latency * 1000,
    tokens_used=token_count
)
```

#### Métricas Prometheus
```python
from prometheus_client import Counter, Histogram

messages_processed = Counter(
    'iris_messages_total',
    'Total de mensagens processadas',
    ['intent', 'status']
)

response_latency = Histogram(
    'iris_response_latency_seconds',
    'Latência de resposta',
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)
```

#### Tracing Distribuído
```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

async def process_message(message: str):
    with tracer.start_as_current_span("process_message") as span:
        span.set_attribute("message.length", len(message))
        
        with tracer.start_as_current_span("classify_intent"):
            intent = await classify(message)
        
        with tracer.start_as_current_span("generate_response"):
            response = await generate(message, intent)
        
        return response
```

---

## 7. Roadmap de Melhorias

### Fase 1: Segurança (1-2 semanas)
- [ ] Implementar rate limiting
- [ ] Sanitização de inputs
- [ ] Audit logging

### Fase 2: Performance (2-3 semanas)
- [ ] Otimizar chamadas LLM (combinar prompts)
- [ ] Implementar cache Redis
- [ ] Connection pooling otimizado

### Fase 3: Qualidade (2-4 semanas)
- [ ] Validação de respostas
- [ ] Grounding de dados
- [ ] Resumo automático de contexto

### Fase 4: Observabilidade (1-2 semanas)
- [ ] Logging estruturado
- [ ] Métricas Prometheus
- [ ] Dashboard de monitoramento

### Fase 5: Escalabilidade (3-4 semanas)
- [ ] Migrar sessões para Redis
- [ ] Implementar queue para mensagens
- [ ] Horizontal scaling
