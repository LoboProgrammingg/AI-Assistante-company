"""
Templates de email profissionais para IRIS.

Arquitetura enterprise com templates modulares e reutilizáveis.
Design system consistente com variáveis CSS inline para máxima compatibilidade.
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class EmailColors:
    """Design tokens - cores do sistema."""
    
    PRIMARY: str = "#667eea"
    PRIMARY_DARK: str = "#5a67d8"
    SECONDARY: str = "#764ba2"
    SUCCESS: str = "#38ef7d"
    SUCCESS_DARK: str = "#11998e"
    WARNING: str = "#f5576c"
    WARNING_LIGHT: str = "#ff8a9b"
    ACCENT: str = "#f093fb"
    
    BG_DARK: str = "#0f0f23"
    BG_CARD: str = "#1a1a2e"
    BG_CARD_ALT: str = "#16213e"
    BG_INPUT: str = "#252545"
    BG_INPUT_ALT: str = "#1e1e3f"
    
    TEXT_PRIMARY: str = "#ffffff"
    TEXT_SECONDARY: str = "#a0a0b0"
    TEXT_MUTED: str = "#606080"
    TEXT_ACCENT: str = "#8080a0"


COLORS = EmailColors()


def base_template(content: str, preheader: str = "") -> str:
    """
    Template base HTML para todos os emails.
    
    Args:
        content: Conteúdo HTML do email
        preheader: Texto de preview (aparece em clients de email)
    """
    return f"""<!DOCTYPE html>
<html lang="pt-BR" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <meta name="x-apple-disable-message-reformatting">
    <meta name="format-detection" content="telephone=no,address=no,email=no,date=no,url=no">
    <title>IRIS</title>
    <!--[if mso]>
    <noscript>
        <xml>
            <o:OfficeDocumentSettings>
                <o:PixelsPerInch>96</o:PixelsPerInch>
            </o:OfficeDocumentSettings>
        </xml>
    </noscript>
    <![endif]-->
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body, table, td, a {{ -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }}
        table, td {{ mso-table-lspace: 0pt; mso-table-rspace: 0pt; }}
        img {{ -ms-interpolation-mode: bicubic; border: 0; height: auto; line-height: 100%; outline: none; text-decoration: none; }}
        body {{ height: 100% !important; margin: 0 !important; padding: 0 !important; width: 100% !important; background-color: {COLORS.BG_DARK}; }}
        a[x-apple-data-detectors] {{ color: inherit !important; text-decoration: none !important; font-size: inherit !important; font-family: inherit !important; font-weight: inherit !important; line-height: inherit !important; }}
        @media only screen and (max-width: 600px) {{
            .container {{ width: 100% !important; max-width: 100% !important; }}
            .content-padding {{ padding: 24px 16px !important; }}
            .code-display {{ font-size: 32px !important; letter-spacing: 8px !important; }}
        }}
    </style>
</head>
<body style="margin: 0; padding: 0; background-color: {COLORS.BG_DARK}; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Fira Sans', 'Droid Sans', 'Helvetica Neue', Arial, sans-serif;">
    <!-- Preheader -->
    <div style="display: none; max-height: 0; overflow: hidden; mso-hide: all;">
        {preheader}
        &nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;
    </div>
    
    <!-- Email Container -->
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: {COLORS.BG_DARK};">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" class="container" style="max-width: 600px; background: linear-gradient(145deg, {COLORS.BG_CARD} 0%, {COLORS.BG_CARD_ALT} 100%); border-radius: 20px; overflow: hidden; box-shadow: 0 20px 60px rgba(0,0,0,0.5);">
                    {content}
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""


def header_section(
    title: str,
    subtitle: str = "",
    gradient_start: str = COLORS.PRIMARY,
    gradient_end: str = COLORS.SECONDARY,
    icon: str = "✨"
) -> str:
    """Seção de cabeçalho do email."""
    subtitle_html = f'<p style="margin: 10px 0 0; color: rgba(255,255,255,0.9); font-size: 14px; font-weight: 400;">{subtitle}</p>' if subtitle else ""
    
    return f"""
    <tr>
        <td style="background: linear-gradient(135deg, {gradient_start} 0%, {gradient_end} 100%); padding: 48px 40px; text-align: center;">
            <h1 style="margin: 0; color: {COLORS.TEXT_PRIMARY}; font-size: 32px; font-weight: 700; letter-spacing: 1px;">
                {icon} {title}
            </h1>
            {subtitle_html}
        </td>
    </tr>"""


def footer_section(highlight_text: str = "", year: int = 2026) -> str:
    """Seção de rodapé do email."""
    highlight_html = f'<p style="color: {COLORS.SUCCESS}; font-size: 14px; margin: 0 0 12px; font-weight: 500;">{highlight_text}</p>' if highlight_text else ""
    
    return f"""
    <tr>
        <td style="padding: 32px 40px; background: rgba(0,0,0,0.25); text-align: center; border-top: 1px solid rgba(255,255,255,0.05);">
            {highlight_html}
            <p style="color: {COLORS.TEXT_MUTED}; font-size: 12px; margin: 0; line-height: 1.6;">
                © {year} IRIS Assistant • Todos os direitos reservados
            </p>
            <p style="color: {COLORS.TEXT_MUTED}; font-size: 11px; margin: 8px 0 0; opacity: 0.7;">
                Este é um email automático, por favor não responda.
            </p>
        </td>
    </tr>"""


def code_box(
    code: str,
    label: str = "Seu código",
    expire_text: str = "",
    accent_color: str = COLORS.PRIMARY
) -> str:
    """Caixa de código de verificação."""
    expire_html = f'<p style="color: {COLORS.WARNING}; font-size: 13px; margin: 20px 0 0; font-weight: 500;">⏱️ {expire_text}</p>' if expire_text else ""
    
    return f"""
    <div style="background: linear-gradient(145deg, {COLORS.BG_INPUT} 0%, {COLORS.BG_INPUT_ALT} 100%); border-radius: 16px; padding: 32px; text-align: center; border: 1px solid rgba(102, 126, 234, 0.2); margin: 24px 0;">
        <p style="color: {accent_color}; font-size: 12px; margin: 0 0 16px; text-transform: uppercase; letter-spacing: 3px; font-weight: 600;">
            {label}
        </p>
        <div class="code-display" style="font-size: 44px; font-weight: 700; letter-spacing: 14px; color: {COLORS.TEXT_PRIMARY}; font-family: 'SF Mono', 'Fira Code', 'Courier New', monospace; padding: 8px 0;">
            {code}
        </div>
        {expire_html}
    </div>"""


def alert_box(
    message: str,
    type: str = "warning",
    icon: str = "🔒"
) -> str:
    """Caixa de alerta/aviso."""
    colors = {
        "warning": (COLORS.WARNING, "rgba(245, 87, 108, 0.12)"),
        "info": (COLORS.PRIMARY, "rgba(102, 126, 234, 0.12)"),
        "success": (COLORS.SUCCESS, "rgba(56, 239, 125, 0.12)"),
    }
    text_color, bg_color = colors.get(type, colors["warning"])
    
    return f"""
    <div style="margin: 28px 0 0; padding: 20px 24px; background: {bg_color}; border-radius: 12px; border-left: 4px solid {text_color};">
        <p style="color: {text_color}; font-size: 14px; margin: 0; line-height: 1.6;">
            {icon} {message}
        </p>
    </div>"""


def feature_card(
    icon: str,
    title: str,
    description: str,
    accent_color: str = COLORS.SUCCESS
) -> str:
    """Card de feature/funcionalidade."""
    return f"""
    <tr>
        <td style="padding: 8px 0;">
            <div style="background: linear-gradient(145deg, {COLORS.BG_INPUT} 0%, {COLORS.BG_INPUT_ALT} 100%); border-radius: 12px; padding: 20px 24px; border-left: 4px solid {accent_color};">
                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                    <tr>
                        <td width="48" valign="top">
                            <span style="font-size: 24px;">{icon}</span>
                        </td>
                        <td valign="top">
                            <p style="color: {COLORS.TEXT_PRIMARY}; font-size: 15px; font-weight: 600; margin: 0 0 4px;">{title}</p>
                            <p style="color: {COLORS.TEXT_ACCENT}; font-size: 13px; margin: 0; line-height: 1.4;">{description}</p>
                        </td>
                    </tr>
                </table>
            </div>
        </td>
    </tr>"""


class EmailTemplates:
    """Fábrica de templates de email."""
    
    @staticmethod
    def verification_code(
        user_name: str,
        code: str,
        expire_minutes: int = 15
    ) -> Dict[str, str]:
        """Template de código de verificação."""
        content = f"""
        {header_section("IRIS", "Sua Assistente Pessoal Inteligente")}
        <tr>
            <td class="content-padding" style="padding: 40px;">
                <h2 style="color: {COLORS.TEXT_PRIMARY}; margin: 0 0 16px; font-size: 24px; font-weight: 600;">
                    Olá, {user_name}! 👋
                </h2>
                <p style="color: {COLORS.TEXT_SECONDARY}; font-size: 16px; line-height: 1.7; margin: 0 0 8px;">
                    Você está a um passo de ativar sua conta.
                </p>
                <p style="color: {COLORS.TEXT_SECONDARY}; font-size: 16px; line-height: 1.7; margin: 0;">
                    Use o código abaixo para verificar seu email:
                </p>
                
                {code_box(code, "Código de verificação", f"Expira em {expire_minutes} minutos")}
                
                {alert_box("Se você não solicitou este código, ignore este email.")}
            </td>
        </tr>
        {footer_section()}"""
        
        html = base_template(content, f"Seu código de verificação IRIS: {code}")
        
        text = f"""IRIS - Verificação de Email

Olá, {user_name}!

Seu código de verificação é: {code}

Este código expira em {expire_minutes} minutos.

Se você não solicitou esta verificação, ignore este email.

---
© 2026 IRIS Assistant"""
        
        return {"html": html, "text": text, "subject": f"🔐 Código de Verificação: {code} - IRIS"}
    
    @staticmethod
    def password_reset(
        user_name: str,
        code: str,
        expire_minutes: int = 15
    ) -> Dict[str, str]:
        """Template de reset de senha."""
        content = f"""
        {header_section("Redefinição de Senha", "IRIS • Sua Assistente Pessoal", COLORS.ACCENT, COLORS.WARNING, "🔑")}
        <tr>
            <td class="content-padding" style="padding: 40px;">
                <h2 style="color: {COLORS.TEXT_PRIMARY}; margin: 0 0 16px; font-size: 24px; font-weight: 600;">
                    Olá, {user_name}! 👋
                </h2>
                <p style="color: {COLORS.TEXT_SECONDARY}; font-size: 16px; line-height: 1.7; margin: 0 0 8px;">
                    Recebemos uma solicitação para redefinir a senha da sua conta.
                </p>
                <p style="color: {COLORS.TEXT_SECONDARY}; font-size: 16px; line-height: 1.7; margin: 0;">
                    Use o código abaixo para criar uma nova senha:
                </p>
                
                {code_box(code, "Código de redefinição", f"Expira em {expire_minutes} minutos", COLORS.ACCENT)}
                
                {alert_box("<strong>Importante:</strong> Se você não solicitou esta redefinição, ignore este email. Sua senha permanecerá a mesma.", "warning", "⚠️")}
            </td>
        </tr>
        {footer_section()}"""
        
        html = base_template(content, "Código para redefinir sua senha IRIS")
        
        text = f"""IRIS - Redefinição de Senha

Olá, {user_name}!

Recebemos uma solicitação para redefinir sua senha.

Seu código de redefinição é: {code}

Este código expira em {expire_minutes} minutos.

IMPORTANTE: Se você não solicitou esta redefinição, ignore este email.

---
© 2026 IRIS Assistant"""
        
        return {"html": html, "text": text, "subject": "🔑 Redefinição de Senha - IRIS"}
    
    @staticmethod
    def welcome(user_name: str) -> Dict[str, str]:
        """Template de boas-vindas."""
        features = f"""
        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
            {feature_card("📝", "Lembretes Inteligentes", "Nunca mais esqueça compromissos importantes", COLORS.SUCCESS)}
            {feature_card("💰", "Controle Financeiro", "Acompanhe receitas, despesas e metas", COLORS.PRIMARY)}
            {feature_card("📅", "Reuniões & Agenda", "Organize e transcreva suas reuniões", COLORS.ACCENT)}
            {feature_card("🌐", "Pesquisa & Investimentos", "Busca na web e dados financeiros em tempo real", COLORS.WARNING)}
            {feature_card("🎯", "Metas Pessoais", "Defina e acompanhe seus objetivos", "#00d4ff")}
        </table>"""
        
        content = f"""
        {header_section("Bem-vindo!", "Sua conta IRIS está pronta para usar", COLORS.SUCCESS_DARK, COLORS.SUCCESS, "🎉")}
        <tr>
            <td class="content-padding" style="padding: 40px;">
                <h2 style="color: {COLORS.TEXT_PRIMARY}; margin: 0 0 16px; font-size: 24px; font-weight: 600;">
                    Olá, {user_name}! ✨
                </h2>
                <p style="color: {COLORS.TEXT_SECONDARY}; font-size: 16px; line-height: 1.7; margin: 0 0 24px;">
                    Sua conta foi verificada com sucesso! Agora você tem acesso completo a todos os recursos da IRIS:
                </p>
                
                {features}
                
                <div style="margin-top: 32px; text-align: center;">
                    <p style="color: {COLORS.TEXT_SECONDARY}; font-size: 15px; margin: 0;">
                        Pronto para começar? Acesse o dashboard agora!
                    </p>
                </div>
            </td>
        </tr>
        {footer_section("✨ Obrigado por escolher a IRIS!")}"""
        
        html = base_template(content, "Sua conta IRIS foi ativada com sucesso!")
        
        text = f"""🎉 Bem-vindo à IRIS!

Olá, {user_name}!

Sua conta foi verificada com sucesso!

Agora você tem acesso a todos os recursos:
• 📝 Lembretes Inteligentes
• 💰 Controle Financeiro
• 📅 Reuniões & Agenda
• 🌐 Pesquisa & Investimentos
• 🎯 Metas Pessoais

Acesse o dashboard e comece a usar!

---
© 2026 IRIS Assistant"""
        
        return {"html": html, "text": text, "subject": "🎉 Bem-vindo à IRIS! Sua conta está ativa"}
    
    @staticmethod
    def generic_notification(
        user_name: str,
        title: str,
        message: str,
        cta_text: Optional[str] = None,
        cta_url: Optional[str] = None
    ) -> Dict[str, str]:
        """Template genérico de notificação."""
        cta_html = ""
        if cta_text and cta_url:
            cta_html = f"""
            <div style="margin-top: 32px; text-align: center;">
                <a href="{cta_url}" style="display: inline-block; background: linear-gradient(135deg, {COLORS.PRIMARY} 0%, {COLORS.SECONDARY} 100%); color: {COLORS.TEXT_PRIMARY}; text-decoration: none; padding: 14px 32px; border-radius: 8px; font-weight: 600; font-size: 15px;">
                    {cta_text}
                </a>
            </div>"""
        
        content = f"""
        {header_section("IRIS", "Notificação")}
        <tr>
            <td class="content-padding" style="padding: 40px;">
                <h2 style="color: {COLORS.TEXT_PRIMARY}; margin: 0 0 16px; font-size: 24px; font-weight: 600;">
                    {title}
                </h2>
                <p style="color: {COLORS.TEXT_SECONDARY}; font-size: 16px; line-height: 1.7; margin: 0;">
                    Olá, {user_name}!
                </p>
                <p style="color: {COLORS.TEXT_SECONDARY}; font-size: 16px; line-height: 1.7; margin: 16px 0 0;">
                    {message}
                </p>
                {cta_html}
            </td>
        </tr>
        {footer_section()}"""
        
        html = base_template(content, title)
        
        text = f"""{title}

Olá, {user_name}!

{message}

---
© 2026 IRIS Assistant"""
        
        return {"html": html, "text": text, "subject": f"📬 {title} - IRIS"}
