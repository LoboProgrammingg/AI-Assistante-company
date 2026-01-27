"""
Health Agent - Organização de saúde (apenas organizacional).

IMPORTANTE: Este agente NÃO fornece:
- Diagnósticos
- Sugestões de tratamento
- Interpretação de exames
- Aconselhamento médico

Apenas organiza:
- Lembretes de remédios
- Agendamentos de consultas
- Notas organizacionais
"""

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Dict, List

from app.ai.agents.base import AgentResult, SpecializedAgent
from app.ai.agents.registry import AgentRegistry

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# Termos que indicam pedido de diagnóstico/tratamento (bloqueados)
MEDICAL_BLOCKED_TERMS = [
    "diagnóstico",
    "diagnostico",
    "diagnosticar",
    "tratamento",
    "tratar",
    "curar",
    "remédio para",
    "medicamento para",
    "sintoma",
    "doença",
    "doente",
    "exame",
    "resultado do exame",
    "prescrição",
    "prescrever",
    "o que eu tenho",
    "estou com",
]


@AgentRegistry.register
class HealthAgent(SpecializedAgent):
    """Agente de organização de saúde."""

    name = "health"
    description = "Organiza lembretes de saúde (não fornece diagnósticos)"
    supported_intents = ["health", "saúde", "remédio", "consulta", "médico"]

    def _register_tools(self) -> Dict[str, callable]:
        """Registra tools do agente."""
        return {
            "create_health_reminder": self._create_health_reminder,
            "read_health_schedule": self._read_health_schedule,
            "store_health_note": self._store_health_note,
        }

    async def process(self, message: str, entities: Dict[str, Any] = None) -> AgentResult:
        """Processa solicitação de saúde."""
        entities = entities or {}
        message_lower = message.lower()

        # BLOQUEIO: Verificar se é pedido médico
        if self._is_medical_request(message_lower):
            return self._blocked_response()

        # Lembrete de remédio
        if any(k in message_lower for k in ["lembrete", "lembra", "avisar", "tomar"]):
            return await self._handle_medication_reminder(message, entities)

        # Agendar consulta
        if any(k in message_lower for k in ["consulta", "médico", "dentista", "exame"]):
            return await self._handle_appointment(message, entities)

        # Ver agenda de saúde
        if any(k in message_lower for k in ["agenda", "próximos", "pendente"]):
            return await self._handle_schedule()

        # Nota de saúde
        if any(k in message_lower for k in ["anotar", "registrar", "salvar"]):
            return await self._handle_note(message, entities)

        # Ajuda geral
        return self._help_response()

    def _is_medical_request(self, message: str) -> bool:
        """Verifica se é pedido de diagnóstico/tratamento."""
        return any(term in message for term in MEDICAL_BLOCKED_TERMS)

    def _blocked_response(self) -> AgentResult:
        """Resposta para pedidos médicos bloqueados."""
        return AgentResult(
            success=True,
            action="blocked",
            data={},
            message=(
                "⚠️ *Não posso ajudar com diagnósticos ou tratamentos.*\n\n"
                "Sou apenas um organizador. Para questões de saúde, "
                "consulte um profissional médico.\n\n"
                "Posso ajudar com:\n"
                "• Lembretes de remédios\n"
                "• Agendar consultas\n"
                "• Organizar sua agenda de saúde"
            ),
        )

    def _help_response(self) -> AgentResult:
        """Resposta de ajuda."""
        lines = [
            "🏥 *Organização de Saúde*\n",
            "Posso ajudar você a:",
            "• Criar lembretes de remédios",
            "• Lembrar de consultas",
            "• Organizar sua agenda de saúde\n",
            "⚠️ _Não forneço diagnósticos ou tratamentos._\n",
            '_Diga: "me lembra de tomar remédio às 8h"_',
        ]

        return AgentResult(
            success=True,
            action="help",
            data={},
            message="\n".join(lines),
        )

    async def _handle_medication_reminder(self, message: str, entities: Dict[str, Any]) -> AgentResult:
        """Cria lembrete de medicação."""
        import re

        # Extrair horário
        time_match = re.search(r"(\d{1,2})[h:](\d{0,2})", message.lower())
        time_str = ""
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2)) if time_match.group(2) else 0
            time_str = f"{hour:02d}:{minute:02d}"

        # Extrair nome do remédio (simplificado)
        medication = entities.get("medication", "remédio")

        if not time_str:
            return AgentResult(
                success=True,
                action="create_health_reminder",
                data={},
                message='💊 A que horas devo te lembrar?\n\n_Ex: "às 8h" ou "às 20:30"_',
                requires_confirmation=True,
            )

        reminder_data = {
            "title": f"💊 Tomar {medication}",
            "scheduled_time": time_str,
            "category": "health",
            "recurrence": "daily",
        }

        return AgentResult(
            success=True,
            action="create_health_reminder",
            data=reminder_data,
            message=f"💊 *Lembrete de medicação:*\n\n⏰ Horário: {time_str}\n\n*Confirma a criação?*",
            requires_confirmation=True,
            confidence=0.8,
        )

    async def _handle_appointment(self, message: str, entities: Dict[str, Any]) -> AgentResult:
        """Registra consulta/exame."""
        import re

        # Detectar tipo
        appointment_type = "Consulta"
        if "dentista" in message.lower():
            appointment_type = "Dentista"
        elif "exame" in message.lower():
            appointment_type = "Exame"
        elif "psicólogo" in message.lower() or "psicologo" in message.lower():
            appointment_type = "Psicólogo"

        # Extrair data
        date_match = re.search(r"(\d{1,2})/(\d{1,2})", message)
        date_str = ""
        if date_match:
            day = int(date_match.group(1))
            month = int(date_match.group(2))
            year = datetime.now().year
            date_str = f"{year}-{month:02d}-{day:02d}"

        reminder_data = {
            "title": f"🏥 {appointment_type}",
            "scheduled_time": date_str,
            "category": "health",
        }

        if not date_str:
            return AgentResult(
                success=True,
                action="create_health_reminder",
                data={"type": appointment_type},
                message=f'🏥 Quando é a consulta/exame?\n\n_Ex: "dia 15/02 às 14h"_',
                requires_confirmation=True,
            )

        return AgentResult(
            success=True,
            action="create_health_reminder",
            data=reminder_data,
            message=f"🏥 *{appointment_type}*\n\n📅 Data: {date_str}\n\n*Confirma?*",
            requires_confirmation=True,
            confidence=0.8,
        )

    async def _handle_schedule(self) -> AgentResult:
        """Mostra agenda de saúde."""
        if not self.db or not self.user_id:
            return AgentResult(success=False, action="error", error="Sem acesso")

        try:
            from app.services.reminder_service import ReminderService

            service = ReminderService(self.db)

            reminders, total = service.list_by_user(self.user_id, status="active", limit=20)

            # Filtrar lembretes de saúde
            health_reminders = [
                r
                for r in reminders
                if any(k in r.title.lower() for k in ["remédio", "💊", "consulta", "🏥", "médico", "dentista"])
            ]

            if not health_reminders:
                return AgentResult(
                    success=True,
                    action="read_health_schedule",
                    data={"reminders": []},
                    message="📅 Nenhum compromisso de saúde agendado.",
                )

            lines = ["🏥 *Agenda de Saúde*\n"]
            for r in health_reminders[:10]:
                time_str = r.scheduled_time.strftime("%d/%m %H:%M") if r.scheduled_time else ""
                lines.append(f"• {r.title} - {time_str}")

            return AgentResult(
                success=True,
                action="read_health_schedule",
                data={"count": len(health_reminders)},
                message="\n".join(lines),
            )

        except Exception as e:
            return AgentResult(success=False, action="error", error=str(e))

    async def _handle_note(self, message: str, entities: Dict[str, Any]) -> AgentResult:
        """Salva nota de saúde."""
        return AgentResult(
            success=True,
            action="store_health_note",
            data={},
            message="📝 O que você gostaria de anotar?\n\n_Nota: Não armazeno resultados de exames ou dados clínicos._",
            requires_confirmation=True,
        )

    # === Tool implementations ===

    def _create_health_reminder(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Cria lembrete de saúde."""
        if not self.db or not self.user_id:
            return {"success": False, "error": "Sem acesso"}

        try:
            from app.services.reminder_service import ReminderService

            service = ReminderService(self.db)
            service.create_from_entities(self.user_id, data)
            return {"success": True, "message": "✅ Lembrete criado!"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _read_health_schedule(self) -> Dict[str, Any]:
        """Lê agenda de saúde."""
        return {"success": False, "error": "Use process()"}

    def _store_health_note(self, note: str) -> Dict[str, Any]:
        """Armazena nota de saúde."""
        return {"success": True, "message": "Nota salva"}
