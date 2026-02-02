# 🧹 CLEAN.md - Análise de Limpeza do Backend

**Data da Análise:** Janeiro 2026  
**Última Atualização:** Janeiro 2026  
**Total de Arquivos Python:** 164 → **~155 arquivos** (após limpeza)  
**Objetivo:** Identificar código não utilizado, duplicado e oportunidades de simplificação

---

## ✅ LIMPEZA REALIZADA

### Arquivos Removidos com Sucesso:
| Arquivo | Motivo | Status |
|---------|--------|--------|
| `app/services/message_broadcast_service.py` | Deprecated | ✅ REMOVIDO |
| `app/ai/iris_identity.py` | Não importado | ✅ REMOVIDO |
| `app/ai/agents/finance_agent.py` | Legado, não usado | ✅ REMOVIDO |
| `app/ai/agents/reminder_agent.py` | Legado, não usado | ✅ REMOVIDO |
| `app/ai/agents/constants/` | Pasta inteira | ✅ REMOVIDO |
| `app/ai/agents/prompts/finance_prompts.py` | Legado | ✅ REMOVIDO |
| `app/ai/agents/prompts/reminder_prompts.py` | Legado | ✅ REMOVIDO |
| `app/ai/agents/prompts/classifier_prompts.py` | Legado | ✅ REMOVIDO |
| `app/ai/agents/prompts/response_prompts.py` | Legado | ✅ REMOVIDO |

### Arquivos Atualizados:
- `app/ai/agents/__init__.py` - Removidos imports legados
- `app/ai/agents/prompts/__init__.py` - Mantido apenas MeetingPrompts

### Itens NÃO Removidos (ainda em uso):
- **Agentes especializados** (advisor, bills, goals, health, memory, patterns, subscriptions) - Usados pelo dispatcher
- **base.py e base_agent.py** - Ambos usados por classes diferentes
- **Shims de compatibilidade** - Ainda referenciados em 5+ arquivos
- **MeetingAgent** - Usado ativamente em chat.py

---

## 📊 Resumo Executivo (Atualizado)

| Categoria | Original | Após Limpeza | Status |
|-----------|----------|--------------|--------|
| Arquivos Removidos | 12 planejados | 9 removidos | ✅ Parcial |
| Pasta constants/ | 3 arquivos | 0 | ✅ Removida |
| Prompts legados | 4 arquivos | 0 | ✅ Removidos |
| Agentes legados | 2 arquivos | 0 | ✅ Removidos |

**Redução real:** ~9 arquivos removidos + 1 pasta inteira

---

## 🗑️ ARQUIVOS PARA REMOVER

### 1. Serviços Não Utilizados

#### `app/services/message_broadcast_service.py`
- **Status:** DEPRECATED (marcado no próprio arquivo)
- **Motivo:** Funcionalidade de contatos/grupos removida
- **Dependências:** Nenhuma - não é importado em lugar nenhum
- **Ação:** ✅ REMOVER

#### `app/utils/seed_categories.py`
- **Status:** Script de seed único
- **Motivo:** Script utilitário para popular categorias, não usado em runtime
- **Dependências:** Nenhuma - é executado manualmente
- **Ação:** ⚠️ MOVER para pasta `scripts/` ou `migrations/`

#### `app/workers/scheduler.py`
- **Status:** Não importado em lugar nenhum
- **Motivo:** Worker de agendamento parece não estar integrado ao sistema
- **Dependências:** Importa vários models mas não é chamado
- **Ação:** ⚠️ VERIFICAR se está em uso via processo separado, senão REMOVER

---

### 2. Agentes Especializados Órfãos

Os seguintes agentes estão definidos mas **NÃO são chamados** diretamente pelo sistema principal (graph_v3). Eles são registrados no `registry.py` e `dispatcher.py` mas nunca invocados:

| Agente | Arquivo | Usado? | Ação |
|--------|---------|--------|------|
| `AdvisorAgent` | `app/ai/agents/advisor/agent.py` | ❌ Apenas em docs | REMOVER |
| `HealthAgent` | `app/ai/agents/health/agent.py` | ❌ Apenas em docs | REMOVER |
| `PatternsAgent` | `app/ai/agents/patterns/agent.py` | ❌ Apenas em docs | REMOVER |
| `SubscriptionsAgent` | `app/ai/agents/subscriptions/agent.py` | ❌ Apenas em docs | REMOVER |
| `FinanceAgent` | `app/ai/agents/finance_agent.py` | ⚠️ Apenas vision_service | AVALIAR |
| `ReminderAgent` | `app/ai/agents/reminder_agent.py` | ❌ Apenas __init__ | REMOVER |
| `MeetingAgent` | `app/ai/agents/meeting_agent.py` | ⚠️ Usado em chat.py | MANTER |

**Pastas inteiras para remover:**
```
app/ai/agents/advisor/        # 2 arquivos
app/ai/agents/health/         # 2 arquivos  
app/ai/agents/patterns/       # 2 arquivos
app/ai/agents/subscriptions/  # 2 arquivos
app/ai/agents/confidence/     # 2 arquivos (só usado internamente pelo dispatcher)
```

---

### 3. Arquivos de Prompts Não Utilizados

| Arquivo | Usado Por | Ação |
|---------|-----------|------|
| `app/ai/agents/prompts/classifier_prompts.py` | Apenas `__init__.py` | REMOVER |
| `app/ai/agents/prompts/response_prompts.py` | Apenas `__init__.py` | REMOVER |
| `app/ai/agents/prompts/reminder_prompts.py` | Nenhum | REMOVER |
| `app/ai/agents/prompts/meeting_prompts.py` | Nenhum | REMOVER |
| `app/ai/agents/prompts/finance_prompts.py` | Apenas graph_v3 prompts | AVALIAR |

**Nota:** O sistema atual usa `app/ai/graph_v3/prompts/` para todos os prompts. Os prompts em `app/ai/agents/prompts/` são legado.

---

### 4. Constantes Não Utilizadas

| Arquivo | Usado Por | Ação |
|---------|-----------|------|
| `app/ai/agents/constants/finance_constants.py` | Nenhum código ativo | REMOVER |
| `app/ai/agents/constants/reminder_constants.py` | Nenhum código ativo | REMOVER |

---

### 5. Módulo iris_identity.py

#### `app/ai/iris_identity.py`
- **Status:** Não importado em lugar nenhum
- **Motivo:** Parece ser um módulo de identidade/personalidade não integrado
- **Ação:** ✅ REMOVER ou INTEGRAR se necessário

---

## 🔄 ARQUIVOS DE COMPATIBILIDADE (SHIMS)

Estes arquivos existem apenas para manter compatibilidade com imports antigos. Podem ser removidos após atualizar os imports:

| Arquivo Shim | Redireciona Para | Dependências | Ação |
|--------------|------------------|--------------|------|
| `app/core/cache_manager.py` | `app/core/cache/` | 1 import | REMOVER após migração |
| `app/services/cache_service.py` | `app/core/cache/` | Usado em main.py | REMOVER após migração |
| `app/services/ai_context_cache.py` | `app/core/cache/ai_context.py` | 2 imports | REMOVER após migração |
| `app/services/email_service.py` | `app/services/email/` | Vários imports | MANTER por agora |

**Plano de migração:**
1. Atualizar todos os imports para usar `app/core/cache/` diretamente
2. Remover os shims
3. Testar

---

## 📁 CÓDIGO DUPLICADO

### 1. Sistema de Cache (3 implementações!)

| Implementação | Localização | Status |
|---------------|-------------|--------|
| `CacheManager` | `app/core/cache/manager.py` | ✅ PRINCIPAL |
| `AIContextCache` | `app/core/cache/ai_context.py` | ✅ PRINCIPAL |
| `RedisWorkingMemory` | `app/ai/memory/redis_working.py` | ⚠️ MIGRADO - usar AIContextCache |
| `CacheService` (legado) | `app/services/cache_service.py` | 🔄 SHIM |

**Ação:** Consolidar tudo em `app/core/cache/`

---

### 2. Context Builders (2 implementações!)

| Implementação | Localização | Usado Por |
|---------------|-------------|-----------|
| `ContextBuilder` | `app/ai/context/context_builder.py` | graph_v3/core.py ✅ |
| `WorkingContextBuilder` | `app/ai/memory/context_builder.py` | memory/__init__.py |

**Ação:** Manter apenas `app/ai/context/context_builder.py`, remover o outro

---

### 3. Memory Readers/Writers

| Componente | Localização | Status |
|------------|-------------|--------|
| `MemoryManager` | `app/ai/memory/manager.py` | ✅ PRINCIPAL |
| `MemoryReaderNode` | `app/ai/memory/reader.py` | ⚠️ Usado apenas em core.py |
| `MemoryWriterNode` | `app/ai/memory/writer.py` | ⚠️ Usado apenas em core.py |

**Ação:** Avaliar se reader/writer são necessários ou podem ser consolidados no manager

---

### 4. Base Agents (2 arquivos!)

| Arquivo | Usado Por |
|---------|-----------|
| `app/ai/agents/base.py` | 9 agentes (registry, dispatcher, etc) |
| `app/ai/agents/base_agent.py` | 4 agentes (finance, meeting, reminder + __init__) |

**Ação:** Consolidar em um único `base.py`

---

### 5. Meetings API (2 versões!)

| Arquivo | Status |
|---------|--------|
| `app/api/meetings.py` | Versão original |
| `app/api/meetings_v2.py` | Versão nova com transcrição |

**Ação:** Avaliar se `meetings.py` ainda é necessário ou pode ser removido

---

## 🔧 MÓDULOS PARA SIMPLIFICAR

### 1. `app/core/` - Código não utilizado diretamente

| Arquivo | Exports | Usado Externamente? |
|---------|---------|---------------------|
| `llm_optimizer.py` | `LLMOptimizer`, `get_optimizer` | ❌ Apenas em __init__ |
| `data_validator.py` | `DataValidator`, `validate_entities` | ❌ Apenas em __init__ |
| `secure_logging.py` | Logger seguro | ❌ Apenas internamente |

**Ação:** Remover se não estiverem em uso real

---

### 2. `app/models/` - Models possivelmente não utilizados

| Model | Arquivo | Verificar Uso |
|-------|---------|---------------|
| `AICache` | `ai_cache.py` | ⚠️ Verificar se há tabela no banco |
| `Integration` | `integration.py` | ⚠️ Verificar uso real |
| `Subscription` | `subscription.py` | ⚠️ Verificar uso real |
| `ScheduledMessage` | `scheduled_message.py` | ⚠️ Usado pelo scheduler não integrado |

---

### 3. `app/schemas/` - Schemas possivelmente não utilizados

| Schema | Arquivo | Verificar Uso |
|--------|---------|---------------|
| `DocumentSchema` | `document.py` | ✅ Usado em documents.py |

---

## 📂 ESTRUTURA RECOMENDADA

### Antes (Atual)
```
app/
├── ai/
│   ├── agents/           # 35+ arquivos, maioria não usada
│   │   ├── advisor/
│   │   ├── bills/
│   │   ├── confidence/
│   │   ├── constants/
│   │   ├── goals/
│   │   ├── health/
│   │   ├── memory/
│   │   ├── patterns/
│   │   ├── prompts/
│   │   ├── subscriptions/
│   │   └── ...
│   ├── context/          # 4 arquivos ✅
│   ├── graph_v3/         # Sistema principal ✅
│   ├── llm/              # 2 arquivos ✅
│   └── memory/           # 7 arquivos, alguns duplicados
├── core/
│   ├── cache/            # 4 arquivos ✅
│   └── ...               # Alguns não usados
└── services/             # Alguns shims e deprecated
```

### Depois (Recomendado)
```
app/
├── ai/
│   ├── agents/           # Apenas os USADOS
│   │   ├── base.py       # Consolidado
│   │   ├── goals/        # ✅ Usado
│   │   ├── bills/        # ✅ Usado
│   │   ├── memory/       # ✅ Usado
│   │   ├── registry.py   # ✅ Usado
│   │   └── dispatcher.py # ✅ Usado
│   ├── context/          # ✅ Manter
│   ├── graph_v3/         # ✅ Manter
│   ├── llm/              # ✅ Manter
│   └── memory/           # Simplificado
│       ├── manager.py    # Principal
│       ├── types.py      # Tipos
│       └── __init__.py
├── core/
│   ├── cache/            # ✅ Manter (único sistema de cache)
│   └── ...               # Limpar não usados
└── services/             # Sem shims
```

---

## ✅ PLANO DE AÇÃO

### Fase 1: Remoção Segura (Baixo Risco)
1. [ ] Remover `app/services/message_broadcast_service.py`
2. [ ] Remover `app/ai/iris_identity.py`
3. [ ] Remover pasta `app/ai/agents/advisor/`
4. [ ] Remover pasta `app/ai/agents/health/`
5. [ ] Remover pasta `app/ai/agents/patterns/`
6. [ ] Remover pasta `app/ai/agents/subscriptions/`
7. [ ] Remover pasta `app/ai/agents/confidence/`
8. [ ] Remover pasta `app/ai/agents/constants/`
9. [ ] Remover `app/ai/agents/prompts/` (exceto se usado)

### Fase 2: Consolidação (Médio Risco)
1. [ ] Consolidar `base.py` e `base_agent.py`
2. [ ] Migrar imports de shims para módulos reais
3. [ ] Remover shims de cache após migração
4. [ ] Avaliar `app/ai/memory/context_builder.py` vs `app/ai/context/context_builder.py`

### Fase 3: Avaliação (Requer Testes)
1. [ ] Verificar se `app/workers/scheduler.py` está em uso
2. [ ] Verificar se models `AICache`, `Integration`, `Subscription` têm dados
3. [ ] Avaliar se `meetings.py` pode ser removido em favor de `meetings_v2.py`
4. [ ] Verificar uso real de `llm_optimizer.py` e `data_validator.py`

---

## 📈 MÉTRICAS ESPERADAS

| Métrica | Antes | Depois | Redução |
|---------|-------|--------|---------|
| Arquivos Python | 164 | ~100 | ~40% |
| Linhas de Código | ~15k | ~10k | ~33% |
| Pastas em agents/ | 11 | 4 | ~64% |
| Imports circulares | Possíveis | Eliminados | 100% |
| Tempo de carregamento | Base | Reduzido | ~20% |

---

## ⚠️ NOTAS IMPORTANTES

1. **Sempre faça backup antes de remover arquivos**
2. **Execute testes após cada fase de remoção**
3. **Verifique se há processos externos usando os arquivos** (workers, scripts cron)
4. **Alguns arquivos marcados como "não usados" podem ser usados via imports dinâmicos**

---

## 🔍 COMANDOS ÚTEIS

```bash
# Encontrar arquivos Python não importados
grep -r "from app\." --include="*.py" | cut -d: -f2 | sort | uniq

# Contar linhas por pasta
find app/ -name "*.py" -exec wc -l {} + | tail -1

# Verificar imports de um módulo específico
grep -r "from app.ai.agents.advisor" --include="*.py"

# Listar arquivos modificados recentemente
find app/ -name "*.py" -mtime -30 -type f
```

---

**Documento gerado automaticamente pela análise de código.**
