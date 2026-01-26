# Arquitetura de Memória Avançada - IRIS AI

## Sumário Executivo

Este documento define a arquitetura de memória para um sistema de IA pessoal enterprise-grade, projetado para gerenciar aspectos críticos da vida do usuário (finanças, tarefas, decisões) com máxima confiabilidade.

**Princípios Fundamentais:**
- Memória estruturada, não texto solto
- Camadas com responsabilidades distintas
- Leitura ANTES da decisão, escrita APÓS
- Nenhum LLM escreve memória livremente
- Auditoria completa de cada operação
- Isolamento total por usuário

---

## 1. Arquitetura em Camadas

```
┌─────────────────────────────────────────────────────────────────┐
│                    CAMADA 1: SESSÃO                              │
│              (RAM/State - Não Persistente)                       │
│                                                                  │
│  • Mensagens da conversa atual                                   │
│  • Intenção em andamento                                         │
│  • Slots parcialmente preenchidos                                │
│  • TTL: Duração da sessão                                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CAMADA 2: TRABALHO                            │
│              (Redis/Cache - Semi-Persistente)                    │
│                                                                  │
│  • Contexto ativo carregado                                      │
│  • Decisão em andamento                                          │
│  • Dados temporários de execução                                 │
│  • TTL: 24 horas                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CAMADA 3: LONGO PRAZO                         │
│              (PostgreSQL - Persistente)                          │
│                                                                  │
│  • Preferências do usuário                                       │
│  • Hábitos recorrentes                                           │
│  • Aversões e restrições                                         │
│  • Informações de identidade                                     │
│  • TTL: Configurável ou indefinido                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CAMADA 4: EPISÓDICA                           │
│              (PostgreSQL - Persistente + Indexada)               │
│                                                                  │
│  • Decisões passadas                                             │
│  • Ações executadas                                              │
│  • Eventos significativos                                        │
│  • TTL: 90-365 dias (com agregação)                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Estrutura de Dados

### 2.1 Schema Principal de Memória

```python
@dataclass
class MemoryItem:
    """Item de memória estruturado."""
    
    # Identificação
    memory_id: str              # UUID único
    user_id: int                # Isolamento por usuário
    
    # Classificação
    memory_type: MemoryType     # preference | habit | recurrence | constraint | event | decision
    layer: MemoryLayer          # session | working | longterm | episodic
    category: str               # finance | health | work | personal | general
    
    # Conteúdo
    key: str                    # Chave semântica (ex: "preferred_greeting_time")
    value: Any                  # Valor estruturado (não texto livre)
    summary: str                # Resumo legível (máx 100 chars)
    
    # Metadados de Confiança
    confidence: float           # 0.0 - 1.0
    importance: Importance      # low | medium | high | critical
    source: MemorySource        # user_explicit | user_implicit | inference | system
    
    # Temporalidade
    created_at: datetime
    updated_at: datetime
    last_accessed: datetime
    last_confirmed: datetime    # Última vez que usuário confirmou
    expires_at: Optional[datetime]
    access_count: int           # Quantas vezes foi usada
    
    # Auditoria
    origin_message_id: str      # Mensagem que originou
    origin_session_id: str      # Sessão de origem
    update_history: List[dict]  # Histórico de mudanças
```

### 2.2 Tipos de Memória

```python
class MemoryType(Enum):
    # Identidade do Usuário
    PREFERENCE = "preference"       # "Prefiro ser chamado de João"
    HABIT = "habit"                 # "Sempre pago contas dia 5"
    RECURRENCE = "recurrence"       # "Academia segundas e quartas"
    CONSTRAINT = "constraint"       # "Alérgico a frutos do mar"
    IDENTITY = "identity"           # "Trabalho como engenheiro"
    
    # Episódicos
    EVENT = "event"                 # "Viajou para SP em janeiro"
    DECISION = "decision"           # "Decidiu investir em X"
    ACTION = "action"               # "Criou lembrete para Y"
    
    # Contextuais
    CONTEXT = "context"             # Informação temporária relevante
    INFERENCE = "inference"         # Dedução do sistema
```

### 2.3 Níveis de Importância

```python
class Importance(Enum):
    LOW = "low"           # Pode ser esquecido após 30 dias
    MEDIUM = "medium"     # Manter por 90 dias
    HIGH = "high"         # Manter por 1 ano
    CRITICAL = "critical" # Nunca expira automaticamente
```

### 2.4 Fontes de Memória

```python
class MemorySource(Enum):
    USER_EXPLICIT = "user_explicit"   # Usuário disse diretamente
    USER_IMPLICIT = "user_implicit"   # Detectado do comportamento
    INFERENCE = "inference"           # IA deduziu
    SYSTEM = "system"                 # Dados do sistema
```

---

## 3. Fluxo no LangGraph

```
┌──────────────────────────────────────────────────────────────────┐
│                         USER INPUT                                │
│                    "Paguei 500 de luz"                            │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                 1. INTENT & SLOT EXTRACTION                       │
│                      (Cognitive Node)                             │
│                                                                   │
│  Input:  message, session_state                                   │
│  Output: intent, entities, confidence                             │
│  LLM:    Gemini Flash (rápido)                                    │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                  2. MEMORY READER NODE                            │
│                    (Sem LLM - Determinístico)                     │
│                                                                   │
│  Input:  user_id, intent, entities                                │
│  Query:  Busca memórias relevantes por:                           │
│          - Tipo compatível com intent                             │
│          - Categoria (finance, health, etc)                       │
│          - Confiança >= 0.5                                       │
│          - Recência (last_accessed)                               │
│  Output: relevant_memories (máx 10 itens)                         │
│                                                                   │
│  REGRA: NUNCA INVENTA - só retorna o que existe                   │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│               3. WORKING CONTEXT BUILDER                          │
│                    (Sem LLM - Determinístico)                     │
│                                                                   │
│  Input:  intent, entities, relevant_memories                      │
│  Process:                                                         │
│    1. Filtra memórias por relevância ao intent                    │
│    2. Ordena por importância + recência                           │
│    3. Comprime para máx 500 tokens                                │
│    4. Formata como contexto estruturado                           │
│  Output: working_context (string otimizada)                       │
│                                                                   │
│  REGRA: Contexto MÍNIMO necessário                                │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│              4. DECISION / TOOL EXECUTION                         │
│                    (Executor Node)                                │
│                                                                   │
│  Input:  intent, entities, working_context                        │
│  Process: Executa ação (criar gasto, lembrete, etc)               │
│  Output: execution_result                                         │
│                                                                   │
│  O QUE VAI PARA O LLM (se necessário):                            │
│    ✅ Intent e entidades                                          │
│    ✅ Contexto comprimido (máx 500 tokens)                        │
│    ✅ Resultado da execução                                       │
│    ❌ NUNCA: histórico bruto                                      │
│    ❌ NUNCA: todas as memórias                                    │
│    ❌ NUNCA: dados de outros usuários                             │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                 5. MEMORY WRITER NODE                             │
│                    (Sem LLM - Regras Determinísticas)             │
│                                                                   │
│  Input:  message, intent, entities, execution_result              │
│  Process:                                                         │
│    1. Detecta se há algo para memorizar                           │
│    2. Classifica tipo e importância                               │
│    3. Verifica se já existe (update vs create)                    │
│    4. Define confiança inicial                                    │
│    5. Persiste com auditoria                                      │
│  Output: memory_operations (list of created/updated)              │
│                                                                   │
│  REGRAS:                                                          │
│    ✅ Preferências explícitas → SALVAR                            │
│    ✅ Padrões recorrentes (3+ vezes) → SALVAR                     │
│    ✅ Decisões importantes → EPISÓDICO                            │
│    ❌ Emoções momentâneas → DESCARTAR                             │
│    ❌ Ruído conversacional → DESCARTAR                            │
│    ❌ Dados sensíveis sem confirmação → DESCARTAR                 │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                  6. RESPONSE FORMATTER                            │
│                    (Responder Node)                               │
│                                                                   │
│  Input:  execution_result, working_context                        │
│  Output: resposta final humanizada                                │
└──────────────────────────────────────────────────────────────────┘
```

---

## 4. Memory Reader - Implementação Detalhada

### 4.1 Estratégia de Busca

```python
class MemoryReaderStrategy:
    """Estratégia de leitura de memória por intent."""
    
    INTENT_MEMORY_MAP = {
        "finance": {
            "types": [MemoryType.PREFERENCE, MemoryType.HABIT, MemoryType.RECURRENCE],
            "categories": ["finance"],
            "max_items": 5,
            "min_confidence": 0.6,
        },
        "reminder": {
            "types": [MemoryType.PREFERENCE, MemoryType.HABIT],
            "categories": ["personal", "work"],
            "max_items": 3,
            "min_confidence": 0.5,
        },
        "health": {
            "types": [MemoryType.CONSTRAINT, MemoryType.RECURRENCE],
            "categories": ["health"],
            "max_items": 5,
            "min_confidence": 0.7,  # Maior para saúde
        },
        "general": {
            "types": [MemoryType.PREFERENCE, MemoryType.IDENTITY],
            "categories": ["general"],
            "max_items": 3,
            "min_confidence": 0.5,
        },
    }
```

### 4.2 Filtros de Relevância

```python
def filter_memories(
    memories: List[MemoryItem],
    intent: str,
    entities: Dict,
) -> List[MemoryItem]:
    """Filtra memórias relevantes para o contexto atual."""
    
    strategy = INTENT_MEMORY_MAP.get(intent, INTENT_MEMORY_MAP["general"])
    
    filtered = []
    for mem in memories:
        # 1. Filtro de tipo
        if mem.memory_type not in strategy["types"]:
            continue
        
        # 2. Filtro de categoria
        if mem.category not in strategy["categories"]:
            continue
        
        # 3. Filtro de confiança
        if mem.confidence < strategy["min_confidence"]:
            continue
        
        # 4. Filtro de expiração
        if mem.expires_at and mem.expires_at < datetime.now():
            continue
        
        # 5. Score de relevância
        relevance = calculate_relevance(mem, intent, entities)
        if relevance > 0.3:
            filtered.append((mem, relevance))
    
    # Ordenar por relevância e limitar
    filtered.sort(key=lambda x: x[1], reverse=True)
    return [m for m, _ in filtered[:strategy["max_items"]]]
```

### 4.3 Cálculo de Relevância

```python
def calculate_relevance(
    memory: MemoryItem,
    intent: str,
    entities: Dict,
) -> float:
    """Calcula score de relevância de 0.0 a 1.0."""
    
    score = 0.0
    
    # 1. Correspondência de categoria (+0.3)
    if memory.category in entities.get("categories", []):
        score += 0.3
    
    # 2. Recência (+0.2)
    days_since_access = (datetime.now() - memory.last_accessed).days
    if days_since_access < 7:
        score += 0.2
    elif days_since_access < 30:
        score += 0.1
    
    # 3. Frequência de uso (+0.2)
    if memory.access_count > 10:
        score += 0.2
    elif memory.access_count > 3:
        score += 0.1
    
    # 4. Importância (+0.2)
    importance_scores = {"critical": 0.2, "high": 0.15, "medium": 0.1, "low": 0.05}
    score += importance_scores.get(memory.importance, 0)
    
    # 5. Confiança (+0.1)
    score += memory.confidence * 0.1
    
    return min(score, 1.0)
```

---

## 5. Memory Writer - Implementação Detalhada

### 5.1 Regras de Detecção

```python
class MemoryDetectionRules:
    """Regras para detectar o que deve ser memorizado."""
    
    # Padrões que DEVEM ser salvos
    SAVE_PATTERNS = {
        "preference": [
            r"(?:eu )?(?:gosto|adoro|amo|prefiro) (?:de |muito )?(.+)",
            r"(?:meu|minha) (?:favorit[oa]|preferid[oa]) (?:é|são) (.+)",
        ],
        "constraint": [
            r"(?:tenho )?alergia (?:a |de )?(.+)",
            r"(?:sou )?(?:alérgic[oa]|intolerante) (?:a |de )?(.+)",
            r"(?:não posso|não consigo) (.+)",
        ],
        "habit": [
            r"(?:sempre|geralmente) (?:eu )?(.+) (?:às|todo|toda) (.+)",
            r"(?:eu )?(.+) (?:todo dia|toda semana|todo mês)",
        ],
        "identity": [
            r"(?:meu nome|me chamo) (?:é )?(.+)",
            r"(?:trabalho|sou) (?:como )?(.+)",
            r"(?:moro|vivo) (?:em|na|no) (.+)",
        ],
    }
    
    # Padrões que NUNCA devem ser salvos
    DISCARD_PATTERNS = [
        r"(?:estou|tô) (?:triste|feliz|cansad[oa]|animad[oa])",  # Emoções momentâneas
        r"(?:acho|penso) que",  # Opiniões vagas
        r"(?:talvez|quem sabe|pode ser)",  # Incertezas
        r"(?:hoje|agora|neste momento)",  # Temporário demais
    ]
    
    # Dados sensíveis que requerem confirmação
    SENSITIVE_PATTERNS = [
        r"(?:cpf|rg|identidade)",
        r"(?:senha|password|pin)",
        r"(?:cartão|conta|agência)",
        r"(?:doença|diagnóstico|medicamento)",
    ]
```

### 5.2 Fluxo de Decisão

```python
async def should_memorize(
    message: str,
    intent: str,
    entities: Dict,
    execution_result: Dict,
) -> Optional[MemoryItem]:
    """Decide se e o que memorizar."""
    
    # 1. Verificar padrões de descarte
    for pattern in DISCARD_PATTERNS:
        if re.search(pattern, message.lower()):
            return None
    
    # 2. Verificar dados sensíveis
    for pattern in SENSITIVE_PATTERNS:
        if re.search(pattern, message.lower()):
            return MemoryItem(
                requires_confirmation=True,
                confidence=0.3,  # Baixa confiança até confirmar
            )
    
    # 3. Detectar tipo de memória
    for mem_type, patterns in SAVE_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, message.lower())
            if match:
                return create_memory_item(
                    memory_type=mem_type,
                    content=match.group(1),
                    source=MemorySource.USER_IMPLICIT,
                    confidence=0.7,
                )
    
    # 4. Verificar ação executada (episódico)
    if execution_result.get("success"):
        action = execution_result.get("action_type", "")
        if action in ["create_finance", "create_reminder", "create_goal"]:
            return create_memory_item(
                memory_type=MemoryType.ACTION,
                content=f"Executou: {action}",
                source=MemorySource.SYSTEM,
                confidence=1.0,
                layer=MemoryLayer.EPISODIC,
            )
    
    return None
```

### 5.3 Atualização de Memória Existente

```python
async def update_or_create_memory(
    new_memory: MemoryItem,
    db: Session,
) -> MemoryItem:
    """Atualiza memória existente ou cria nova."""
    
    # Buscar memória similar
    existing = await find_similar_memory(
        user_id=new_memory.user_id,
        memory_type=new_memory.memory_type,
        key=new_memory.key,
        db=db,
    )
    
    if existing:
        # Atualizar memória existente
        
        # 1. Reforçar confiança (máx 1.0)
        new_confidence = min(existing.confidence + 0.1, 1.0)
        
        # 2. Atualizar valor se diferente
        value_changed = existing.value != new_memory.value
        
        # 3. Registrar no histórico
        existing.update_history.append({
            "timestamp": datetime.now().isoformat(),
            "action": "reinforced" if not value_changed else "updated",
            "old_value": existing.value if value_changed else None,
            "new_value": new_memory.value if value_changed else None,
            "old_confidence": existing.confidence,
            "new_confidence": new_confidence,
        })
        
        existing.confidence = new_confidence
        existing.updated_at = datetime.now()
        existing.last_confirmed = datetime.now()
        
        if value_changed:
            existing.value = new_memory.value
        
        return existing
    
    else:
        # Criar nova memória
        new_memory.created_at = datetime.now()
        new_memory.updated_at = datetime.now()
        new_memory.last_accessed = datetime.now()
        new_memory.access_count = 0
        new_memory.update_history = [{
            "timestamp": datetime.now().isoformat(),
            "action": "created",
            "source": new_memory.source.value,
        }]
        
        return new_memory
```

---

## 6. Working Context Builder

### 6.1 Compressão de Contexto

```python
def build_working_context(
    memories: List[MemoryItem],
    intent: str,
    max_tokens: int = 500,
) -> str:
    """Constrói contexto comprimido para o LLM."""
    
    if not memories:
        return ""
    
    # Agrupar por tipo
    by_type = defaultdict(list)
    for mem in memories:
        by_type[mem.memory_type].append(mem)
    
    lines = []
    
    # Preferências (máx 3)
    if MemoryType.PREFERENCE in by_type:
        prefs = by_type[MemoryType.PREFERENCE][:3]
        lines.append("Preferências: " + "; ".join(p.summary for p in prefs))
    
    # Restrições (todas - crítico)
    if MemoryType.CONSTRAINT in by_type:
        constraints = by_type[MemoryType.CONSTRAINT]
        lines.append("⚠️ Restrições: " + "; ".join(c.summary for c in constraints))
    
    # Hábitos relevantes (máx 2)
    if MemoryType.HABIT in by_type:
        habits = by_type[MemoryType.HABIT][:2]
        lines.append("Hábitos: " + "; ".join(h.summary for h in habits))
    
    # Identidade (máx 2)
    if MemoryType.IDENTITY in by_type:
        identity = by_type[MemoryType.IDENTITY][:2]
        lines.append("Sobre: " + "; ".join(i.summary for i in identity))
    
    context = "\n".join(lines)
    
    # Truncar se necessário
    if len(context) > max_tokens * 4:  # ~4 chars por token
        context = context[:max_tokens * 4] + "..."
    
    return context
```

### 6.2 O que NUNCA vai para o LLM

```python
# CAMPOS QUE NUNCA DEVEM IR PARA O LLM
NEVER_TO_LLM = [
    "memory_id",
    "user_id",
    "origin_message_id",
    "origin_session_id",
    "update_history",
    "created_at",
    "updated_at",
    "last_accessed",
    "access_count",
    "expires_at",
]

# TIPOS DE MEMÓRIA QUE NUNCA VÃO PARA O LLM
NEVER_TO_LLM_TYPES = [
    MemoryType.ACTION,  # Histórico de ações
    MemoryType.INFERENCE,  # Deduções internas
]
```

---

## 7. Gestão de Confiança

### 7.1 Ciclo de Vida da Confiança

```
┌─────────────────────────────────────────────────────────────────┐
│                     CRIAÇÃO                                      │
│                                                                  │
│  USER_EXPLICIT  → confidence = 0.9                               │
│  USER_IMPLICIT  → confidence = 0.7                               │
│  INFERENCE      → confidence = 0.5                               │
│  SYSTEM         → confidence = 1.0                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     REFORÇO                                      │
│                                                                  │
│  Usuário menciona novamente → +0.1 (máx 1.0)                     │
│  Memória usada com sucesso  → +0.05                              │
│  Usuário confirma           → = 1.0                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     DECAY (Degradação)                           │
│                                                                  │
│  30 dias sem uso  → -0.1                                         │
│  90 dias sem uso  → -0.2                                         │
│  180 dias sem uso → -0.3                                         │
│  confidence < 0.3 → ARQUIVAR                                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     INVALIDAÇÃO                                  │
│                                                                  │
│  Usuário contradiz → confidence = 0.2                            │
│  Usuário corrige   → update + confidence = 0.9                   │
│  Usuário exclui    → DELETE + audit log                          │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 Implementação de Decay

```python
async def apply_memory_decay(db: Session):
    """Job diário para degradar memórias não usadas."""
    
    now = datetime.now()
    
    # Memórias não acessadas há 30+ dias
    stale_30 = await get_memories_not_accessed_since(db, days=30)
    for mem in stale_30:
        mem.confidence = max(mem.confidence - 0.1, 0.0)
    
    # Memórias não acessadas há 90+ dias
    stale_90 = await get_memories_not_accessed_since(db, days=90)
    for mem in stale_90:
        mem.confidence = max(mem.confidence - 0.2, 0.0)
    
    # Arquivar memórias com confiança muito baixa
    to_archive = [m for m in stale_30 + stale_90 if m.confidence < 0.3]
    for mem in to_archive:
        mem.layer = MemoryLayer.ARCHIVED
        mem.archived_at = now
    
    await db.commit()
```

---

## 8. Segurança e Privacidade

### 8.1 Isolamento por Usuário

```python
# TODAS as queries DEVEM incluir user_id
class MemoryRepository:
    async def get_memories(
        self,
        user_id: int,  # OBRIGATÓRIO
        **filters,
    ) -> List[MemoryItem]:
        query = select(Memory).where(Memory.user_id == user_id)
        # ...
        return await self.db.execute(query)
    
    # NUNCA expor método sem user_id
    # async def get_all_memories(self): ← PROIBIDO
```

### 8.2 Exclusão Seletiva (LGPD)

```python
async def delete_user_memory(
    user_id: int,
    memory_id: str = None,
    memory_type: MemoryType = None,
    delete_all: bool = False,
    db: Session,
) -> DeleteResult:
    """Exclui memória com auditoria completa."""
    
    # 1. Validar permissão
    if not await user_owns_memory(user_id, memory_id, db):
        raise PermissionError("Memória não pertence ao usuário")
    
    # 2. Criar log de auditoria ANTES de deletar
    audit_log = AuditLog(
        user_id=user_id,
        action="memory_delete",
        target_id=memory_id,
        reason="user_request",
        timestamp=datetime.now(),
        data_snapshot=memory_to_dict(memory),  # Cópia antes de deletar
    )
    db.add(audit_log)
    
    # 3. Deletar
    if delete_all:
        await db.execute(delete(Memory).where(Memory.user_id == user_id))
    elif memory_type:
        await db.execute(
            delete(Memory).where(
                Memory.user_id == user_id,
                Memory.memory_type == memory_type,
            )
        )
    else:
        await db.execute(
            delete(Memory).where(
                Memory.user_id == user_id,
                Memory.memory_id == memory_id,
            )
        )
    
    await db.commit()
    
    return DeleteResult(success=True, audit_id=audit_log.id)
```

### 8.3 Correção de Memória

```python
async def correct_memory(
    user_id: int,
    memory_id: str,
    new_value: Any,
    correction_reason: str,
    db: Session,
) -> MemoryItem:
    """Corrige memória mantendo histórico."""
    
    memory = await get_memory_by_id(memory_id, user_id, db)
    
    # Registrar correção no histórico
    memory.update_history.append({
        "timestamp": datetime.now().isoformat(),
        "action": "user_correction",
        "old_value": memory.value,
        "new_value": new_value,
        "reason": correction_reason,
    })
    
    memory.value = new_value
    memory.confidence = 0.95  # Alta confiança após correção manual
    memory.source = MemorySource.USER_EXPLICIT
    memory.updated_at = datetime.now()
    memory.last_confirmed = datetime.now()
    
    await db.commit()
    return memory
```

---

## 9. Performance e Escalabilidade

### 9.1 Índices Recomendados

```sql
-- Índice principal para busca por usuário
CREATE INDEX idx_memory_user_type 
ON memories(user_id, memory_type, confidence DESC);

-- Índice para decay/cleanup
CREATE INDEX idx_memory_last_accessed 
ON memories(last_accessed, confidence);

-- Índice para busca por categoria
CREATE INDEX idx_memory_category 
ON memories(user_id, category, importance);

-- Índice para expiração
CREATE INDEX idx_memory_expires 
ON memories(expires_at) WHERE expires_at IS NOT NULL;
```

### 9.2 Cache Strategy

```python
class MemoryCache:
    """Cache em Redis para memórias frequentes."""
    
    TTL_SECONDS = 3600  # 1 hora
    
    async def get_user_context(self, user_id: int) -> Optional[Dict]:
        key = f"memory:context:{user_id}"
        cached = await self.redis.get(key)
        return json.loads(cached) if cached else None
    
    async def set_user_context(self, user_id: int, context: Dict):
        key = f"memory:context:{user_id}"
        await self.redis.setex(key, self.TTL_SECONDS, json.dumps(context))
    
    async def invalidate_user(self, user_id: int):
        """Invalida cache quando memória é modificada."""
        pattern = f"memory:*:{user_id}"
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)
```

### 9.3 Limites por Usuário

```python
# Limites para evitar crescimento infinito
MEMORY_LIMITS = {
    MemoryType.PREFERENCE: 50,
    MemoryType.HABIT: 30,
    MemoryType.CONSTRAINT: 20,
    MemoryType.IDENTITY: 10,
    MemoryType.RECURRENCE: 30,
    MemoryType.EVENT: 100,      # Episódico - rotaciona
    MemoryType.ACTION: 500,     # Episódico - rotaciona
    MemoryType.DECISION: 200,   # Episódico - rotaciona
}

async def enforce_memory_limits(user_id: int, memory_type: MemoryType, db: Session):
    """Remove memórias mais antigas quando limite é atingido."""
    
    limit = MEMORY_LIMITS.get(memory_type, 50)
    count = await count_memories(user_id, memory_type, db)
    
    if count >= limit:
        # Remover as mais antigas com menor confiança
        excess = count - limit + 10  # Remove 10 para ter margem
        await delete_oldest_low_confidence(user_id, memory_type, excess, db)
```

---

## 10. O que NUNCA Fazer

### 10.1 Anti-Patterns

```python
# ❌ NUNCA: Jogar histórico bruto para o LLM
prompt = f"Histórico: {all_messages[-100:]}"  # ERRADO

# ❌ NUNCA: Salvar tudo
if message:
    save_memory(message)  # ERRADO - sem critério

# ❌ NUNCA: LLM decide o que salvar
llm_response = llm.invoke("O que devo lembrar dessa conversa?")  # ERRADO

# ❌ NUNCA: Contexto ilimitado
context = "\n".join(memory.value for memory in all_memories)  # ERRADO

# ❌ NUNCA: Query sem user_id
memories = db.query(Memory).all()  # ERRADO - sem isolamento

# ❌ NUNCA: Confiar em inference sem validação
memory.confidence = 1.0  # ERRADO para inference
```

### 10.2 Padrões Corretos

```python
# ✅ CORRETO: Contexto comprimido
context = build_working_context(relevant_memories, max_tokens=500)

# ✅ CORRETO: Regras determinísticas para salvar
if matches_save_pattern(message):
    save_memory(message, confidence=0.7)

# ✅ CORRETO: Código decide, não LLM
memory_type = classify_memory_type(message)  # Regex/Rules

# ✅ CORRETO: Limite de contexto
memories = get_top_relevant(user_id, intent, limit=10)

# ✅ CORRETO: Sempre com user_id
memories = db.query(Memory).filter(Memory.user_id == user_id).all()

# ✅ CORRETO: Confiança proporcional à fonte
memory.confidence = SOURCE_CONFIDENCE[source]  # 0.5 para inference
```

---

## 11. Métricas e Monitoramento

### 11.1 Métricas de Saúde

```python
MEMORY_METRICS = {
    # Volume
    "memory_count_per_user": Gauge,
    "memory_created_total": Counter,
    "memory_deleted_total": Counter,
    
    # Performance
    "memory_read_latency_seconds": Histogram,
    "memory_write_latency_seconds": Histogram,
    "context_build_latency_seconds": Histogram,
    
    # Qualidade
    "memory_confidence_avg": Gauge,
    "memory_decay_count": Counter,
    "memory_archive_count": Counter,
    
    # Cache
    "memory_cache_hit_ratio": Gauge,
    "memory_cache_miss_total": Counter,
}
```

### 11.2 Alertas Recomendados

```yaml
alerts:
  - name: MemoryGrowthAnomaly
    condition: memory_count_per_user > 1000
    severity: warning
    
  - name: MemoryReadSlow
    condition: memory_read_latency_seconds_p95 > 0.5
    severity: critical
    
  - name: LowConfidenceMemories
    condition: memory_confidence_avg < 0.5
    severity: warning
    
  - name: CacheMissHigh
    condition: memory_cache_hit_ratio < 0.7
    severity: warning
```

---

## 12. Resumo da Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                     IRIS MEMORY SYSTEM                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  CAMADAS:                                                        │
│    1. Sessão     → State do LangGraph (volátil)                  │
│    2. Trabalho   → Redis (24h TTL)                               │
│    3. Longo Prazo→ PostgreSQL (persistente)                      │
│    4. Episódica  → PostgreSQL (rotacionada)                      │
│                                                                  │
│  FLUXO:                                                          │
│    Input → Cognitive → Reader → Context → Executor → Writer      │
│                                                                  │
│  REGRAS:                                                         │
│    • Leitura ANTES, escrita APÓS                                 │
│    • LLM não escreve memória                                     │
│    • Contexto máximo: 500 tokens                                 │
│    • Máximo 10 memórias por query                                │
│    • Decay automático de confiança                               │
│    • Isolamento total por user_id                                │
│                                                                  │
│  SEGURANÇA:                                                      │
│    • Auditoria completa                                          │
│    • Exclusão com log                                            │
│    • Correção com histórico                                      │
│    • LGPD compliant                                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```
