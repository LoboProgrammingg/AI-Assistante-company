# Estrutura Reorganizada dos Agentes - IRIS

## Visão Geral da Nova Estrutura

A reorganização separou o código dos agentes em componentes modulares para facilitar manutenção e visualização.

```
app/ai/
├── agents/
│   ├── __init__.py
│   ├── prompts/                    # 📝 PROMPTS CENTRALIZADOS
│   │   ├── __init__.py
│   │   ├── classifier_prompts.py   # Classificação de intenções
│   │   ├── response_prompts.py     # Geração de respostas finais
│   │   ├── reminder_prompts.py     # Prompts do ReminderAgent
│   │   ├── finance_prompts.py      # Prompts do FinanceAgent
│   │   ├── meeting_prompts.py      # Prompts do MeetingAgent
│   │   └── contact_prompts.py      # Prompts do ContactAgent
│   │
│   ├── constants/                  # 📊 CONSTANTES E CONFIGURAÇÕES
│   │   ├── __init__.py
│   │   ├── finance_constants.py    # Categorias, keywords financeiros
│   │   └── reminder_constants.py   # Opções de tempo, keywords
│   │
│   ├── base_agent.py               # Classe base abstrata
│   ├── reminder_agent.py           # Lógica do ReminderAgent
│   ├── finance_agent.py            # Lógica do FinanceAgent
│   ├── meeting_agent.py            # Lógica do MeetingAgent
│   └── contact_agent.py            # Lógica do ContactAgent
│
├── graph.py                        # Orquestrador LangGraph
├── memory.py                       # Gerenciador de memória
├── iris_identity.py                # Identidade da IRIS
└── tools/                          # Ferramentas auxiliares
```

---

## Benefícios da Reorganização

### 1. Separação de Responsabilidades
- **Prompts**: Fácil de visualizar e modificar textos enviados ao LLM
- **Constantes**: Configurações centralizadas e reutilizáveis
- **Agentes**: Apenas lógica de processamento

### 2. Facilidade de Manutenção
```python
# Antes: Prompt inline no código
def process(self, message):
    prompt = f"""
    Você é um assistente...
    [100 linhas de prompt]
    """
    
# Depois: Prompt importado
from app.ai.agents.prompts.reminder_prompts import ReminderPrompts

def process(self, message):
    prompt = ReminderPrompts.get_extraction_prompt(
        context=context,
        current_time=time,
        message=message
    )
```

### 3. Testabilidade
```python
# Agora é possível testar prompts isoladamente
def test_extraction_prompt():
    prompt = ReminderPrompts.get_extraction_prompt(
        context="Teste",
        current_time="01/01/2025 10:00",
        message="Me lembre de reunião às 14h"
    )
    assert "reunião" in prompt
    assert "14h" in prompt
```

### 4. Reutilização
```python
# Constantes podem ser usadas em múltiplos lugares
from app.ai.agents.constants.finance_constants import FinanceConstants

# No agente
category = FinanceConstants.detect_category_in_message(message)

# Em testes
categories = FinanceConstants.get_all_expense_categories()

# Em validações
if category not in FinanceConstants.EXPENSE_CATEGORIES:
    raise ValueError("Categoria inválida")
```

---

## Estrutura dos Arquivos de Prompts

### `classifier_prompts.py`
```python
class ClassifierPrompts:
    @staticmethod
    def get_classification_prompt(
        conversation_history: str,
        message: str,
        audio_hint: str = ""
    ) -> str:
        """Prompt para classificar intenção da mensagem."""
        
    @staticmethod
    def get_audio_hint(message_length: int) -> str:
        """Dica adicional para áudios longos."""
```

### `response_prompts.py`
```python
class ResponsePrompts:
    @staticmethod
    def get_communication_style_prompt(memory: dict) -> str:
        """Estilo de comunicação baseado no comportamento."""
        
    @staticmethod
    def get_response_generation_prompt(
        user_name: str,
        comm_style: str,
        context_prompt: str,
        next_action: str,
        entities: Dict[str, Any],
        last_message: str
    ) -> str:
        """Prompt para geração de resposta final."""
```

### `reminder_prompts.py`
```python
class ReminderPrompts:
    SYSTEM_PROMPT = "..."  # Prompt de sistema
    
    TEMPLATES = {
        "single_confirmation": "...",
        "multiple_confirmation": "...",
        "delete_success": "...",
    }
    
    @staticmethod
    def get_extraction_prompt(...) -> str:
        """Prompt para extrair lembretes."""
        
    @staticmethod
    def get_delete_identification_prompt(...) -> str:
        """Prompt para identificar lembrete a deletar."""
```

---

## Estrutura dos Arquivos de Constantes

### `finance_constants.py`
```python
class FinanceConstants:
    # Categorias de despesa com keywords
    EXPENSE_CATEGORIES = {
        "Alimentação": ["almoço", "jantar", "café", ...],
        "Transporte": ["uber", "gasolina", ...],
        ...
    }
    
    # Categorias de receita
    INCOME_CATEGORIES = {...}
    
    # Keywords para detecção
    CATEGORY_KEYWORDS = {...}
    
    @classmethod
    def detect_category_in_message(cls, message: str) -> Optional[str]:
        """Detecta categoria mencionada na mensagem."""
        
    @classmethod
    def get_all_expense_categories(cls) -> List[str]:
        """Lista todas as categorias de despesa."""
```

### `reminder_constants.py`
```python
class ReminderConstants:
    # Tipos de recorrência
    RECURRENCE_TYPES = ["once", "daily", "weekly", ...]
    
    # Mapeamento de opções numéricas
    TIME_OPTIONS = {"1": 0, "2": 5, "3": 15, ...}
    
    # Keywords
    DELETE_KEYWORDS = ["cancele", "delete", ...]
    TIME_KEYWORDS = ["min", "hora", ...]
    
    @classmethod
    def is_delete_request(cls, message: str) -> bool:
        """Verifica se é pedido de deleção."""
        
    @classmethod
    def parse_remind_time(cls, message: str) -> int:
        """Extrai minutos de antecedência."""
        
    @classmethod
    def format_remind_time(cls, minutes: int) -> str:
        """Formata tempo em texto legível."""
```

---

## Como Modificar Prompts

### 1. Alterar Texto de um Prompt
```python
# Edite o arquivo correspondente
# app/ai/agents/prompts/reminder_prompts.py

class ReminderPrompts:
    SYSTEM_PROMPT = """
    Você é um assistente especializado...
    
    # Adicione novas instruções aqui
    Nova regra: ...
    """
```

### 2. Adicionar Nova Template de Resposta
```python
# app/ai/agents/prompts/reminder_prompts.py

TEMPLATES = {
    "single_confirmation": "...",
    "multiple_confirmation": "...",
    # Nova template
    "reminder_updated": (
        "✅ *Lembrete atualizado!*\n\n"
        "📌 {title}\n"
        "📅 Nova data: {scheduled_time}"
    ),
}
```

### 3. Adicionar Nova Categoria Financeira
```python
# app/ai/agents/constants/finance_constants.py

EXPENSE_CATEGORIES = {
    ...
    # Nova categoria
    "Pets": ["veterinário", "ração", "pet shop", "banho e tosa"],
}
```

---

## Migração de Código Existente

### Antes (código antigo)
```python
class ReminderAgent:
    def process(self, message):
        # Prompt inline - difícil de manter
        prompt = f"""
        Analise a mensagem...
        [muitas linhas]
        """
        
        # Keywords inline - duplicação
        delete_keywords = ["cancele", "delete", ...]
        if any(kw in message for kw in delete_keywords):
            ...
```

### Depois (código refatorado)
```python
from app.ai.agents.prompts.reminder_prompts import ReminderPrompts
from app.ai.agents.constants.reminder_constants import ReminderConstants

class ReminderAgent:
    @property
    def system_prompt(self) -> str:
        return ReminderPrompts.SYSTEM_PROMPT
    
    def process(self, message):
        # Prompt centralizado
        prompt = ReminderPrompts.get_extraction_prompt(...)
        
        # Verificação usando constantes
        if ReminderConstants.is_delete_request(message):
            ...
```

---

## Checklist de Migração

- [x] Criar estrutura de pastas `prompts/` e `constants/`
- [x] Extrair prompts do `graph.py` para `classifier_prompts.py`
- [x] Extrair prompts de resposta para `response_prompts.py`
- [x] Migrar prompts do `ReminderAgent`
- [x] Migrar prompts do `FinanceAgent`
- [x] Migrar prompts do `MeetingAgent`
- [x] Migrar prompts do `ContactAgent`
- [x] Extrair constantes financeiras
- [x] Extrair constantes de lembretes
- [x] Atualizar imports em todos os agentes
- [x] Criar identidade IRIS
