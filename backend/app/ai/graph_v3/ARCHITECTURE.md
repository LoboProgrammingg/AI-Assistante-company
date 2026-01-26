# IRIS Graph v3 - Arquitetura Otimizada

## Resumo Executivo

**Problema:** Latência ~15s, 3-4 chamadas LLM por request, patterns frágeis.

**Solução:** Nova arquitetura com 1-2 chamadas LLM, execução síncrona, templates prontos.

**Resultado Esperado:** Latência <4s, custo -50%.

---

## Comparação v2 vs v3

| Aspecto | v2 (Atual) | v3 (Novo) |
|---------|-----------|-----------|
| **Nós** | 8 | 3 (+finalize) |
| **Chamadas LLM** | 3-4 | 1-2 |
| **Classificação** | LLM Flash | LLM Flash |
| **Execução** | pending_execution → response_formatter | Síncrona no executor_node |
| **Resposta** | Sempre LLM Pro | Template quando possível |
| **Latência** | ~15s | <4s target |
| **Custo tokens** | Alto | ~50% menor |

---

## Fluxo do Graph v3

```
┌─────────────────────────────────────────────────────────┐
│                                                          │
│  USER INPUT                                              │
│      │                                                   │
│      ▼                                                   │
│  ┌──────────────────────────────────────────────────┐   │
│  │     COGNITIVE_NODE (Gemini Flash)                │   │
│  │  • Classifica intenção                           │   │
│  │  • Extrai entidades                              │   │
│  │  • Decide ação                                   │   │
│  │  Output: intent, action, entities                │   │
│  └──────────────────────────────────────────────────┘   │
│      │                                                   │
│      ├─────────────────┬─────────────────┐              │
│      │                 │                 │              │
│      ▼                 ▼                 ▼              │
│  [has_action]    [needs_llm]     [early_exit]           │
│      │                 │                 │              │
│      ▼                 │                 │              │
│  ┌──────────┐          │                 │              │
│  │ EXECUTOR │          │                 │              │
│  │ (código) │          │                 │              │
│  └──────────┘          │                 │              │
│      │                 │                 │              │
│      ├─────────────────┤                 │              │
│      │                 │                 │              │
│      ▼                 ▼                 │              │
│  [has_template]   [no_template]          │              │
│      │                 │                 │              │
│      │                 ▼                 │              │
│      │         ┌─────────────┐           │              │
│      │         │  RESPONDER  │           │              │
│      │         │ (Gemini Pro)│           │              │
│      │         └─────────────┘           │              │
│      │                 │                 │              │
│      ▼                 ▼                 ▼              │
│  ┌─────────────────────────────────────────────────┐   │
│  │                   FINALIZE                       │   │
│  │  • Garante resposta                              │   │
│  │  • Aplica template se disponível                 │   │
│  └─────────────────────────────────────────────────┘   │
│      │                                                   │
│      ▼                                                   │
│    [END]                                                 │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## Componentes

### 1. CognitiveNode (`cognitive_node.py`)

**Responsabilidade:** Uma chamada LLM que faz classificação + extração + decisão.

**Prompt otimizado:**
- ~500 tokens de input
- Retorna JSON estruturado
- Determinístico (temperature=0.2)

**Output:**
```python
{
    "intent": "finance|reminder|meeting|contact|todoist|search|general",
    "action": ExtractedAction(action_type, params, confidence),
    "entities": {...},
    "early_exit": bool,
    "response_template": str | None,
}
```

**Early Exit:** Saudações, agradecimentos, e mensagens triviais são respondidas com template SEM chamar LLM Pro.

### 2. ExecutorNode (`executor_node.py`)

**Responsabilidade:** Executar ações no banco/APIs.

**Diferença do v2:** 
- Execução SÍNCRONA (não pending_execution)
- Gera template de resposta quando possível
- SEM chamadas LLM

**Ações suportadas:**
- Finanças: create, query, delete, update
- Lembretes: create, list, delete
- Calendar: create_event, list_events
- Contatos: create, list
- Todoist: create_task, list_tasks

### 3. ResponderNode (`responder_node.py`)

**Responsabilidade:** Gerar respostas complexas via LLM Pro.

**Usado apenas quando:**
- Executor não tem template
- Intent é "general" com pergunta complexa
- Resultados de pesquisa precisam ser processados
- Erro precisa de explicação amigável

### 4. ResponseTemplates (`response_templates.py`)

**Templates prontos para:**
- Confirmações de criação
- Listagens
- Deletações
- Erros conhecidos
- Saudações

**Impacto:** ~60% das respostas NÃO precisam de LLM Pro.

---

## Estratégia de Migração

### Fase 1: Deploy Paralelo
```bash
# Manter v2 como padrão
IRIS_GRAPH_VERSION=v2
```

### Fase 2: Testes A/B
```python
# Em dev/staging
from app.ai.graph_v3.migration import compare_performance
result = await compare_performance(user_id, session_id, message)
```

### Fase 3: Rollout Gradual
```bash
# Ativar v3 para subset de usuários
IRIS_GRAPH_VERSION=v3
```

### Fase 4: Migração Completa
- Remover graph_v2
- v3 se torna padrão

---

## Métricas de Sucesso

| Métrica | v2 Atual | v3 Target | Como Medir |
|---------|----------|-----------|------------|
| Latência P50 | ~10s | <3s | Logs |
| Latência P95 | ~20s | <5s | Logs |
| Chamadas LLM/request | 3-4 | 1-2 | Contador |
| Custo tokens/request | Alto | -50% | API billing |
| Taxa de early exit | 0% | 30%+ | Logs |
| Taxa de template | 0% | 60%+ | Logs |

---

## Fallbacks

### 1. Erro de Parse JSON
```python
# cognitive_node.py
def _fallback_result(self, message):
    return {
        "intent": "general",
        "action": ExtractedAction(action_type="needs_llm_response", ...),
    }
```
→ Vai para ResponderNode (LLM Pro resolve)

### 2. Erro de Execução
```python
# executor_node.py
return ExecutionResult(success=False, error=str(e))
```
→ Vai para ResponderNode (explica erro amigavelmente)

### 3. LLM Timeout
- Retry com backoff
- Fallback para template genérico

---

## Não-Metas (O que NÃO fazer)

1. **Não usar regex como fonte da verdade**
   - Early exit é OTIMIZAÇÃO, não decisão
   - LLM é sempre a fonte final

2. **Não criar mais nós**
   - Se precisar de mais lógica, adicione no executor
   - Grafo simples = debug simples

3. **Não aumentar tamanho do prompt cognitivo**
   - Prompt curto = resposta rápida
   - Mais contexto vai no RAG, não no prompt

4. **Não chamar LLM Pro para confirmações**
   - Template é suficiente
   - "Gasto registrado!" não precisa de IA

---

## Checklist de Implementação

- [x] State v3 com tipos corretos
- [x] CognitiveNode com prompt otimizado
- [x] ExecutorNode com execução síncrona
- [x] ResponderNode apenas quando necessário
- [x] ResponseTemplates para ações comuns
- [x] Migration helper para rollout gradual
- [ ] Testes unitários
- [ ] Testes de integração
- [ ] Benchmark de latência
- [ ] Deploy em staging

---

## Autores e Histórico

- **v3.0** (Jan 2026): Refatoração completa para baixa latência
- **v2.0**: Arquitetura Hub-and-Spoke original
- **v1.0**: Implementação inicial
