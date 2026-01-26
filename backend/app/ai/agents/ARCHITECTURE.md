# Arquitetura Multi-Agente IRIS v3

## Visão Geral

Sistema de IA pessoal com agentes especializados, cada um com responsabilidades e ferramentas bem definidas.

```
┌─────────────────────────────────────────────────────────────┐
│                      IRIS ROUTER                             │
│         (Cognitive Node - Intent Classification)             │
└─────────────────────────┬───────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│ Bills Agent   │ │ Memory Agent  │ │ Pattern Agent │
│ (Faturas/OCR) │ │ (Long-term)   │ │ (Anomalias)   │
└───────────────┘ └───────────────┘ └───────────────┘
        │                 │                 │
        ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│ Goals Agent   │ │ Advisor Agent │ │ Health Agent  │
│ (Metas)       │ │ (Consultor)   │ │ (Saúde leve)  │
└───────────────┘ └───────────────┘ └───────────────┘
        │                 │
        ▼                 ▼
┌───────────────┐ ┌───────────────┐
│ Subscriptions │ │ Confidence    │
│ Agent         │ │ Scoring       │
└───────────────┘ └───────────────┘
```

---

## Princípios de Arquitetura

### 1. Isolamento de Tools
- **Nenhuma tool é global**
- Cada agente só acessa suas próprias tools
- Comunicação via estado validado no LangGraph

### 2. Separação de Responsabilidades
- **LLM decide** *o que fazer*
- **Código decide** *se pode executar*

### 3. Confidence Scoring
- Ações financeiras → score alto obrigatório
- Mensagens externas → confirmação do usuário
- Score baixo → apenas sugestão

---

## Agentes e Ferramentas

### 1. 🧾 Bills Agent (Faturas)

**Responsabilidade:**
- Ler faturas em PDF, imagem ou email
- Extrair valores, datas, parcelas e vencimentos
- Criar lembretes financeiros automaticamente

**Tools Permitidas:**
```python
BILLS_TOOLS = [
    "read_pdf",
    "read_image",           # OCR (já implementado)
    "read_email",
    "extract_invoice_data",
    "create_financial_reminder",
]
```

**Restrições:**
- ❌ Nunca executar pagamento
- ❌ Nunca assumir valores não explicitados
- ✅ Confirmar dados críticos antes de salvar

---

### 2. 🧠 Memory Agent (Memória Pessoal)

**Responsabilidade:**
- Detectar informações pessoais relevantes
- Decidir o que deve ser salvo como memória
- Atualizar preferências do usuário

**Tools Permitidas:**
```python
MEMORY_TOOLS = [
    "write_memory",
    "read_memory",
    "update_memory",
]
```

**Regras:**
- ❌ NÃO salvar tudo
- ✅ Priorizar: hábitos, preferências, recorrências, aversões
- ❌ Nunca salvar dados sensíveis sem confirmação

---

### 3. 🔮 Pattern Agent (Padrões & Anomalias)

**Responsabilidade:**
- Analisar histórico financeiro, agenda e comportamento
- Detectar desvios, excessos e padrões recorrentes
- Gerar alertas inteligentes

**Tools Permitidas:**
```python
PATTERN_TOOLS = [
    "read_financial_history",
    "read_task_history",
    "read_calendar_history",
    "generate_pattern_insight",
]
```

**Regras:**
- ❌ Nunca emitir julgamentos
- ✅ Sempre explicar o motivo do alerta
- ✅ Alertas informativos, não invasivos

---

### 4. 🧭 Goals Agent (Metas)

**Responsabilidade:**
- Criar metas financeiras, pessoais ou profissionais
- Acompanhar progresso automaticamente
- Ajustar metas conforme comportamento real

**Tools Permitidas:**
```python
GOALS_TOOLS = [
    "create_goal",
    "update_goal",
    "read_goal_progress",
    "suggest_adjustment",
]
```

**Regras:**
- ✅ Metas devem ser realistas
- ✅ Ajustes sugeridos, nunca impostos
- ✅ Cruzar metas com finanças e agenda

---

### 5. 🧠 Advisor Agent (Consultor)

**Responsabilidade:**
- Responder perguntas estratégicas
- Simular cenários financeiros e pessoais
- Ajudar em decisões importantes

**Tools Permitidas:**
```python
ADVISOR_TOOLS = [
    "simulate_scenario",
    "read_financial_state",
    "read_commitments",
    "run_projection",
]
```

**Regras:**
- ❌ Nunca dar ordens
- ✅ Sempre apresentar opções
- ✅ Explicitar incertezas

---

### 6. 🏥 Health Agent (Saúde Leve)

**Responsabilidade:**
- Organizar compromissos de saúde
- Criar lembretes de remédios e consultas
- Armazenar histórico organizacional (não clínico)

**Tools Permitidas:**
```python
HEALTH_TOOLS = [
    "create_health_reminder",
    "read_health_schedule",
    "store_health_note",
]
```

**Restrições CRÍTICAS:**
- ❌ NÃO diagnosticar
- ❌ NÃO sugerir tratamentos
- ❌ NÃO interpretar exames

---

### 7. 🛒 Subscriptions Agent (Assinaturas)

**Responsabilidade:**
- Identificar cobranças recorrentes
- Alertar sobre aumentos de preço
- Sugerir cancelamento de serviços não utilizados

**Tools Permitidas:**
```python
SUBSCRIPTIONS_TOOLS = [
    "detect_recurring_payment",
    "track_subscription",
    "alert_price_change",
]
```

**Regras:**
- ❌ Nunca cancelar automaticamente
- ✅ Sempre pedir confirmação
- ✅ Priorizar impacto financeiro

---

### 8. 📊 Confidence Agent (Scoring)

**Responsabilidade:**
- Avaliar confiança de qualquer ação sugerida
- Definir se a IA pode agir ou deve confirmar
- Reduzir erros críticos

**Tools Permitidas:**
```python
CONFIDENCE_TOOLS = [
    "calculate_confidence",
    "require_user_confirmation",
    "log_decision_score",
]
```

**Regras:**
- Score ALTO (>0.9): Ação automática permitida
- Score MÉDIO (0.5-0.9): Requer confirmação
- Score BAIXO (<0.5): Apenas sugestão

---

## Fluxo de Processamento

```
┌──────────────────────────────────────────────────────────────┐
│ 1. INPUT                                                      │
│    Usuário envia mensagem/imagem/PDF                          │
└──────────────────────────┬───────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ 2. COGNITIVE NODE (Flash)                                     │
│    - Classifica intenção                                      │
│    - Identifica agente responsável                            │
│    - Extrai entidades iniciais                                │
└──────────────────────────┬───────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ 3. AGENT DISPATCHER                                           │
│    - Roteia para agente específico                            │
│    - Injeta apenas tools permitidas                           │
└──────────────────────────┬───────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ 4. SPECIALIZED AGENT                                          │
│    - Processa com suas tools                                  │
│    - Valida dados extraídos                                   │
│    - Calcula confidence score                                 │
└──────────────────────────┬───────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ 5. CONFIDENCE CHECK                                           │
│    - Score >= 0.9: Executa automaticamente                    │
│    - Score 0.5-0.9: Pede confirmação                          │
│    - Score < 0.5: Sugere, não executa                         │
└──────────────────────────┬───────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ 6. EXECUTOR                                                   │
│    - Executa ação se aprovada                                 │
│    - Salva no banco de dados                                  │
│    - Atualiza memória se relevante                            │
└──────────────────────────┬───────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ 7. RESPONDER                                                  │
│    - Gera resposta humanizada                                 │
│    - Usa template quando possível                             │
└──────────────────────────────────────────────────────────────┘
```

---

## Estrutura de Diretórios

```
app/ai/
├── graph_v3/
│   ├── core.py              # Grafo principal
│   ├── migration.py         # v2↔v3
│   ├── state/               # Estado
│   ├── nodes/               # Cognitive, Responder
│   ├── executors/           # Por domínio
│   └── templates/           # Respostas
│
└── agents/
    ├── ARCHITECTURE.md      # Este documento
    ├── __init__.py
    ├── base.py              # Classe base
    ├── registry.py          # Registro de agentes
    │
    ├── bills/               # 🧾 Faturas
    │   ├── __init__.py
    │   ├── agent.py
    │   └── tools.py
    │
    ├── memory/              # 🧠 Memória
    │   ├── __init__.py
    │   ├── agent.py
    │   └── tools.py
    │
    ├── patterns/            # 🔮 Padrões
    │   ├── __init__.py
    │   ├── agent.py
    │   └── tools.py
    │
    ├── goals/               # 🧭 Metas
    │   ├── __init__.py
    │   ├── agent.py
    │   └── tools.py
    │
    ├── advisor/             # 🧠 Consultor
    │   ├── __init__.py
    │   ├── agent.py
    │   └── tools.py
    │
    ├── health/              # 🏥 Saúde
    │   ├── __init__.py
    │   ├── agent.py
    │   └── tools.py
    │
    ├── subscriptions/       # 🛒 Assinaturas
    │   ├── __init__.py
    │   ├── agent.py
    │   └── tools.py
    │
    └── confidence/          # 📊 Scoring
        ├── __init__.py
        └── scorer.py
```

---

## Integração com Graph v3

Os agentes especializados serão chamados pelo `ExecutorNode` quando a intenção for mapeada:

```python
# executors/dispatcher.py
AGENT_MAPPING = {
    "bills": BillsAgent,
    "memory": MemoryAgent,
    "patterns": PatternAgent,
    "goals": GoalsAgent,
    "advisor": AdvisorAgent,
    "health": HealthAgent,
    "subscriptions": SubscriptionsAgent,
}
```

---

## Status de Implementação

| Agente | Status | Descrição |
|--------|--------|-----------|
| 🧾 **Bills** | ✅ Implementado | OCR + extração de faturas |
| 🧠 **Memory** | ✅ Implementado | Preferências e memórias |
| 📊 **Confidence** | ✅ Implementado | Scoring de segurança |
| 🔮 **Patterns** | ✅ Implementado | Detecção de anomalias |
| 🧭 **Goals** | ✅ Implementado | Metas financeiras |
| 🛒 **Subscriptions** | ✅ Implementado | Assinaturas recorrentes |
| 🧠 **Advisor** | ✅ Implementado | Simulações e projeções |
| 🏥 **Health** | ✅ Implementado | Lembretes de saúde |

---

## Fallbacks de Segurança

1. **Agente não encontrado** → General Chat
2. **Confidence < 0.3** → Apenas sugere, não executa
3. **Tool falha** → Log + mensagem amigável
4. **Timeout** → Resposta genérica + retry

---

## Métricas de Sucesso

- **Latência**: < 3s para ações simples
- **Precisão**: > 95% de classificação correta
- **Segurança**: 0 ações financeiras sem confirmação quando score < 0.9
- **UX**: Respostas naturais via templates
