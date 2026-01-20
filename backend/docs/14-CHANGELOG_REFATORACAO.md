# Changelog da Refatoração - IRIS v1.0

## Data: Janeiro 2025

---

## Resumo das Mudanças

Esta refatoração reorganizou a estrutura dos agentes de IA para melhorar a manutenibilidade, legibilidade e escalabilidade do código.

---

## Arquivos Criados

### Prompts Centralizados (`app/ai/agents/prompts/`)

| Arquivo | Descrição |
|---------|-----------|
| `__init__.py` | Exporta todas as classes de prompts |
| `classifier_prompts.py` | Prompts para classificação de intenções |
| `response_prompts.py` | Prompts para geração de respostas finais + identidade IRIS |
| `reminder_prompts.py` | Prompts e templates do ReminderAgent |
| `finance_prompts.py` | Prompts e templates do FinanceAgent |
| `meeting_prompts.py` | Prompts e templates do MeetingAgent |
| `contact_prompts.py` | Prompts e templates do ContactAgent |

### Constantes (`app/ai/agents/constants/`)

| Arquivo | Descrição |
|---------|-----------|
| `__init__.py` | Exporta todas as classes de constantes |
| `finance_constants.py` | Categorias financeiras, keywords, métodos de detecção |
| `reminder_constants.py` | Tipos de recorrência, opções de tempo, keywords |

### Identidade IRIS (`app/ai/`)

| Arquivo | Descrição |
|---------|-----------|
| `iris_identity.py` | Nome, descrição, capacidades e mensagens da IRIS |

### Documentação (`backend/docs/`)

| Arquivo | Descrição |
|---------|-----------|
| `11-IRIS_OVERVIEW.md` | Visão geral da arquitetura IRIS |
| `12-PONTOS_CRITICOS_MELHORIAS.md` | Análise de segurança, performance e melhorias |
| `13-ESTRUTURA_REORGANIZADA.md` | Documentação da nova estrutura |
| `14-CHANGELOG_REFATORACAO.md` | Este arquivo |

---

## Arquivos Modificados

### `app/ai/graph.py`
- Adicionada documentação de módulo com nome IRIS
- Importação de `ClassifierPrompts` e `ResponsePrompts`
- Método `_classify_intent()` agora usa `ClassifierPrompts.get_classification_prompt()`
- Método `_get_communication_style_prompt()` agora usa `ResponsePrompts.get_communication_style_prompt()`
- Método `_generate_response()` agora usa `ResponsePrompts.get_response_generation_prompt()`

### `app/ai/agents/reminder_agent.py`
- Adicionada documentação de módulo
- Importação de `ReminderPrompts` e `ReminderConstants`
- `system_prompt` agora retorna `ReminderPrompts.SYSTEM_PROMPT`
- Verificação de deleção usa `ReminderConstants.is_delete_request()`
- Verificação de resposta de tempo usa `ReminderConstants.is_time_response()`
- Extração de lembretes usa `ReminderPrompts.get_extraction_prompt()`
- Parse de tempo usa `ReminderConstants.parse_remind_time()`
- Formatação de tempo usa `ReminderConstants.format_remind_time()`
- Templates de confirmação usam `ReminderPrompts.TEMPLATES`

### `app/ai/agents/finance_agent.py`
- Adicionada documentação de módulo
- Importação de `FinancePrompts` e `FinanceConstants`
- Removidas constantes `EXPENSE_CATEGORIES` e `INCOME_CATEGORIES` (movidas para `FinanceConstants`)
- `system_prompt` agora retorna `FinancePrompts.SYSTEM_PROMPT`
- Classificação de intenção usa `FinancePrompts.get_intent_prompt()`
- Extração de transações usa `FinancePrompts.get_extraction_prompt()`
- Detecção de categoria usa `FinanceConstants.detect_category_in_message()`
- Identificação de deleção usa `FinancePrompts.get_delete_identification_prompt()`

### `app/ai/agents/meeting_agent.py`
- Adicionada documentação de módulo
- Importação de `MeetingPrompts`
- `system_prompt` agora retorna `MeetingPrompts.SYSTEM_PROMPT`
- Classificação de intenção usa `MeetingPrompts.get_intent_prompt()`
- Extração de agendamento usa `MeetingPrompts.get_schedule_extraction_prompt()`
- Análise de transcrição usa `MeetingPrompts.get_analysis_prompt()`

### `app/ai/agents/contact_agent.py`
- Adicionada documentação de módulo
- Importação de `ContactPrompts`
- Classificação de intenção usa `ContactPrompts.get_intent_classification_prompt()`
- Extração de contatos usa `ContactPrompts.get_contact_extraction_prompt()`

---

## Lógica Preservada

**IMPORTANTE**: Toda a lógica de processamento foi mantida exatamente igual. As mudanças foram apenas de organização:

- ✅ Fluxo de classificação de intenções
- ✅ Processamento de lembretes (único e múltiplos)
- ✅ Processamento financeiro (gastos, receitas, consultas)
- ✅ Processamento de reuniões (agendamento e análise)
- ✅ Processamento de contatos (criação, broadcast, agendamento)
- ✅ Gerenciamento de memória
- ✅ Cache de classificação
- ✅ RAG com embeddings
- ✅ Adaptação de estilo de comunicação

---

## Benefícios

1. **Manutenibilidade**: Prompts em arquivos separados são fáceis de encontrar e modificar
2. **Legibilidade**: Agentes focam apenas na lógica de processamento
3. **Testabilidade**: Prompts e constantes podem ser testados isoladamente
4. **Reutilização**: Constantes compartilhadas entre componentes
5. **Documentação**: Cada arquivo tem propósito claro e documentado

---

## Compatibilidade

- ✅ Compatível com versão anterior da API
- ✅ Sem mudanças no banco de dados
- ✅ Sem mudanças nos endpoints
- ✅ Sem mudanças no frontend

---

## Próximos Passos Recomendados

1. Executar testes para validar que nada quebrou
2. Revisar documentação de pontos críticos (`12-PONTOS_CRITICOS_MELHORIAS.md`)
3. Implementar melhorias de segurança prioritárias
4. Adicionar testes unitários para prompts e constantes
