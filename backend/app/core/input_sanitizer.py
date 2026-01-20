"""
Sanitização de inputs para IRIS.
Protege contra injeção e caracteres maliciosos.
"""
import re
import html
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class SanitizerConfig:
    """Configuração do sanitizador."""
    max_message_length: int = 5000
    max_field_length: int = 500
    allow_urls: bool = True
    allow_emojis: bool = True
    strip_html: bool = True
    log_sanitization: bool = True


class InputSanitizer:
    """
    Sanitizador de inputs para proteção contra ataques.
    
    Protege contra:
    - Injeção de comandos
    - XSS (Cross-Site Scripting)
    - SQL Injection básico
    - Caracteres de controle
    - Overflow de tamanho
    """
    
    # Padrões perigosos para detectar
    DANGEROUS_PATTERNS = [
        r'<script[^>]*>.*?</script>',  # Scripts
        r'javascript:',  # JS inline
        r'on\w+\s*=',  # Event handlers
        r'\{\{.*?\}\}',  # Template injection
        r'\$\{.*?\}',  # Template literals
        r';\s*(?:DROP|DELETE|UPDATE|INSERT|TRUNCATE)',  # SQL
        r'--\s*$',  # SQL comment
        r"'\s*(?:OR|AND)\s*'",  # SQL injection
    ]
    
    # Caracteres de controle a remover (exceto newline e tab)
    CONTROL_CHARS = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
    
    def __init__(self, config: SanitizerConfig = None):
        self.config = config or self._load_config_from_settings()
        self._compiled_patterns = [
            re.compile(p, re.IGNORECASE | re.DOTALL) 
            for p in self.DANGEROUS_PATTERNS
        ]
    
    def _load_config_from_settings(self) -> SanitizerConfig:
        """Carrega configuração do settings."""
        return SanitizerConfig(
            max_message_length=getattr(settings, 'MAX_MESSAGE_LENGTH', 5000),
            max_field_length=getattr(settings, 'MAX_FIELD_LENGTH', 500),
            allow_urls=getattr(settings, 'ALLOW_URLS_IN_MESSAGE', True),
            allow_emojis=getattr(settings, 'ALLOW_EMOJIS', True),
            strip_html=getattr(settings, 'STRIP_HTML', True),
            log_sanitization=getattr(settings, 'LOG_SANITIZATION', True),
        )
    
    def sanitize_message(self, message: str) -> str:
        """
        Sanitiza mensagem do usuário.
        
        Args:
            message: Mensagem original
            
        Returns:
            Mensagem sanitizada
        """
        if not message:
            return ""
        
        original = message
        
        # 1. Limitar tamanho
        message = self._truncate(message, self.config.max_message_length)
        
        # 2. Remover caracteres de controle
        message = self._remove_control_chars(message)
        
        # 3. Remover padrões perigosos
        message = self._remove_dangerous_patterns(message)
        
        # 4. Strip HTML se configurado
        if self.config.strip_html:
            message = self._strip_html(message)
        
        # 5. Normalizar espaços
        message = self._normalize_whitespace(message)
        
        # Log se houve mudança
        if self.config.log_sanitization and message != original:
            logger.info(
                f"Mensagem sanitizada: {len(original)} -> {len(message)} chars"
            )
        
        return message.strip()
    
    def sanitize_field(self, value: str, field_name: str = "field") -> str:
        """
        Sanitiza campo específico (nome, telefone, etc).
        
        Args:
            value: Valor do campo
            field_name: Nome do campo para logging
            
        Returns:
            Valor sanitizado
        """
        if not value:
            return ""
        
        value = self._truncate(value, self.config.max_field_length)
        value = self._remove_control_chars(value)
        value = html.escape(value)
        
        return value.strip()
    
    def sanitize_phone(self, phone: str) -> str:
        """Sanitiza número de telefone - apenas dígitos e +."""
        if not phone:
            return ""
        return re.sub(r'[^\d+]', '', phone)[:20]
    
    def sanitize_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitiza dicionário recursivamente.
        
        Args:
            data: Dicionário com dados
            
        Returns:
            Dicionário sanitizado
        """
        sanitized = {}
        
        for key, value in data.items():
            if isinstance(value, str):
                sanitized[key] = self.sanitize_field(value, key)
            elif isinstance(value, dict):
                sanitized[key] = self.sanitize_dict(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    self.sanitize_dict(item) if isinstance(item, dict)
                    else self.sanitize_field(item) if isinstance(item, str)
                    else item
                    for item in value
                ]
            else:
                sanitized[key] = value
        
        return sanitized
    
    def _truncate(self, text: str, max_length: int) -> str:
        """Trunca texto no limite."""
        if len(text) <= max_length:
            return text
        return text[:max_length]
    
    def _remove_control_chars(self, text: str) -> str:
        """Remove caracteres de controle."""
        return self.CONTROL_CHARS.sub('', text)
    
    def _remove_dangerous_patterns(self, text: str) -> str:
        """Remove padrões perigosos."""
        for pattern in self._compiled_patterns:
            if pattern.search(text):
                text = pattern.sub('[REMOVED]', text)
                logger.warning(f"Padrão perigoso detectado e removido")
        return text
    
    def _strip_html(self, text: str) -> str:
        """Remove tags HTML."""
        # Remove tags
        text = re.sub(r'<[^>]+>', '', text)
        # Decode entities
        text = html.unescape(text)
        return text
    
    def _normalize_whitespace(self, text: str) -> str:
        """Normaliza espaços em branco."""
        # Múltiplos espaços -> um
        text = re.sub(r' +', ' ', text)
        # Múltiplas quebras -> máximo 2
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text
    
    def is_safe(self, text: str) -> bool:
        """Verifica se texto é seguro (sem padrões perigosos)."""
        for pattern in self._compiled_patterns:
            if pattern.search(text):
                return False
        return True
    
    def get_violations(self, text: str) -> List[str]:
        """Retorna lista de violações encontradas."""
        violations = []
        
        if len(text) > self.config.max_message_length:
            violations.append(f"Excede tamanho máximo ({self.config.max_message_length})")
        
        for i, pattern in enumerate(self._compiled_patterns):
            if pattern.search(text):
                violations.append(f"Padrão perigoso #{i+1} detectado")
        
        return violations


# Instância global para uso conveniente
_sanitizer: Optional[InputSanitizer] = None


def get_sanitizer() -> InputSanitizer:
    """Retorna instância global do sanitizador."""
    global _sanitizer
    if _sanitizer is None:
        _sanitizer = InputSanitizer()
    return _sanitizer


def sanitize(message: str) -> str:
    """Função utilitária para sanitizar mensagem."""
    return get_sanitizer().sanitize_message(message)
