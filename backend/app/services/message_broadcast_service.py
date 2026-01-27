"""Serviço de broadcast de mensagens (deprecated - funcionalidade de contatos removida)."""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class MessageBroadcastService:
    """Serviço de broadcast - mantido para compatibilidade mas sem funcionalidade de grupos."""

    def __init__(self, db=None, whatsapp_service=None):
        self.db = db
        self.whatsapp_service = whatsapp_service

    def send_to_phone(self, phone: str, message: str, name: str = "Contato") -> Dict[str, Any]:
        """Envia mensagem para um número específico."""
        if not self.whatsapp_service:
            return {"sent": 0, "failed": 1, "error": "WhatsApp service não configurado"}

        try:
            self.whatsapp_service.send_message(to_number=phone, message=message)
            logger.info(f"Mensagem enviada para {name}")
            return {
                "sent": 1,
                "failed": 0,
                "recipients": [{"name": name, "phone": phone, "status": "sent"}],
            }
        except Exception as e:
            logger.error(f"Erro ao enviar para {name}: {e}")
            return {
                "sent": 0,
                "failed": 1,
                "recipients": [{"name": name, "phone": phone, "status": "failed", "error": str(e)}],
            }

    def format_broadcast_summary(self, result: Dict[str, Any], recipients: List[str] = None) -> str:
        """Formata resumo do envio para resposta ao usuário."""
        if result.get("error"):
            return f"❌ {result['error']}"

        if result["sent"] == 0 and result.get("failed", 0) == 0:
            return "⚠️ Nenhum destinatário encontrado"

        msg = f"📤 *Mensagem enviada!*\n\n"
        msg += f"✅ Enviadas: {result['sent']}\n"

        if result.get("failed", 0) > 0:
            msg += f"❌ Falhas: {result['failed']}\n"

        return msg
