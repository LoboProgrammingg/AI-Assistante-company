"""
Serviço de envio de emails.
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Serviço para envio de emails via SMTP."""

    def __init__(self):
        self.host = settings.SMTP_HOST
        self.port = settings.SMTP_PORT
        self.use_ssl = getattr(settings, "SMTP_USE_SSL", False)
        self.user = settings.SMTP_USER
        self.password = settings.SMTP_PASSWORD
        self.from_email = settings.SMTP_FROM_EMAIL or self.user
        self.from_name = settings.SMTP_FROM_NAME

    @property
    def is_configured(self) -> bool:
        """Verifica se o serviço está configurado."""
        return bool(self.user and self.password)

    def _create_message(
        self, to_email: str, subject: str, html_content: str, text_content: Optional[str] = None
    ) -> MIMEMultipart:
        """Cria mensagem de email."""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{self.from_name} <{self.from_email}>"
        msg["To"] = to_email

        if text_content:
            msg.attach(MIMEText(text_content, "plain", "utf-8"))

        msg.attach(MIMEText(html_content, "html", "utf-8"))

        return msg

    def send_email(self, to_email: str, subject: str, html_content: str, text_content: Optional[str] = None) -> bool:
        """
        Envia email.

        Args:
            to_email: Email do destinatário
            subject: Assunto do email
            html_content: Conteúdo HTML
            text_content: Conteúdo em texto puro (opcional)

        Returns:
            True se enviado com sucesso
        """
        if not self.is_configured:
            logger.error("EmailService não configurado. Defina SMTP_USER e SMTP_PASSWORD.")
            return False

        try:
            msg = self._create_message(to_email, subject, html_content, text_content)

            logger.info(f"Conectando ao SMTP: {self.host}:{self.port} (SSL={self.use_ssl})")

            # Login com senha (remover espaços extras se houver)
            password = self.password.strip() if self.password else ""

            # Usar timeout de 30 segundos para evitar travamento
            if self.use_ssl:
                # SSL direto (porta 465)
                with smtplib.SMTP_SSL(self.host, self.port, timeout=30) as server:
                    server.login(self.user, password)
                    server.send_message(msg)
            else:
                # STARTTLS (porta 587)
                with smtplib.SMTP(self.host, self.port, timeout=30) as server:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    server.login(self.user, password)
                    server.send_message(msg)

            logger.info(f"Email enviado com sucesso para {to_email}: {subject}")
            return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"Erro de autenticação SMTP (verifique App Password): {e}")
            return False
        except smtplib.SMTPConnectError as e:
            logger.error(f"Erro de conexão SMTP (porta bloqueada?): {e}")
            return False
        except smtplib.SMTPServerDisconnected as e:
            logger.error(f"Servidor SMTP desconectou: {e}")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"Erro SMTP ao enviar email: {e}")
            return False
        except TimeoutError as e:
            logger.error(f"Timeout ao conectar ao SMTP (Railway pode bloquear porta 587): {e}")
            return False
        except Exception as e:
            logger.error(f"Erro inesperado ao enviar email: {type(e).__name__}: {e}")
            return False

    def send_verification_code(self, to_email: str, code: str, user_name: Optional[str] = None) -> bool:
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

        subject = f"Seu código de verificação: {code}"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .code {{ font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #667eea; text-align: center; padding: 20px; background: white; border-radius: 8px; margin: 20px 0; }}
                .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🤖 WhatsApp AI Assistant</h1>
                </div>
                <div class="content">
                    <h2>Olá, {name}!</h2>
                    <p>Você solicitou a verificação do seu email. Use o código abaixo para confirmar sua conta:</p>
                    <div class="code">{code}</div>
                    <p>Este código expira em <strong>{settings.VERIFICATION_CODE_EXPIRE_MINUTES} minutos</strong>.</p>
                    <p>Se você não solicitou esta verificação, ignore este email.</p>
                </div>
                <div class="footer">
                    <p>© 2026 WhatsApp AI Assistant. Todos os direitos reservados.</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = f"""
        Olá, {name}!
        
        Seu código de verificação é: {code}
        
        Este código expira em {settings.VERIFICATION_CODE_EXPIRE_MINUTES} minutos.
        
        Se você não solicitou esta verificação, ignore este email.
        """

        return self.send_email(to_email, subject, html_content, text_content)

    def send_password_reset(self, to_email: str, code: str, user_name: Optional[str] = None) -> bool:
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

        subject = "Redefinição de Senha - WhatsApp AI Assistant"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .code {{ font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #f5576c; text-align: center; padding: 20px; background: white; border-radius: 8px; margin: 20px 0; }}
                .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔐 Redefinição de Senha</h1>
                </div>
                <div class="content">
                    <h2>Olá, {name}!</h2>
                    <p>Recebemos uma solicitação para redefinir sua senha. Use o código abaixo:</p>
                    <div class="code">{code}</div>
                    <p>Este código expira em <strong>{settings.VERIFICATION_CODE_EXPIRE_MINUTES} minutos</strong>.</p>
                    <p><strong>Se você não solicitou esta redefinição, ignore este email e sua senha permanecerá a mesma.</strong></p>
                </div>
                <div class="footer">
                    <p>© 2026 WhatsApp AI Assistant. Todos os direitos reservados.</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = f"""
        Olá, {name}!
        
        Recebemos uma solicitação para redefinir sua senha.
        
        Seu código de redefinição é: {code}
        
        Este código expira em {settings.VERIFICATION_CODE_EXPIRE_MINUTES} minutos.
        
        Se você não solicitou esta redefinição, ignore este email.
        """

        return self.send_email(to_email, subject, html_content, text_content)

    def send_welcome(self, to_email: str, user_name: Optional[str] = None) -> bool:
        """
        Envia email de boas-vindas após verificação.

        Args:
            to_email: Email do destinatário
            user_name: Nome do usuário (opcional)

        Returns:
            True se enviado com sucesso
        """
        name = user_name or "Usuário"

        subject = "Bem-vindo ao WhatsApp AI Assistant! 🎉"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .feature {{ background: white; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 4px solid #38ef7d; }}
                .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎉 Bem-vindo!</h1>
                </div>
                <div class="content">
                    <h2>Olá, {name}!</h2>
                    <p>Sua conta foi verificada com sucesso! Agora você pode aproveitar todos os recursos do WhatsApp AI Assistant:</p>
                    
                    <div class="feature">
                        <strong>📝 Lembretes Inteligentes</strong>
                        <p>Crie e gerencie lembretes via WhatsApp</p>
                    </div>
                    
                    <div class="feature">
                        <strong>💰 Controle Financeiro</strong>
                        <p>Acompanhe suas receitas e despesas</p>
                    </div>
                    
                    <div class="feature">
                        <strong>📅 Reuniões</strong>
                        <p>Organize suas reuniões e transcreva áudios</p>
                    </div>
                    
                    <div class="feature">
                        <strong>👥 Contatos</strong>
                        <p>Gerencie seus contatos e envie mensagens em grupo</p>
                    </div>
                    
                    <p>Comece agora mesmo acessando o dashboard!</p>
                </div>
                <div class="footer">
                    <p>© 2026 WhatsApp AI Assistant. Todos os direitos reservados.</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = f"""
        Olá, {name}!
        
        Sua conta foi verificada com sucesso!
        
        Agora você pode aproveitar todos os recursos do WhatsApp AI Assistant:
        - Lembretes Inteligentes
        - Controle Financeiro
        - Reuniões
        - Contatos
        
        Comece agora mesmo acessando o dashboard!
        """

        return self.send_email(to_email, subject, html_content, text_content)


# Singleton instance
email_service = EmailService()
