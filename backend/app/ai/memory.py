import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.services.memory_service import MemoryService

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    Gerenciador central de memória do usuário para o agente de IA.
    Responsável por manter contexto, preferências e fatos aprendidos.
    """

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self.service = MemoryService(db)
        self._cache: Dict[str, Any] = {}

    def get_full_context(self) -> Dict[str, Any]:
        """
        Retorna contexto completo para o agente.

        Returns:
            Dict com conversation, preferences, facts, stats
        """
        if "full_context" in self._cache:
            return self._cache["full_context"]

        context = self.service.get_full_context(self.user_id)
        self._cache["full_context"] = context
        return context

    def get_conversation_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retorna histórico de conversa expandido."""
        return self.service.get_conversation_context(self.user_id, limit)

    def get_user_preferences(self) -> Dict[str, Any]:
        """Retorna preferências do usuário."""
        return self.service.get_user_preferences(self.user_id)

    def get_learned_facts(self) -> Dict[str, Any]:
        """Retorna fatos aprendidos sobre o usuário."""
        return self.service.get_learned_facts(self.user_id)

    def build_context_prompt(self) -> str:
        """
        Constrói prompt de contexto para o agente.

        Returns:
            String formatada com contexto do usuário
        """
        context = self.get_full_context()
        facts = context.get("facts", {})
        preferences = context.get("preferences", {})
        stats = context.get("stats", {})
        conversation = context.get("conversation", [])

        parts = ["CONTEXTO DO USUÁRIO (MEMÓRIA DE LONGO PRAZO):"]

        if facts.get("name"):
            parts.append(f"Nome: {facts['name']}")

        if preferences.get("timezone"):
            parts.append(f"Timezone: {preferences['timezone']}")

        # Informações importantes aprendidas
        if facts.get("profissao"):
            profissao = facts["profissao"] if isinstance(facts["profissao"], list) else [facts["profissao"]]
            parts.append(f"Profissão: {', '.join(profissao)}")

        if facts.get("familia"):
            familia = facts["familia"] if isinstance(facts["familia"], list) else [facts["familia"]]
            parts.append(f"Família: {', '.join(familia)}")

        if facts.get("objetivo"):
            objetivo = facts["objetivo"] if isinstance(facts["objetivo"], list) else [facts["objetivo"]]
            parts.append(f"Objetivos: {', '.join(objetivo)}")

        if facts.get("preferencia"):
            preferencia = facts["preferencia"] if isinstance(facts["preferencia"], list) else [facts["preferencia"]]
            parts.append(f"Preferências: {', '.join(preferencia)}")

        # Outros fatos relevantes
        other_facts = {
            k: v for k, v in facts.items() if k not in ["name", "profissao", "familia", "objetivo", "preferencia"]
        }
        if other_facts:
            parts.append(f"Outros fatos: {other_facts}")

        if stats:
            parts.append(
                f"Estatísticas: {stats.get('total_messages', 0)} mensagens, "
                f"{stats.get('reminders_created', 0)} lembretes, "
                f"{stats.get('transactions_logged', 0)} transações"
            )

        # Dados do usuário (finanças, lembretes, reuniões)
        user_data = context.get("user_data", {})

        # Finanças
        finances = user_data.get("finances", {})
        this_month = finances.get("this_month", {})
        if this_month.get("total_expense", 0) > 0 or this_month.get("total_income", 0) > 0:
            parts.append(f"\nRESUMO FINANCEIRO DO MÊS:")
            parts.append(f"  • Gastos: R$ {this_month.get('total_expense', 0):.2f}")
            parts.append(f"  • Receitas: R$ {this_month.get('total_income', 0):.2f}")
            parts.append(f"  • Saldo: R$ {this_month.get('balance', 0):.2f}")

            # Comparação com mês anterior
            last_month = finances.get("last_month_expense", 0)
            if last_month > 0:
                change = finances.get("expense_change", 0)
                if change > 0:
                    parts.append(f"  • Comparado ao mês passado: +R$ {change:.2f} (gastou mais)")
                elif change < 0:
                    parts.append(f"  • Comparado ao mês passado: -R$ {abs(change):.2f} (economizou)")

            # Por categoria
            by_category = this_month.get("by_category", {})
            if by_category:
                top_cats = sorted(by_category.items(), key=lambda x: x[1], reverse=True)[:3]
                parts.append(f"  • Maiores gastos: {', '.join([f'{c}: R${v:.0f}' for c,v in top_cats])}")

        # Lembretes
        reminders = user_data.get("reminders", {})
        upcoming = reminders.get("upcoming", [])
        if upcoming:
            parts.append(f"\nLEMBRETES PRÓXIMOS:")
            for r in upcoming[:3]:
                parts.append(f"  • {r.get('title')} - {r.get('scheduled_time')}")

        # Reuniões
        meetings = user_data.get("meetings", {})
        recent_meetings = meetings.get("recent", [])
        if recent_meetings:
            parts.append(f"\nREUNIÕES RECENTES:")
            for m in recent_meetings[:2]:
                parts.append(f"  • {m.get('title')} ({m.get('date')})")

        # Contatos
        contacts = user_data.get("contacts", {})
        if contacts.get("total", 0) > 0:
            parts.append(f"\nCONTATOS ({contacts.get('total')} total):")
            by_group = contacts.get("by_group", {})
            for group, group_contacts in by_group.items():
                group_label = group.replace("_", " ").title()
                contact_names = [c.get("name") for c in group_contacts[:5]]
                parts.append(
                    f"  • {group_label}: {', '.join(contact_names)}"
                    + (f" (+{len(group_contacts)-5} mais)" if len(group_contacts) > 5 else "")
                )

        # Documentos (RAG)
        documents = user_data.get("documents", {})
        if documents.get("count", 0) > 0:
            parts.append(f"\nDOCUMENTOS DO USUÁRIO ({documents.get('count')} para contexto IA):")
            for doc in documents.get("documents", [])[:5]:
                parts.append(f"  📄 *{doc.get('title')}* [{doc.get('category')}]")
                if doc.get("content_preview"):
                    parts.append(f"     Conteúdo: {doc.get('content_preview')[:200]}...")

        if conversation:
            parts.append("\nÚltimas mensagens (contexto expandido):")
            # Aumentar para 15 mensagens para melhor contexto
            for msg in conversation[-15:]:
                role = "Usuário" if msg["role"] == "user" else "Assistente"
                intent = f" [{msg.get('intent', '')}]" if msg.get("intent") else ""
                content = msg["content"][:150] + "..." if len(msg["content"]) > 150 else msg["content"]
                parts.append(f"  {role}{intent}: {content}")

        # Adicionar ações recentes confirmadas para evitar alucinações
        recent_actions = self.get_recent_actions(5)
        if recent_actions:
            parts.append("\nAÇÕES RECENTES CONFIRMADAS (NÃO INVENTE - USE APENAS ESTES DADOS):")
            for action in recent_actions:
                action_type = action.get("action", "")
                entities = action.get("entities", {})
                timestamp = action.get("timestamp", "")[:16]

                if action_type == "create_finance":
                    finance = entities.get("finance", {})
                    parts.append(
                        f"  ✅ Transação registrada: {finance.get('description', 'N/A')} - R${finance.get('amount', 0)} ({timestamp})"
                    )
                elif action_type == "create_reminder":
                    reminder = entities.get("reminder", {})
                    parts.append(f"  ✅ Lembrete criado: {reminder.get('title', 'N/A')} ({timestamp})")

        return "\n".join(parts)

    def update_after_action(self, action: str, entities: Dict[str, Any]) -> None:
        """
        Atualiza memória após uma ação ser executada.

        Args:
            action: Ação executada (create_reminder, create_finance, etc.)
            entities: Entidades processadas
        """
        self.service.update_after_action(self.user_id, action, entities)

        # Registrar ação recente para evitar alucinações
        self._record_recent_action(action, entities)
        self._invalidate_cache()

    def _record_recent_action(self, action: str, entities: Dict[str, Any]) -> None:
        """Registra ação recente para contexto preciso."""
        recent_actions = self.service.get_memory(self.user_id, "recent_actions") or {"actions": []}

        action_record = {
            "action": action,
            "entities": entities,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "confirmed": True,  # Ação foi executada com sucesso
        }

        # Manter apenas as últimas 20 ações
        recent_actions["actions"] = recent_actions["actions"][-19:] + [action_record]
        self.service.set_memory(self.user_id, "recent_actions", recent_actions)
        logger.info(f"Ação registrada: {action}")

    def get_recent_actions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retorna ações recentes confirmadas."""
        recent = self.service.get_memory(self.user_id, "recent_actions") or {"actions": []}
        return recent["actions"][-limit:]

    def was_action_performed(self, action_type: str, description: str = None) -> bool:
        """Verifica se uma ação específica foi realizada recentemente."""
        recent = self.get_recent_actions(5)
        for action in recent:
            if action["action"] == action_type:
                if description:
                    entities = action.get("entities", {})
                    finance = entities.get("finance", {})
                    if description.lower() in str(finance.get("description", "")).lower():
                        return True
                else:
                    return True
        return False

    def learn_from_message(self, message: str, intent: str, entities: Dict[str, Any], response: str = "") -> None:
        """
        Aprende com a interação do usuário.

        Args:
            message: Mensagem do usuário
            intent: Intenção detectada
            entities: Entidades extraídas
            response: Resposta gerada pela IA
        """
        self._learn_name(message)
        self._learn_time_preferences(intent, entities)
        self._learn_category_preferences(intent, entities)
        self.learn_important_info(message, response, intent)
        self.analyze_user_behavior(message)
        self._invalidate_cache()

    def _learn_name(self, message: str) -> None:
        """Detecta e salva nome do usuário."""
        patterns = [
            r"meu nome (?:é|e) (\w+)",
            r"pode me chamar de (\w+)",
            r"sou (?:o|a) (\w+)",
            r"me chamo (\w+)",
        ]

        message_lower = message.lower()

        for pattern in patterns:
            match = re.search(pattern, message_lower)
            if match:
                name = match.group(1).capitalize()
                current_facts = self.get_learned_facts()
                if current_facts.get("name") != name:
                    self.service.add_learned_fact(self.user_id, "name", name)
                    logger.info(f"Nome aprendido: {name}")
                break

    def learn_important_info(self, message: str, response: str, intent: str) -> None:
        """
        Aprende informações importantes do usuário para memória de longo prazo.

        Exemplos de informações importantes:
        - Profissão, trabalho
        - Família (esposa, filhos, pais)
        - Hobbies, interesses
        - Preferências
        - Objetivos, metas
        """
        important_patterns = {
            "profissao": [
                r"(?:trabalho|sou|atuo) (?:como|de) (\w+(?:\s+\w+)?)",
                r"minha profiss[aã]o (?:é|e) (\w+(?:\s+\w+)?)",
            ],
            "familia": [
                r"(?:minha|meu) (esposa|marido|filho|filha|m[aã]e|pai) (?:se chama |é |)(\w+)",
                r"tenho (\d+) filhos?",
            ],
            "objetivo": [
                r"(?:meu|minha) (?:objetivo|meta) (?:é|e) (.+?)(?:\.|$)",
                r"quero (?:economizar|juntar|guardar) (.+?)(?:\.|$)",
            ],
            "preferencia": [
                r"(?:prefiro|gosto de) (.+?)(?:\.|$)",
            ],
        }

        message_lower = message.lower()
        current_facts = self.get_learned_facts()

        for fact_type, patterns in important_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, message_lower)
                if match:
                    info = match.group(1) if len(match.groups()) == 1 else " ".join(match.groups())

                    # Armazenar como lista se já existir
                    existing = current_facts.get(fact_type, [])
                    if isinstance(existing, str):
                        existing = [existing]

                    if info not in existing:
                        existing.append(info)
                        self.service.add_learned_fact(self.user_id, fact_type, existing)
                        logger.info(f"Info importante aprendida [{fact_type}]: {info}")

    def _learn_time_preferences(self, intent: str, entities: Dict[str, Any]) -> None:
        """Aprende preferências de horário."""
        if intent != "reminder":
            return

        reminder = entities.get("reminder", {})
        scheduled_time = reminder.get("scheduled_time")

        if scheduled_time:
            try:
                dt = datetime.fromisoformat(scheduled_time.replace("Z", "+00:00"))
                hour = dt.hour

                time_stats = self.service.get_memory(self.user_id, "time_preferences") or {}
                hour_counts = time_stats.get("hour_counts", {})
                hour_counts[str(hour)] = hour_counts.get(str(hour), 0) + 1

                time_stats["hour_counts"] = hour_counts
                self.service.set_memory(self.user_id, "time_preferences", time_stats)
            except:
                pass

    def _learn_category_preferences(self, intent: str, entities: Dict[str, Any]) -> None:
        """Aprende preferências de categoria financeira."""
        if intent != "finance":
            return

        finance = entities.get("finance", {})
        category = finance.get("category")

        if category:
            cat_stats = self.service.get_memory(self.user_id, "category_preferences") or {}
            cat_counts = cat_stats.get("category_counts", {})
            cat_counts[category] = cat_counts.get(category, 0) + 1

            cat_stats["category_counts"] = cat_counts
            self.service.set_memory(self.user_id, "category_preferences", cat_stats)

    def get_personalization_hints(self) -> Dict[str, Any]:
        """
        Retorna dicas de personalização baseadas no histórico.

        Returns:
            Dict com sugestões de personalização
        """
        hints = {}

        time_prefs = self.service.get_memory(self.user_id, "time_preferences") or {}
        hour_counts = time_prefs.get("hour_counts", {})

        if hour_counts:
            most_common_hour = max(hour_counts, key=hour_counts.get)
            hints["preferred_reminder_hour"] = int(most_common_hour)

        cat_prefs = self.service.get_memory(self.user_id, "category_preferences") or {}
        cat_counts = cat_prefs.get("category_counts", {})

        if cat_counts:
            sorted_cats = sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)
            hints["top_categories"] = [cat for cat, _ in sorted_cats[:5]]

        # Adicionar estilo de comunicação
        hints["communication_style"] = self.get_communication_style()

        return hints

    def analyze_user_behavior(self, message: str) -> None:
        """
        Analisa o comportamento do usuário para adaptar o estilo de comunicação.

        Args:
            message: Mensagem do usuário
        """
        behavior = self.service.get_memory(self.user_id, "behavior_analysis") or {
            "message_count": 0,
            "emoji_usage": 0,
            "informal_language": 0,
            "question_count": 0,
            "greeting_style": "formal",
            "avg_message_length": 0,
            "humor_detected": 0,
            "urgency_patterns": 0,
        }

        message_lower = message.lower()

        # Contador de mensagens
        behavior["message_count"] = behavior.get("message_count", 0) + 1

        # Análise de emoji
        import re

        emoji_pattern = re.compile(
            "[" "\U0001f600-\U0001f64f" "\U0001f300-\U0001f5ff" "\U0001f680-\U0001f6ff" "\U0001f1e0-\U0001f1ff" "]+",
            flags=re.UNICODE,
        )
        if emoji_pattern.search(message):
            behavior["emoji_usage"] = behavior.get("emoji_usage", 0) + 1

        # Linguagem informal
        informal_words = [
            "vc",
            "tb",
            "pq",
            "blz",
            "vlw",
            "flw",
            "tmj",
            "kk",
            "haha",
            "rsrs",
            "eae",
            "ae",
            "mano",
            "cara",
        ]
        if any(word in message_lower for word in informal_words):
            behavior["informal_language"] = behavior.get("informal_language", 0) + 1

        # Perguntas
        if "?" in message:
            behavior["question_count"] = behavior.get("question_count", 0) + 1

        # Estilo de saudação
        formal_greetings = ["bom dia", "boa tarde", "boa noite", "olá"]
        informal_greetings = ["oi", "eae", "e aí", "fala", "salve"]

        if any(g in message_lower for g in formal_greetings):
            behavior["greeting_style"] = "formal"
        elif any(g in message_lower for g in informal_greetings):
            behavior["greeting_style"] = "informal"

        # Média de tamanho de mensagem
        total_len = behavior.get("avg_message_length", 0) * (behavior["message_count"] - 1)
        behavior["avg_message_length"] = (total_len + len(message)) / behavior["message_count"]

        # Humor/piadas
        humor_words = ["haha", "kkkk", "rsrs", "lol", "kkk", "hehe", "risos"]
        if any(word in message_lower for word in humor_words):
            behavior["humor_detected"] = behavior.get("humor_detected", 0) + 1

        # Padrões de urgência
        urgency_words = ["urgente", "agora", "rápido", "logo", "imediatamente", "preciso"]
        if any(word in message_lower for word in urgency_words):
            behavior["urgency_patterns"] = behavior.get("urgency_patterns", 0) + 1

        self.service.set_memory(self.user_id, "behavior_analysis", behavior)

    def get_communication_style(self) -> Dict[str, Any]:
        """
        Retorna o estilo de comunicação recomendado baseado no comportamento do usuário.

        Returns:
            Dict com recomendações de estilo
        """
        behavior = self.service.get_memory(self.user_id, "behavior_analysis") or {}
        msg_count = behavior.get("message_count", 1)

        if msg_count < 5:
            return {"style": "neutral", "formality": "balanced", "use_emoji": False}

        # Calcular porcentagens
        emoji_ratio = behavior.get("emoji_usage", 0) / msg_count
        informal_ratio = behavior.get("informal_language", 0) / msg_count
        humor_ratio = behavior.get("humor_detected", 0) / msg_count

        style = {
            "style": "friendly",
            "formality": "balanced",
            "use_emoji": emoji_ratio > 0.2,
            "be_casual": informal_ratio > 0.3,
            "add_humor": humor_ratio > 0.15,
            "greeting_style": behavior.get("greeting_style", "formal"),
            "message_length": "short" if behavior.get("avg_message_length", 50) < 30 else "detailed",
        }

        # Determinar formalidade
        if informal_ratio > 0.4:
            style["formality"] = "casual"
        elif informal_ratio < 0.1:
            style["formality"] = "formal"

        return style

    def _invalidate_cache(self) -> None:
        """Invalida cache local."""
        self._cache.clear()

    def clear_memory(self) -> int:
        """
        Limpa toda a memória do usuário.

        Returns:
            Quantidade de registros removidos
        """
        self._invalidate_cache()
        return self.service.clear_user_memory(self.user_id)
