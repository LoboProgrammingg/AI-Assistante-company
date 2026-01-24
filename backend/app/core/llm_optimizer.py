"""
Otimizador de chamadas LLM para IRIS.
Combina prompts, usa cache e reduz latência.
"""

import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


logger = logging.getLogger(__name__)

# Cache em memória para respostas recentes
try:
    from app.services.cache_service import cache_service

    CACHE_AVAILABLE = cache_service.is_available
except ImportError:
    cache_service = None
    CACHE_AVAILABLE = False


@dataclass
class LLMOptimizationConfig:
    """Configuração de otimização LLM."""

    enable_prompt_caching: bool = True
    cache_ttl_seconds: int = 300  # 5 minutos
    enable_combined_prompts: bool = True
    max_prompt_length: int = 10000
    enable_response_streaming: bool = False


class PromptCache:
    """Cache de prompts e respostas para evitar chamadas duplicadas."""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        self._cache: Dict[str, Tuple[str, float]] = {}
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._hits = 0
        self._misses = 0

    def _generate_key(self, prompt: str, context_hash: str = "") -> str:
        """Gera chave única para o prompt."""
        content = f"{prompt}:{context_hash}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def get(self, prompt: str, context_hash: str = "") -> Optional[str]:
        """Busca resposta no cache."""
        key = self._generate_key(prompt, context_hash)

        if key in self._cache:
            response, timestamp = self._cache[key]
            if time.time() - timestamp < self.ttl_seconds:
                self._hits += 1
                logger.debug(f"Cache hit para prompt (key={key[:8]}...)")
                return response
            else:
                del self._cache[key]

        self._misses += 1
        return None

    def set(self, prompt: str, response: str, context_hash: str = "") -> None:
        """Armazena resposta no cache."""
        if len(self._cache) >= self.max_size:
            self._evict_oldest()

        key = self._generate_key(prompt, context_hash)
        self._cache[key] = (response, time.time())

    def _evict_oldest(self) -> None:
        """Remove entradas mais antigas."""
        if not self._cache:
            return
        oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
        del self._cache[oldest_key]

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do cache."""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {
            "size": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.1f}%",
        }

    def clear(self) -> None:
        """Limpa o cache."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0


class LLMOptimizer:
    """
    Otimizador de chamadas LLM.

    Estratégias:
    - Cache de respostas frequentes
    - Combinação de prompts quando possível
    - Detecção de intenção rápida para casos simples
    - Fallback inteligente
    """

    _instance: Optional["LLMOptimizer"] = None

    def __new__(cls, config: LLMOptimizationConfig = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config: LLMOptimizationConfig = None):
        if self._initialized:
            return

        self.config = config or LLMOptimizationConfig()
        self.prompt_cache = PromptCache(ttl_seconds=self.config.cache_ttl_seconds)
        self._call_count = 0
        self._saved_calls = 0
        self._initialized = True

        logger.info("LLMOptimizer inicializado")

    def should_use_fast_classification(self, message: str) -> Tuple[bool, Optional[str]]:
        """
        Verifica se pode usar classificação rápida sem LLM.

        Returns:
            Tuple[bool, Optional[str]]: (usar_fast, intent_detectada)
        """
        message_lower = message.lower().strip()

        # Padrões óbvios de intenção
        # IMPORTANTE: 
        # - "agendar reunião" é REMINDER, não MEETING
        # - "anota uma tarefa" é GENERAL (usa Todoist)
        # - MEETING é apenas para transcrições de reuniões já realizadas
        fast_patterns = {
            # GENERAL tem prioridade para tarefas do Todoist
            "general": [
                "anota uma tarefa",
                "anote uma tarefa",
                "cria uma tarefa",
                "criar tarefa",
                "adiciona tarefa",
                "adicione tarefa",
                "coloca no todoist",
                "add no todoist",
                "tarefa no todoist",
                "nova tarefa",
                "pesquisa sobre",
                "busca sobre",
                "o que é",
                "quem é",
                "como funciona",
                "me explica",
                "me conta",
            ],
            "reminder": [
                "me lembre",
                "lembre-me",
                "lembrete",
                "não esquecer",
                "me avise",
                "avisa quando",
                "alarme",
                "agenda pra",
                "agendar reunião",
                "marcar reunião",
                "agende uma reunião",
                "agende reunião",
                "marca um compromisso",
                "compromisso às",
                "amanhã às",
                "hoje às",
                "delete o lembrete",
                "deletar lembrete",
                "remover lembrete",
                "cancela o compromisso",
                "mude o horário",
            ],
            "finance": [
                "gastei",
                "paguei",
                "comprei",
                "recebi",
                "ganhei",
                "quanto gastei",
                "meus gastos",
                "minhas despesas",
                "quanto tenho",
                "meu saldo",
                "extrato",
                "delete o gasto",
                "deletar gasto",
                "remover gasto",
                "apaga o gasto",
                "delete o uber",
                "delete a fralda",
                "na verdade eram",
                "corrija o valor",
                "altere o valor",
            ],
            "meeting": [
                "agenda", 
                "agende", 
                "agend", 
                "marcar", 
                "marc", 
                "compromisso", 
                "reunião", 
                "reuniao", 
                "meeting", 
                "aula", 
                "consulta", 
                "evento",
                "google calendar", 
                "calendário",
            ],
            "transcription": [
                "transcrição da reunião",
                "resumo da reunião",
                "ata da reunião",
                "resuma a reunião",
                "analise essa reunião",
                "o que foi discutido na reunião",
                "transcrição", "transcricao", "resuma", "resumir", 
                "analise", "analisar"
            ],
            "contact": [
                "salvar contato",
                "novo contato",
                "adicionar contato",
                "enviar mensagem para",
                "manda mensagem para",
                "broadcast",
                "lista de contatos",
                "meus contatos",
                "delete o contato",
                "deletar contato",
                "remover contato",
            ],
        }

        for intent, patterns in fast_patterns.items():
            for pattern in patterns:
                if pattern in message_lower:
                    logger.debug(f"Fast classification: {intent} (pattern: {pattern})")
                    self._saved_calls += 1
                    return True, intent

        return False, None

    def get_cached_response(self, prompt: str, context: Dict[str, Any] = None) -> Optional[str]:
        """Busca resposta em cache."""
        if not self.config.enable_prompt_caching:
            return None

        context_hash = self._hash_context(context) if context else ""
        return self.prompt_cache.get(prompt, context_hash)

    def cache_response(self, prompt: str, response: str, context: Dict[str, Any] = None) -> None:
        """Armazena resposta em cache."""
        if not self.config.enable_prompt_caching:
            return

        context_hash = self._hash_context(context) if context else ""
        self.prompt_cache.set(prompt, response, context_hash)

    def _hash_context(self, context: Dict[str, Any]) -> str:
        """Gera hash do contexto relevante para cache."""
        relevant_keys = ["user_id", "intent", "timezone"]
        relevant = {k: context.get(k) for k in relevant_keys if k in context}
        return hashlib.md5(str(relevant).encode()).hexdigest()[:16]

    def combine_classification_and_extraction(
        self, message: str, conversation_history: str = "", intent_hint: str = None
    ) -> str:
        """
        Gera prompt combinado para classificação e extração.
        Reduz de 2 chamadas LLM para 1.
        """
        hint_section = ""
        if intent_hint:
            hint_section = f"\nDica: A mensagem parece estar relacionada a '{intent_hint}'."

        return f"""Analise a mensagem do usuário e retorne um JSON com:
1. A intenção classificada
2. As entidades extraídas

Histórico da conversa:
{conversation_history}

Mensagem atual: "{message}"
{hint_section}

Classifique a intenção como UMA das seguintes:
- "reminder": lembretes, compromissos, avisos
- "finance": gastos, receitas, consultas financeiras
- "meeting": reuniões, transcrições, agendamentos de call
- "contact": salvar/buscar contatos, enviar mensagens
- "general": conversas gerais, perguntas, saudações

Extraia entidades relevantes baseado na intenção:
- Para reminder: title, scheduled_time, description
- Para finance: amount, category, description, type (expense/income)
- Para meeting: title, scheduled_time, participants, location
- Para contact: name, phone, email, action

Responda APENAS com JSON válido:
{{
    "intent": "...",
    "confidence": 0.0-1.0,
    "entities": {{...}},
    "reasoning": "breve explicação"
}}"""

    def track_call(self) -> None:
        """Registra uma chamada LLM."""
        self._call_count += 1

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de otimização."""
        return {
            "total_calls": self._call_count,
            "saved_calls": self._saved_calls,
            "cache_stats": self.prompt_cache.get_stats(),
            "optimization_rate": f"{(self._saved_calls / max(1, self._call_count + self._saved_calls) * 100):.1f}%",
        }


# Instância global
_optimizer: Optional[LLMOptimizer] = None


def get_optimizer() -> LLMOptimizer:
    """Retorna instância global do otimizador."""
    global _optimizer
    if _optimizer is None:
        _optimizer = LLMOptimizer()
    return _optimizer
