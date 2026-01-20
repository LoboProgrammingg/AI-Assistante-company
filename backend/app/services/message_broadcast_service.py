import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.services.contact_service import ContactService, normalize_group_name

logger = logging.getLogger(__name__)


class MessageBroadcastService:
    """Serviço para envio de mensagens em massa para grupos de contatos."""

    def __init__(self, db: Session, whatsapp_service=None):
        self.db = db
        self.contact_service = ContactService(db)
        self.whatsapp_service = whatsapp_service

    def get_recipients_by_group(self, user_id: int, group_name: str) -> List[Dict[str, str]]:
        """Retorna lista de destinatários de um grupo."""
        normalized = normalize_group_name(group_name)
        contacts = self.contact_service.get_by_group(user_id, normalized)
        return [{"name": c.name, "phone_number": c.phone_number} for c in contacts]

    def get_recipients_by_groups(self, user_id: int, group_names: List[str]) -> List[Dict[str, str]]:
        """Retorna lista de destinatários de múltiplos grupos."""
        recipients = []
        seen_phones = set()

        for group_name in group_names:
            contacts = self.contact_service.get_by_group(user_id, group_name)
            for c in contacts:
                if c.phone_number not in seen_phones:
                    recipients.append({"name": c.name, "phone_number": c.phone_number})
                    seen_phones.add(c.phone_number)

        return recipients

    def prepare_broadcast(
        self,
        user_id: int,
        group_name: Optional[str] = None,
        group_names: Optional[List[str]] = None,
        contact_ids: Optional[List[int]] = None,
    ) -> List[Dict[str, str]]:
        """Prepara lista de destinatários para broadcast."""
        recipients = []
        seen_phones = set()

        if group_name:
            for r in self.get_recipients_by_group(user_id, group_name):
                if r["phone_number"] not in seen_phones:
                    recipients.append(r)
                    seen_phones.add(r["phone_number"])

        if group_names:
            for r in self.get_recipients_by_groups(user_id, group_names):
                if r["phone_number"] not in seen_phones:
                    recipients.append(r)
                    seen_phones.add(r["phone_number"])

        if contact_ids:
            for contact_id in contact_ids:
                contact = self.contact_service.get_by_id(user_id, contact_id)
                if contact and contact.phone_number not in seen_phones:
                    recipients.append({"name": contact.name, "phone_number": contact.phone_number})
                    seen_phones.add(contact.phone_number)

        return recipients

    def get_group_preview(self, user_id: int, group_name: str) -> Dict[str, Any]:
        """Retorna preview de um grupo antes do envio."""
        recipients = self.get_recipients_by_group(user_id, group_name)
        return {
            "group_name": group_name,
            "total": len(recipients),
            "recipients": recipients[:10],  # Primeiros 10 para preview
            "has_more": len(recipients) > 10,
        }

    def send_broadcast(
        self,
        user_id: int,
        message: str,
        group_name: Optional[str] = None,
        group_names: Optional[List[str]] = None,
        contact_ids: Optional[List[int]] = None,
        whatsapp_service=None,
    ) -> Dict[str, Any]:
        """
        Envia mensagem para grupo(s) de contatos.

        Returns:
            Dict com estatísticas do envio (sent, failed, recipients)
        """
        ws = whatsapp_service or self.whatsapp_service
        recipients = self.prepare_broadcast(
            user_id, group_name=group_name, group_names=group_names, contact_ids=contact_ids
        )

        if not recipients:
            return {
                "sent": 0,
                "failed": 0,
                "total": 0,
                "recipients": [],
                "error": "Nenhum contato encontrado no(s) grupo(s)",
            }

        results = {"sent": 0, "failed": 0, "total": len(recipients), "recipients": []}

        for recipient in recipients:
            try:
                if ws:
                    ws.send_message(to_number=recipient["phone_number"], message=message)
                    results["sent"] += 1
                    results["recipients"].append(
                        {"name": recipient["name"], "phone": recipient["phone_number"], "status": "sent"}
                    )
                    logger.info(f"Mensagem enviada para {recipient['name']}")
                else:
                    # Sem WhatsApp service, simular envio (para testes)
                    results["sent"] += 1
                    results["recipients"].append(
                        {"name": recipient["name"], "phone": recipient["phone_number"], "status": "simulated"}
                    )
            except Exception as e:
                results["failed"] += 1
                results["recipients"].append(
                    {"name": recipient["name"], "phone": recipient["phone_number"], "status": "failed", "error": str(e)}
                )
                logger.error(f"Erro ao enviar para {recipient['name']}: {e}")

        return results

    def format_broadcast_summary(self, result: Dict[str, Any], group_names: List[str]) -> str:
        """Formata resumo do broadcast para resposta ao usuário."""
        groups_str = ", ".join(group_names)

        if result.get("error"):
            return f"❌ {result['error']}"

        if result["sent"] == 0 and result["failed"] == 0:
            return f"⚠️ Nenhum contato encontrado no(s) grupo(s): {groups_str}"

        msg = f"📤 *Mensagem enviada!*\n\n"
        msg += f"👥 Grupo(s): {groups_str}\n"
        msg += f"✅ Enviadas: {result['sent']}\n"

        if result["failed"] > 0:
            msg += f"❌ Falhas: {result['failed']}\n"

        # Listar destinatários (máximo 5)
        if result["recipients"]:
            msg += f"\n📋 Destinatários:\n"
            for r in result["recipients"][:5]:
                status_icon = "✅" if r["status"] in ("sent", "simulated") else "❌"
                msg += f"{status_icon} {r['name']}\n"

            if len(result["recipients"]) > 5:
                msg += f"_...e mais {len(result['recipients']) - 5} contatos_"

        return msg
