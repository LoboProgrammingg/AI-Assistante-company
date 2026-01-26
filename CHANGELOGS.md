# CHANGELOGS - IRIS AI Assistant

## [v3.0.0] - Janeiro 2026

### 🚀 IRIS Graph v3 - Arquitetura Completa

Esta versão representa uma reescrita significativa do sistema de IA, introduzindo uma arquitetura modular, sistema de memória avançado e melhor observabilidade.

---

### ✨ Novidades

#### Sistema de Memória Avançado
- **UserMemory Model** - Novo modelo de memória estruturada com:
  - 10 tipos de memória (preference, habit, constraint, identity, etc.)
  - 5 camadas (session, working, longterm, episodic, archived)
  - Sistema de confiança (0.0 - 1.0) com decay automático
  - Níveis de importância (low, medium, high, critical)
  - Tracking de origem (user_explicit, user_implicit, inference, system)
  - TTL e expiração automática
  - Auditoria completa via `MemoryAuditLog`

- **MemoryReaderNode** - Leitura determinística de memórias
  - Estratégias por intent
  - Filtragem por confiança e recência
  - Fallback gracioso para v2

- **MemoryWriterNode** - Escrita determinística de memórias
  - Detecção de padrões (preferências, hábitos, constraints)
  - Proteção de dados sensíveis
  - Auditoria automática
  - Limites por tipo de memória

- **WorkingContextBuilder** - Construção de contexto para LLM
  - Compressão inteligente de memórias
  - Priorização por importância e confiança
  - Limite de tokens configurável

- **RedisWorkingMemory** - Cache de working memory
  - TTL dinâmico por risco de operação
  - Isolamento por user_id e session_id
  - Fallback gracioso se Redis indisponível

#### Jobs de Manutenção
- **MemoryDecayJob** - Reduz confiança ao longo do tempo
- **MemoryExpirationJob** - Arquiva memórias expiradas
- **MemoryCleanupJob** - Remove memórias arquivadas antigas
- **MemoryReinforcementJob** - Reforça memórias frequentes

#### Agentes Especializados (8 agentes)
1. **FinanceAgent** - Gestão financeira
2. **ReminderAgent** - Lembretes e alarmes
3. **CalendarAgent** - Eventos e agenda
4. **ContactAgent** - Contatos e mensagens
5. **PatternsAgent** - Análise de padrões
6. **GoalsAgent** - Metas e objetivos
7. **SubscriptionsAgent** - Assinaturas recorrentes
8. **HealthAgent** - Lembretes de saúde

#### Arquitetura LangGraph
- **CognitiveNode** - Classificação de intent (16 intents)
- **ExecutorNode** - Roteamento para agentes
- **ResponderNode** - Geração de respostas
- **Fluxo de Memória Integrado** - Reader → ContextBuilder → Executor → Writer

---

### 🔧 Mudanças Técnicas

#### Banco de Dados
- Nova tabela `user_memories` (21 colunas, 6 índices)
- Nova tabela `memory_audit_logs` (11 colunas)
- 4 novos Enums PostgreSQL
- Criação automática via `Base.metadata.create_all()`

#### Configuração
- `IRIS_GRAPH_VERSION` agora padrão `v3`
- Suporte a feature flags: `IRIS_V3_MEMORY`, `IRIS_V3_DECAY`
- TTL dinâmico no Redis por tipo de operação

#### Endpoints Atualizados
- `/api/v1/chat/message` - Usa camada de migração v3
- `/api/v1/chat/audio` - Usa camada de migração v3
- `/api/v1/webhook/whatsapp` - Usa camada de migração v3

---

### 📁 Arquivos Criados/Modificados

#### Novos Arquivos
```
backend/app/models/user_memory.py          # Modelo UserMemory + MemoryAuditLog
backend/app/ai/memory/                      # Pacote de memória avançada
├── __init__.py
├── types.py                                # MemoryItem, Enums, constantes
├── reader.py                               # MemoryReaderNode
├── writer.py                               # MemoryWriterNode
├── context_builder.py                      # WorkingContextBuilder
└── redis_working.py                        # RedisWorkingMemory
backend/app/jobs/                           # Jobs de manutenção
├── __init__.py
└── memory_decay.py                         # Jobs de decay/cleanup
backend/app/ai/memory_legacy.py             # MemoryManager legado (renomeado)
backend/app/ai/HARDENING_GUIDE.md           # Guia de hardening
backend/app/ai/graph_v3/GRAPH_V3_DOCUMENTATION.md  # Documentação completa
```

#### Arquivos Modificados
```
backend/app/models/__init__.py              # Exports dos novos modelos
backend/app/models/user.py                  # Relacionamento memories
backend/app/ai/graph_v3/migration.py        # Padrão v3
backend/app/api/chat.py                     # Usa camada de migração
```

---

### 🔄 Migração

#### De v2 para v3
1. Deploy do código (tabelas criadas automaticamente)
2. `IRIS_GRAPH_VERSION=v3` já é o padrão
3. Memórias existentes em `ConversationMemory` continuam funcionando (fallback)
4. Novas memórias são salvas em `UserMemory`

#### Rollback (se necessário)
```bash
# Voltar para v2
IRIS_GRAPH_VERSION=v2
# Reiniciar aplicação
```

---

### ⚠️ Breaking Changes

- `app.ai.memory.MemoryManager` movido para `app.ai.memory_legacy.MemoryManager`
- Import mantido compatível via `app.ai.memory`

---

### 📊 Métricas de Sucesso

| Métrica | Threshold | Status |
|---------|-----------|--------|
| Latência p95 | < 2s | ⏳ A validar |
| Taxa de erro | < 1% | ⏳ A validar |
| Accuracy de intent | > 90% | ⏳ A validar |
| Cache hit | > 70% | ⏳ A validar |

---

### 🔮 Próximos Passos

- [ ] Validação em staging
- [ ] Dashboard de auditoria
- [ ] A/B testing v2 vs v3
- [ ] Métricas de qualidade de memória
- [ ] Ajuste fino de decay por tipo

---

## [v2.x.x] - Versões Anteriores

### v2.0.0
- Implementação inicial do LangGraph
- Agentes básicos (Finance, Reminder, Calendar, Contact)
- Integração com WhatsApp via Twilio
- Transcrição de áudio com Gemini
- Análise de imagens financeiras

### v1.0.0
- Versão inicial com WhatsAppAIAgent
- Integração básica com Gemini

---

*Última atualização: Janeiro 2026*
