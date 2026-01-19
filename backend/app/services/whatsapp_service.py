from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from typing import Optional, Dict
import logging
import httpx
from pathlib import Path
import base64

logger = logging.getLogger(__name__)


class WhatsAppService:
    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        whatsapp_number: str
    ):
        self.client = Client(account_sid, auth_token)
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.whatsapp_number = whatsapp_number
        self.from_number = f"whatsapp:{whatsapp_number}"
    
    def send_typing_indicator(self, message_sid: str) -> bool:
        """
        Envia indicador de 'digitando...' para o WhatsApp.
        
        Args:
            message_sid: ID da mensagem que está sendo respondida (SM... ou MM...)
        
        Returns:
            bool: True se enviado com sucesso
        """
        try:
            url = "https://messaging.twilio.com/v2/Indicators/Typing.json"
            
            auth = base64.b64encode(
                f"{self.account_sid}:{self.auth_token}".encode()
            ).decode()
            
            with httpx.Client() as client:
                response = client.post(
                    url,
                    headers={"Authorization": f"Basic {auth}"},
                    data={
                        "messageId": message_sid,
                        "channel": "whatsapp"
                    }
                )
                
                if response.status_code == 200:
                    logger.info(f"Typing indicator enviado para mensagem {message_sid}")
                    return True
                else:
                    logger.warning(f"Typing indicator falhou: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Erro ao enviar typing indicator: {e}")
            return False
    
    def send_message(
        self,
        to_number: str,
        message: str,
        media_url: Optional[str] = None
    ) -> Dict:
        """Envia uma mensagem de texto via WhatsApp"""
        try:
            to_whatsapp = f"whatsapp:{to_number}"
            
            message_params = {
                "from_": self.from_number,
                "to": to_whatsapp,
                "body": message
            }
            
            if media_url:
                message_params["media_url"] = [media_url]
            
            message_obj = self.client.messages.create(**message_params)
            
            logger.info(f"Mensagem enviada com sucesso: {message_obj.sid}")
            
            return {
                "success": True,
                "message_sid": message_obj.sid,
                "status": message_obj.status
            }
            
        except TwilioRestException as e:
            logger.error(f"Erro ao enviar mensagem: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def download_audio(
        self,
        media_url: str,
        save_path: Path
    ) -> Optional[Path]:
        """Baixa o áudio do WhatsApp"""
        try:
            async with httpx.AsyncClient() as client:
                # Twilio requer autenticação para baixar mídia
                response = await client.get(
                    media_url,
                    auth=(self.client.username, self.client.password)
                )
                response.raise_for_status()
                
                save_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(save_path, "wb") as f:
                    f.write(response.content)
                
                logger.info(f"Áudio baixado com sucesso: {save_path}")
                return save_path
                
        except Exception as e:
            logger.error(f"Erro ao baixar áudio: {e}")
            return None
    
    def get_message_status(self, message_sid: str) -> Optional[str]:
        """Verifica o status de uma mensagem"""
        try:
            message = self.client.messages(message_sid).fetch()
            return message.status
        except TwilioRestException as e:
            logger.error(f"Erro ao buscar status: {e}")
            return None
    
    def send_template_message(
        self,
        to_number: str,
        template_name: str,
        variables: list
    ) -> Dict:
        """Envia uma mensagem template (para mensagens proativas)"""
        # Templates precisam ser aprovados pelo WhatsApp Business
        try:
            to_whatsapp = f"whatsapp:{to_number}"
            
            # Exemplo de formato de template
            content_sid = f"HX{template_name}"
            
            message = self.client.messages.create(
                from_=self.from_number,
                to=to_whatsapp,
                content_sid=content_sid,
                content_variables=variables
            )
            
            return {
                "success": True,
                "message_sid": message.sid
            }
            
        except TwilioRestException as e:
            logger.error(f"Erro ao enviar template: {e}")
            return {
                "success": False,
                "error": str(e)
            }


class WhatsAppWebhookHandler:
    """Processa webhooks do WhatsApp"""
    
    @staticmethod
    def parse_incoming_message(form_data: dict) -> Dict:
        """Parse dos dados do webhook"""
        return {
            "message_sid": form_data.get("MessageSid"),
            "from_number": form_data.get("From", "").replace("whatsapp:", ""),
            "to_number": form_data.get("To", "").replace("whatsapp:", ""),
            "body": form_data.get("Body", ""),
            "num_media": int(form_data.get("NumMedia", 0)),
            "media_content_type": form_data.get("MediaContentType0"),
            "media_url": form_data.get("MediaUrl0"),
            "profile_name": form_data.get("ProfileName", ""),
            "timestamp": form_data.get("Timestamp")
        }
    
    @staticmethod
    def parse_status_callback(form_data: dict) -> Dict:
        """Parse dos callbacks de status"""
        return {
            "message_sid": form_data.get("MessageSid"),
            "message_status": form_data.get("MessageStatus"),
            "error_code": form_data.get("ErrorCode"),
            "error_message": form_data.get("ErrorMessage"),
            "timestamp": form_data.get("Timestamp")
        }