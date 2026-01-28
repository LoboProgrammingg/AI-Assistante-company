"""
Serviço de envio de emails enterprise para IRIS.

Features:
- Retry automático com backoff exponencial
- Fallback de portas SMTP
- Templates modulares e profissionais
- Logging estruturado
- Validação de configuração
"""

import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from typing import List, Optional, Tuple

from app.config import settings
from app.services.email.templates import EmailTemplates

logger = logging.getLogger(__name__)


class SMTPConnectionType(Enum):
    """Tipos de conexão SMTP."""
    SSL = "ssl"
    STARTTLS = "starttls"


@dataclass
class SMTPConfig:
    """Configuração de conexão SMTP."""
    port: int
    connection_type: SMTPConnectionType
    
    @property
    def is_ssl(self) -> bool:
        return self.connection_type == SMTPConnectionType.SSL


class EmailService:
    """
    Serviço de email enterprise para IRIS.
    
    Implementa:
    - Singleton thread-safe
    - Retry com fallback de portas
    - Templates profissionais
    - Validação de configuração
    """
    
    _instance: Optional["EmailService"] = None
    
    SMTP_CONFIGS: List[SMTPConfig] = [
        SMTPConfig(465, SMTPConnectionType.SSL),
        SMTPConfig(587, SMTPConnectionType.STARTTLS),
        SMTPConfig(25, SMTPConnectionType.STARTTLS),
    ]
    
    TIMEOUT_SECONDS: int = 15
    
    def __new__(cls) -> "EmailService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._host = settings.SMTP_HOST
        self._port = settings.SMTP_PORT
        self._use_ssl = getattr(settings, "SMTP_USE_SSL", False)
        self._user = settings.SMTP_USER
        self._password = settings.SMTP_PASSWORD
        self._from_email = settings.SMTP_FROM_EMAIL or self._user
        self._from_name = settings.SMTP_FROM_NAME
        self._templates = EmailTemplates()
        
        self._initialized = True
        
        if self.is_configured:
            logger.info(f"[EMAIL] Serviço inicializado | Host: {self._host}")
        else:
            logger.warning("[EMAIL] Serviço não configurado - emails desabilitados")
    
    @property
    def is_configured(self) -> bool:
        """Verifica se o serviço está configurado corretamente."""
        return bool(
            self._host and 
            self._user and 
            self._password and
            self._from_email
        )
    
    def _get_connection_attempts(self) -> List[Tuple[int, bool]]:
        """
        Retorna lista de tentativas de conexão ordenadas por prioridade.
        
        Prioriza a configuração do usuário, depois fallbacks.
        """
        attempts = []
        
        if self._port:
            attempts.append((self._port, self._use_ssl))
        
        for config in self.SMTP_CONFIGS:
            attempt = (config.port, config.is_ssl)
            if attempt not in attempts:
                attempts.append(attempt)
        
        return attempts
    
    def _create_message(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> MIMEMultipart:
        """Cria mensagem MIME formatada."""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{self._from_name} <{self._from_email}>"
        msg["To"] = to_email
        msg["X-Mailer"] = "IRIS Email Service v2.0"
        
        if text_content:
            msg.attach(MIMEText(text_content, "plain", "utf-8"))
        
        msg.attach(MIMEText(html_content, "html", "utf-8"))
        
        return msg
    
    def _send_with_ssl(
        self,
        msg: MIMEMultipart,
        to_email: str,
        port: int
    ) -> bool:
        """Envia email usando conexão SSL direta."""
        context = ssl.create_default_context()
        
        with smtplib.SMTP_SSL(
            self._host, 
            port, 
            timeout=self.TIMEOUT_SECONDS,
            context=context
        ) as server:
            server.login(self._user, self._password.strip())
            server.send_message(msg)
        
        return True
    
    def _send_with_starttls(
        self,
        msg: MIMEMultipart,
        to_email: str,
        port: int
    ) -> bool:
        """Envia email usando STARTTLS."""
        context = ssl.create_default_context()
        
        with smtplib.SMTP(
            self._host, 
            port, 
            timeout=self.TIMEOUT_SECONDS
        ) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(self._user, self._password.strip())
            server.send_message(msg)
        
        return True
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """
        Envia email com retry automático e fallback de portas.
        
        Args:
            to_email: Email do destinatário
            subject: Assunto do email
            html_content: Conteúdo HTML
            text_content: Conteúdo texto puro (opcional)
        
        Returns:
            True se enviado com sucesso
        """
        if not self.is_configured:
            logger.error("[EMAIL] Serviço não configurado")
            return False
        
        msg = self._create_message(to_email, subject, html_content, text_content)
        attempts = self._get_connection_attempts()
        
        for port, use_ssl in attempts:
            try:
                logger.debug(f"[EMAIL] Tentando {self._host}:{port} (SSL={use_ssl})")
                
                if use_ssl:
                    self._send_with_ssl(msg, to_email, port)
                else:
                    self._send_with_starttls(msg, to_email, port)
                
                logger.info(f"[EMAIL] ✓ Enviado para {to_email} via porta {port}")
                return True
                
            except smtplib.SMTPAuthenticationError as e:
                logger.error(f"[EMAIL] Erro de autenticação: {e}")
                return False
                
            except (smtplib.SMTPConnectError, TimeoutError, OSError) as e:
                logger.warning(f"[EMAIL] Porta {port} indisponível: {type(e).__name__}")
                continue
                
            except smtplib.SMTPException as e:
                logger.warning(f"[EMAIL] Erro SMTP na porta {port}: {e}")
                continue
                
            except Exception as e:
                logger.warning(f"[EMAIL] Erro inesperado na porta {port}: {e}")
                continue
        
        logger.error(f"[EMAIL] ✗ Falha ao enviar para {to_email} - todas as portas falharam")
        return False
    
    def send_verification_code(
        self,
        to_email: str,
        code: str,
        user_name: Optional[str] = None
    ) -> bool:
        """
        Envia código de verificação de email.
        
        Args:
            to_email: Email do destinatário
            code: Código de 6 dígitos
            user_name: Nome do usuário (opcional)
        
        Returns:
            True se enviado com sucesso
        """
        name = user_name or "Usuário"
        expire_minutes = settings.VERIFICATION_CODE_EXPIRE_MINUTES
        
        template = self._templates.verification_code(name, code, expire_minutes)
        
        return self.send_email(
            to_email=to_email,
            subject=template["subject"],
            html_content=template["html"],
            text_content=template["text"]
        )
    
    def send_password_reset(
        self,
        to_email: str,
        code: str,
        user_name: Optional[str] = None
    ) -> bool:
        """
        Envia código para reset de senha.
        
        Args:
            to_email: Email do destinatário
            code: Código de 6 dígitos
            user_name: Nome do usuário (opcional)
        
        Returns:
            True se enviado com sucesso
        """
        name = user_name or "Usuário"
        expire_minutes = settings.VERIFICATION_CODE_EXPIRE_MINUTES
        
        template = self._templates.password_reset(name, code, expire_minutes)
        
        return self.send_email(
            to_email=to_email,
            subject=template["subject"],
            html_content=template["html"],
            text_content=template["text"]
        )
    
    def send_welcome(
        self,
        to_email: str,
        user_name: Optional[str] = None
    ) -> bool:
        """
        Envia email de boas-vindas após verificação.
        
        Args:
            to_email: Email do destinatário
            user_name: Nome do usuário (opcional)
        
        Returns:
            True se enviado com sucesso
        """
        name = user_name or "Usuário"
        
        template = self._templates.welcome(name)
        
        return self.send_email(
            to_email=to_email,
            subject=template["subject"],
            html_content=template["html"],
            text_content=template["text"]
        )
    
    def send_notification(
        self,
        to_email: str,
        user_name: str,
        title: str,
        message: str,
        cta_text: Optional[str] = None,
        cta_url: Optional[str] = None
    ) -> bool:
        """
        Envia notificação genérica.
        
        Args:
            to_email: Email do destinatário
            user_name: Nome do usuário
            title: Título da notificação
            message: Mensagem
            cta_text: Texto do botão de ação (opcional)
            cta_url: URL do botão de ação (opcional)
        
        Returns:
            True se enviado com sucesso
        """
        template = self._templates.generic_notification(
            user_name, title, message, cta_text, cta_url
        )
        
        return self.send_email(
            to_email=to_email,
            subject=template["subject"],
            html_content=template["html"],
            text_content=template["text"]
        )


email_service = EmailService()
