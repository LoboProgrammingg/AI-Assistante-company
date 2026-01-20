"""
Agente especializado em lembretes e agendamentos.
Utiliza prompts e constantes centralizados para fácil manutenção.
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any

from app.ai.agents.base_agent import BaseAgent
from app.ai.agents.prompts.reminder_prompts import ReminderPrompts
from app.ai.agents.constants.reminder_constants import ReminderConstants
from app.utils.timezone_helper import get_current_time_for_user

logger = logging.getLogger(__name__)


class ReminderAgent(BaseAgent):
    """Agente especializado em lembretes e agendamentos."""

    def __init__(self):
        super().__init__(
            name="ReminderAgent",
            description="Especialista em criar, gerenciar e interpretar lembretes e compromissos",
            temperature=0.3
        )

    @property
    def system_prompt(self) -> str:
        return ReminderPrompts.SYSTEM_PROMPT

    def process_sync(
        self,
        message: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Processa mensagem relacionada a lembretes (versão síncrona)."""
        
        user_timezone = context.get("timezone", "America/Sao_Paulo")
        current_time = get_current_time_for_user(user_timezone)
        
        # Verificar se é pedido de cancelamento/deleção
        if ReminderConstants.is_delete_request(message):
            return self._handle_delete_sync(message, context)
        
        # Verificar se é resposta sobre tempo de antecedência
        pending_reminder = context.get("pending_reminder")
        if not pending_reminder:
            pending_reminder = context.get("memory", {}).get("pending_reminder")
        
        if pending_reminder and ReminderConstants.is_time_response(message):
            return self._complete_reminder_with_time_sync(message, pending_reminder, context)
        
        extraction_prompt = ReminderPrompts.get_extraction_prompt(
            context=self.format_context(context),
            current_time=current_time.strftime("%d/%m/%Y %H:%M"),
            message=message
        )

        try:
            response = self.invoke_llm_sync(extraction_prompt)
            
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                extracted = json.loads(response[json_start:json_end])
            else:
                extracted = {"needs_clarification": True}
            
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Erro ao extrair entidades: {e}")
            extracted = {
                "needs_clarification": True,
                "clarification_question": "Desculpe, não entendi bem. Pode me dizer quando você quer ser lembrado?"
            }

        if extracted.get("needs_clarification"):
            response_text = extracted.get(
                "clarification_question",
                "Poderia me dar mais detalhes sobre o lembrete?"
            )
            return {
                "response": response_text,
                "entities": {},
                "next_action": "await_clarification",
                "confidence": 0.0
            }

        # Suporte a múltiplos lembretes
        reminders = extracted.get("reminders", [])
        
        # Compatibilidade: se veio no formato antigo, converter
        if not reminders and extracted.get("title"):
            reminders = [extracted]
        
        if not reminders:
            return {
                "response": "Não consegui identificar os lembretes. Pode repetir?",
                "entities": {},
                "next_action": "await_clarification",
                "confidence": 0.0
            }

        # Verificar se algum lembrete precisa de tempo de antecedência
        reminders_need_time = [r for r in reminders if r.get("remind_before_minutes", 0) == 0]
        
        if reminders_need_time:
            # Se múltiplos lembretes, perguntar uma vez e aplicar para todos
            if len(reminders) > 1:
                titles = "\n".join([f"• *{r.get('title')}* - {self._format_datetime(r.get('scheduled_time'))}" for r in reminders])
                return {
                    "response": (
                        f"⏰ Vou agendar {len(reminders)} lembretes:\n\n{titles}\n\n"
                        f"Quanto tempo antes você quer ser lembrado?\n\n"
                        f"1. Na hora\n"
                        f"2. 5 minutos antes\n"
                        f"3. 15 minutos antes\n"
                        f"4. 30 minutos antes\n"
                        f"5. 1 hora antes\n\n"
                        f"_Responda com o número (aplicarei para todos)_"
                    ),
                    "entities": {"pending_reminders": reminders},
                    "next_action": "await_remind_time",
                    "confidence": 0.9
                }
            else:
                reminder = reminders[0]
                return {
                    "response": (
                        f"⏰ Vou agendar: *{reminder.get('title')}* para {self._format_datetime(reminder.get('scheduled_time'))}\n\n"
                        f"Quanto tempo antes você quer ser lembrado?\n\n"
                        f"1. Na hora\n"
                        f"2. 5 minutos antes\n"
                        f"3. 15 minutos antes\n"
                        f"4. 30 minutos antes\n"
                        f"5. 1 hora antes\n\n"
                        f"_Responda com o número ou digite o tempo (ex: 20 min)_"
                    ),
                    "entities": {"pending_reminder": reminder},
                    "next_action": "await_remind_time",
                    "confidence": 0.9
                }

        # Todos os lembretes já têm tempo de antecedência
        return self._build_multiple_confirmation_response(reminders)

    async def process(
        self,
        message: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Wrapper async para process_sync."""
        return self.process_sync(message, context)

    def _handle_delete_sync(
        self,
        message: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Processa solicitação de cancelamento de lembrete (versão síncrona)."""
        
        db = context.get("db")
        user_id = context.get("user_id")
        
        if not db or not user_id:
            return {
                "response": "❌ Para cancelar lembretes, acesse a página de Lembretes no menu.",
                "entities": {},
                "next_action": "none",
                "confidence": 0.5
            }
        
        from app.models import Reminder
        reminders = db.query(Reminder).filter(
            Reminder.user_id == user_id,
            Reminder.is_active == True
        ).order_by(Reminder.scheduled_time.asc()).limit(10).all()
        
        if not reminders:
            return {
                "response": "📋 Você não tem lembretes ativos para cancelar.",
                "entities": {},
                "next_action": "none",
                "confidence": 1.0
            }
        
        reminders_text = "\n".join([
            f"ID {r.id}: {r.title} - {r.scheduled_time.strftime('%d/%m/%Y %H:%M')}"
            for r in reminders
        ])
        
        identify_prompt = ReminderPrompts.get_delete_identification_prompt(
            message=message,
            reminders_text=reminders_text
        )
        
        response = self.invoke_llm_sync(identify_prompt)
        
        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            identified = json.loads(response[json_start:json_end])
        except:
            identified = {"reminder_id": None}
        
        reminder_id = identified.get("reminder_id")
        
        if reminder_id:
            reminder = db.query(Reminder).filter(
                Reminder.id == reminder_id,
                Reminder.user_id == user_id
            ).first()
            
            if reminder:
                title = reminder.title
                scheduled = reminder.scheduled_time.strftime('%d/%m/%Y %H:%M')
                
                # Deletar diretamente
                db.delete(reminder)
                db.commit()
                
                return {
                    "response": f"✅ Lembrete cancelado: **{title}** (agendado para {scheduled})",
                    "entities": {"delete_reminder": {"id": reminder_id, "title": title}},
                    "next_action": "none",
                    "confidence": 0.95
                }
        
        options = "\n".join([
            f"• **{r.title}** - {r.scheduled_time.strftime('%d/%m %H:%M')}"
            for r in reminders[:5]
        ])
        
        return {
            "response": f"🔍 Qual lembrete você quer cancelar?\n\n{options}\n\nDiga qual você quer remover.",
            "entities": {"active_reminders": [{"id": r.id, "title": r.title} for r in reminders[:5]]},
            "next_action": "await_delete_selection",
            "confidence": 0.7
        }

    def _parse_remind_time(self, message: str) -> int:
        """Extrai minutos de antecedência da mensagem usando ReminderConstants."""
        return ReminderConstants.parse_remind_time(message)
    
    def _format_datetime(self, dt_str: str) -> str:
        """Formata datetime para exibição amigável."""
        try:
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            return dt.strftime("%d/%m/%Y às %H:%M")
        except:
            return dt_str
    
    def _complete_reminder_with_time_sync(
        self,
        message: str,
        pending_reminder: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Completa o lembrete com o tempo de antecedência especificado (versão síncrona)."""
        remind_before = self._parse_remind_time(message)
        
        # Suporte a múltiplos lembretes pendentes
        pending_reminders = context.get("pending_reminders") or context.get("memory", {}).get("pending_reminders")
        
        if pending_reminders:
            for reminder in pending_reminders:
                reminder["remind_before_minutes"] = remind_before
            return self._build_multiple_confirmation_response(pending_reminders)
        
        pending_reminder["remind_before_minutes"] = remind_before
        return self._build_confirmation_response(pending_reminder)

    async def _complete_reminder_with_time(
        self,
        message: str,
        pending_reminder: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Wrapper async."""
        return self._complete_reminder_with_time_sync(message, pending_reminder, context)
    
    def _build_confirmation_response(self, extracted: Dict[str, Any]) -> Dict[str, Any]:
        """Constrói resposta de confirmação do lembrete."""
        remind_before = extracted.get("remind_before_minutes", 0)
        time_text = ReminderConstants.format_remind_time(remind_before)
        
        title = extracted.get("title", "Lembrete")
        scheduled = self._format_datetime(extracted.get("scheduled_time", ""))
        
        confirmation = ReminderPrompts.TEMPLATES["single_confirmation"].format(
            title=title,
            scheduled_time=scheduled,
            remind_time=f"{time_text} antes" if remind_before > 0 else time_text
        )
        
        return {
            "response": confirmation,
            "entities": {"reminder": extracted},
            "next_action": "create_reminder",
            "confidence": 0.95
        }

    def _build_multiple_confirmation_response(self, reminders: list) -> Dict[str, Any]:
        """Constrói resposta de confirmação para múltiplos lembretes."""
        if len(reminders) == 1:
            return self._build_confirmation_response(reminders[0])
        
        remind_before = reminders[0].get("remind_before_minutes", 0)
        time_text = ReminderConstants.format_remind_time(remind_before)
        
        items = "\n".join([
            f"📌 *{r.get('title')}* - {self._format_datetime(r.get('scheduled_time', ''))}"
            for r in reminders
        ])
        
        confirmation = ReminderPrompts.TEMPLATES["multiple_confirmation"].format(
            count=len(reminders),
            items=items,
            remind_time=f"{time_text} antes" if remind_before > 0 else time_text
        )
        
        return {
            "response": confirmation,
            "entities": {"reminders": reminders},
            "next_action": "create_multiple_reminders",
            "confidence": 0.95
        }

    def extract_entities(
        self,
        message: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extrai entidades de lembrete de forma síncrona."""
        return {}
