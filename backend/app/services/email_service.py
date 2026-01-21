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
        Envia email com fallback automático de porta.

        Args:
            to_email: Email do destinatário
            subject: Assunto do email
            html_content: Conteúdo HTML
            text_content: Conteúdo em texto puro (opcional)

        Returns:
            True se enviado com sucesso
        """
        if not self.is_configured:
            logger.error(f"[EMAIL] Não configurado. SMTP_USER={bool(self.user)}, SMTP_PASSWORD={bool(self.password)}")
            return False

        msg = self._create_message(to_email, subject, html_content, text_content)
        password = self.password.strip() if self.password else ""

        # Tentar primeiro com a configuração atual, depois fallback
        attempts = [
            (self.port, self.use_ssl),
            (465, True),   # Fallback SSL
            (587, False),  # Fallback STARTTLS
        ]

        for port, use_ssl in attempts:
            try:
                logger.info(f"[EMAIL] Tentando {self.host}:{port} (SSL={use_ssl}) para {to_email}")

                if use_ssl:
                    with smtplib.SMTP_SSL(self.host, port, timeout=15) as server:
                        server.login(self.user, password)
                        server.send_message(msg)
                else:
                    with smtplib.SMTP(self.host, port, timeout=15) as server:
                        server.ehlo()
                        server.starttls()
                        server.ehlo()
                        server.login(self.user, password)
                        server.send_message(msg)

                logger.info(f"[EMAIL] ✓ Enviado para {to_email}: {subject}")
                return True

            except smtplib.SMTPAuthenticationError as e:
                logger.error(f"[EMAIL] Erro de autenticação (App Password inválido?): {e}")
                return False  # Não tentar outras portas se auth falhou
            except (smtplib.SMTPConnectError, TimeoutError, OSError) as e:
                logger.warning(f"[EMAIL] Porta {port} falhou: {type(e).__name__}")
                continue  # Tentar próxima porta
            except Exception as e:
                logger.warning(f"[EMAIL] Erro na porta {port}: {type(e).__name__}: {e}")
                continue

        logger.error(f"[EMAIL] ✗ Falha total ao enviar para {to_email} - todas as portas falharam")
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

        subject = f"🔐 Código de Verificação: {code} - IRIS"

        html_content = f"""
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="margin: 0; padding: 0; background-color: #0f0f23; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #0f0f23; padding: 40px 20px;">
                <tr>
                    <td align="center">
                        <table role="presentation" width="600" cellspacing="0" cellpadding="0" style="background: linear-gradient(145deg, #1a1a2e 0%, #16213e 100%); border-radius: 20px; overflow: hidden; box-shadow: 0 20px 60px rgba(0,0,0,0.5);">
                            <!-- Header -->
                            <tr>
                                <td style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px; text-align: center;">
                                    <h1 style="margin: 0; color: #ffffff; font-size: 32px; font-weight: 700; letter-spacing: 2px;">
                                        ✨ IRIS
                                    </h1>
                                    <p style="margin: 10px 0 0; color: rgba(255,255,255,0.9); font-size: 14px;">
                                        Sua Assistente Pessoal Inteligente
                                    </p>
                                </td>
                            </tr>
                            <!-- Content -->
                            <tr>
                                <td style="padding: 40px;">
                                    <h2 style="color: #ffffff; margin: 0 0 20px; font-size: 24px;">
                                        Olá, {name}! 👋
                                    </h2>
                                    <p style="color: #a0a0b0; font-size: 16px; line-height: 1.6; margin: 0 0 30px;">
                                        Você está a um passo de ativar sua conta. Use o código abaixo para verificar seu email:
                                    </p>
                                    <!-- Code Box -->
                                    <div style="background: linear-gradient(145deg, #252545 0%, #1e1e3f 100%); border-radius: 16px; padding: 30px; text-align: center; border: 1px solid rgba(102, 126, 234, 0.3);">
                                        <p style="color: #667eea; font-size: 14px; margin: 0 0 15px; text-transform: uppercase; letter-spacing: 2px;">
                                            Seu código de verificação
                                        </p>
                                        <div style="font-size: 42px; font-weight: 700; letter-spacing: 12px; color: #ffffff; font-family: 'Courier New', monospace;">
                                            {code}
                                        </div>
                                        <p style="color: #f5576c; font-size: 13px; margin: 20px 0 0;">
                                            ⏱️ Expira em {settings.VERIFICATION_CODE_EXPIRE_MINUTES} minutos
                                        </p>
                                    </div>
                                    <!-- Security Notice -->
                                    <div style="margin-top: 30px; padding: 20px; background: rgba(245, 87, 108, 0.1); border-radius: 12px; border-left: 4px solid #f5576c;">
                                        <p style="color: #f5576c; font-size: 14px; margin: 0;">
                                            🔒 Se você não solicitou este código, ignore este email.
                                        </p>
                                    </div>
                                </td>
                            </tr>
                            <!-- Footer -->
                            <tr>
                                <td style="padding: 30px; background: rgba(0,0,0,0.2); text-align: center;">
                                    <p style="color: #606080; font-size: 12px; margin: 0;">
                                        © 2026 IRIS Assistant • Todos os direitos reservados
                                    </p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """

        text_content = f"""
IRIS - Sua Assistente Pessoal

Olá, {name}!

Seu código de verificação é: {code}

Este código expira em {settings.VERIFICATION_CODE_EXPIRE_MINUTES} minutos.

Se você não solicitou esta verificação, ignore este email.

---
© 2026 IRIS Assistant
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

        subject = "🔑 Redefinição de Senha - IRIS"

        html_content = f"""
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="margin: 0; padding: 0; background-color: #0f0f23; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #0f0f23; padding: 40px 20px;">
                <tr>
                    <td align="center">
                        <table role="presentation" width="600" cellspacing="0" cellpadding="0" style="background: linear-gradient(145deg, #1a1a2e 0%, #16213e 100%); border-radius: 20px; overflow: hidden; box-shadow: 0 20px 60px rgba(0,0,0,0.5);">
                            <!-- Header -->
                            <tr>
                                <td style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); padding: 40px; text-align: center;">
                                    <h1 style="margin: 0; color: #ffffff; font-size: 32px; font-weight: 700;">
                                        🔑 Redefinição de Senha
                                    </h1>
                                    <p style="margin: 10px 0 0; color: rgba(255,255,255,0.9); font-size: 14px;">
                                        IRIS • Sua Assistente Pessoal
                                    </p>
                                </td>
                            </tr>
                            <!-- Content -->
                            <tr>
                                <td style="padding: 40px;">
                                    <h2 style="color: #ffffff; margin: 0 0 20px; font-size: 24px;">
                                        Olá, {name}! 👋
                                    </h2>
                                    <p style="color: #a0a0b0; font-size: 16px; line-height: 1.6; margin: 0 0 30px;">
                                        Recebemos uma solicitação para redefinir a senha da sua conta. Use o código abaixo para criar uma nova senha:
                                    </p>
                                    <!-- Code Box -->
                                    <div style="background: linear-gradient(145deg, #352545 0%, #2e1e3f 100%); border-radius: 16px; padding: 30px; text-align: center; border: 1px solid rgba(240, 147, 251, 0.3);">
                                        <p style="color: #f093fb; font-size: 14px; margin: 0 0 15px; text-transform: uppercase; letter-spacing: 2px;">
                                            Código de redefinição
                                        </p>
                                        <div style="font-size: 42px; font-weight: 700; letter-spacing: 12px; color: #ffffff; font-family: 'Courier New', monospace;">
                                            {code}
                                        </div>
                                        <p style="color: #f5576c; font-size: 13px; margin: 20px 0 0;">
                                            ⏱️ Expira em {settings.VERIFICATION_CODE_EXPIRE_MINUTES} minutos
                                        </p>
                                    </div>
                                    <!-- Security Notice -->
                                    <div style="margin-top: 30px; padding: 20px; background: rgba(245, 87, 108, 0.15); border-radius: 12px; border-left: 4px solid #f5576c;">
                                        <p style="color: #ff8a9b; font-size: 14px; margin: 0; line-height: 1.5;">
                                            ⚠️ <strong>Importante:</strong> Se você não solicitou esta redefinição, ignore este email. Sua senha permanecerá a mesma.
                                        </p>
                                    </div>
                                </td>
                            </tr>
                            <!-- Footer -->
                            <tr>
                                <td style="padding: 30px; background: rgba(0,0,0,0.2); text-align: center;">
                                    <p style="color: #606080; font-size: 12px; margin: 0;">
                                        © 2026 IRIS Assistant • Todos os direitos reservados
                                    </p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """

        text_content = f"""
IRIS - Redefinição de Senha

Olá, {name}!

Recebemos uma solicitação para redefinir sua senha.

Seu código de redefinição é: {code}

Este código expira em {settings.VERIFICATION_CODE_EXPIRE_MINUTES} minutos.

IMPORTANTE: Se você não solicitou esta redefinição, ignore este email.

---
© 2026 IRIS Assistant
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

        subject = "🎉 Bem-vindo à IRIS! Sua conta está ativa"

        html_content = f"""
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="margin: 0; padding: 0; background-color: #0f0f23; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #0f0f23; padding: 40px 20px;">
                <tr>
                    <td align="center">
                        <table role="presentation" width="600" cellspacing="0" cellpadding="0" style="background: linear-gradient(145deg, #1a1a2e 0%, #16213e 100%); border-radius: 20px; overflow: hidden; box-shadow: 0 20px 60px rgba(0,0,0,0.5);">
                            <!-- Header -->
                            <tr>
                                <td style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); padding: 50px 40px; text-align: center;">
                                    <h1 style="margin: 0; color: #ffffff; font-size: 36px; font-weight: 700;">
                                        🎉 Bem-vindo!
                                    </h1>
                                    <p style="margin: 15px 0 0; color: rgba(255,255,255,0.95); font-size: 18px;">
                                        Sua conta IRIS está pronta para usar
                                    </p>
                                </td>
                            </tr>
                            <!-- Content -->
                            <tr>
                                <td style="padding: 40px;">
                                    <h2 style="color: #ffffff; margin: 0 0 20px; font-size: 24px;">
                                        Olá, {name}! ✨
                                    </h2>
                                    <p style="color: #a0a0b0; font-size: 16px; line-height: 1.6; margin: 0 0 30px;">
                                        Sua conta foi verificada com sucesso! Agora você tem acesso completo a todos os recursos da IRIS:
                                    </p>
                                    <!-- Features Grid -->
                                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                                        <tr>
                                            <td style="padding: 8px;">
                                                <div style="background: linear-gradient(145deg, #252545 0%, #1e1e3f 100%); border-radius: 12px; padding: 20px; border-left: 4px solid #38ef7d;">
                                                    <p style="color: #38ef7d; font-size: 20px; margin: 0 0 8px;">📝</p>
                                                    <p style="color: #ffffff; font-size: 15px; font-weight: 600; margin: 0 0 5px;">Lembretes Inteligentes</p>
                                                    <p style="color: #8080a0; font-size: 13px; margin: 0;">Nunca mais esqueça compromissos</p>
                                                </div>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td style="padding: 8px;">
                                                <div style="background: linear-gradient(145deg, #252545 0%, #1e1e3f 100%); border-radius: 12px; padding: 20px; border-left: 4px solid #667eea;">
                                                    <p style="color: #667eea; font-size: 20px; margin: 0 0 8px;">💰</p>
                                                    <p style="color: #ffffff; font-size: 15px; font-weight: 600; margin: 0 0 5px;">Controle Financeiro</p>
                                                    <p style="color: #8080a0; font-size: 13px; margin: 0;">Acompanhe receitas e despesas</p>
                                                </div>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td style="padding: 8px;">
                                                <div style="background: linear-gradient(145deg, #252545 0%, #1e1e3f 100%); border-radius: 12px; padding: 20px; border-left: 4px solid #f093fb;">
                                                    <p style="color: #f093fb; font-size: 20px; margin: 0 0 8px;">📅</p>
                                                    <p style="color: #ffffff; font-size: 15px; font-weight: 600; margin: 0 0 5px;">Reuniões & Agenda</p>
                                                    <p style="color: #8080a0; font-size: 13px; margin: 0;">Organize e transcreva reuniões</p>
                                                </div>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td style="padding: 8px;">
                                                <div style="background: linear-gradient(145deg, #252545 0%, #1e1e3f 100%); border-radius: 12px; padding: 20px; border-left: 4px solid #f5576c;">
                                                    <p style="color: #f5576c; font-size: 20px; margin: 0 0 8px;">🌐</p>
                                                    <p style="color: #ffffff; font-size: 15px; font-weight: 600; margin: 0 0 5px;">Pesquisa & Investimentos</p>
                                                    <p style="color: #8080a0; font-size: 13px; margin: 0;">Busca na web e dados financeiros</p>
                                                </div>
                                            </td>
                                        </tr>
                                    </table>
                                    <!-- CTA -->
                                    <div style="margin-top: 30px; text-align: center;">
                                        <p style="color: #a0a0b0; font-size: 15px; margin: 0 0 15px;">
                                            Pronto para começar? Acesse o dashboard agora!
                                        </p>
                                    </div>
                                </td>
                            </tr>
                            <!-- Footer -->
                            <tr>
                                <td style="padding: 30px; background: rgba(0,0,0,0.2); text-align: center;">
                                    <p style="color: #38ef7d; font-size: 14px; margin: 0 0 10px;">
                                        ✨ Obrigado por escolher a IRIS!
                                    </p>
                                    <p style="color: #606080; font-size: 12px; margin: 0;">
                                        © 2026 IRIS Assistant • Todos os direitos reservados
                                    </p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """

        text_content = f"""
🎉 Bem-vindo à IRIS!

Olá, {name}!

Sua conta foi verificada com sucesso!

Agora você tem acesso a todos os recursos:
- 📝 Lembretes Inteligentes
- 💰 Controle Financeiro
- 📅 Reuniões & Agenda
- 🌐 Pesquisa & Investimentos

Acesse o dashboard e comece a usar!

---
© 2026 IRIS Assistant
        """

        return self.send_email(to_email, subject, html_content, text_content)


# Singleton instance
email_service = EmailService()
