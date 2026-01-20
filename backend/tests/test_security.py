"""
Testes para módulos de segurança - IRIS.
"""
import pytest
from datetime import datetime, timedelta

from app.core.security import (
    PasswordValidator,
    TokenManager,
    LoginAttemptTracker,
    RequestValidator,
    generate_secure_token,
    hash_data,
    mask_sensitive_data,
    SecurityConfig
)
from app.core.input_sanitizer import InputSanitizer


class TestPasswordValidator:
    """Testes para validação de senhas."""
    
    def test_valid_password(self):
        """Testa senha válida."""
        is_valid, errors = PasswordValidator.validate("SenhaForte123")
        assert is_valid
        assert len(errors) == 0
    
    def test_short_password(self):
        """Testa senha muito curta."""
        is_valid, errors = PasswordValidator.validate("Ab1")
        assert not is_valid
        assert any("mínimo" in e for e in errors)
    
    def test_no_uppercase(self):
        """Testa senha sem maiúscula."""
        is_valid, errors = PasswordValidator.validate("senhafraca123")
        assert not is_valid
        assert any("maiúscula" in e for e in errors)
    
    def test_no_lowercase(self):
        """Testa senha sem minúscula."""
        is_valid, errors = PasswordValidator.validate("SENHAFORCA123")
        assert not is_valid
        assert any("minúscula" in e for e in errors)
    
    def test_no_digit(self):
        """Testa senha sem número."""
        is_valid, errors = PasswordValidator.validate("SenhaForte")
        assert not is_valid
        assert any("número" in e for e in errors)
    
    def test_common_password(self):
        """Testa senha comum."""
        is_valid, errors = PasswordValidator.validate("123456")
        assert not is_valid
        assert any("comum" in e for e in errors)
    
    def test_hash_password(self):
        """Testa hash de senha."""
        hashed = PasswordValidator.hash_password("MinhaSenha123")
        assert hashed.startswith("$2b$")
        assert len(hashed) > 50
    
    def test_verify_password(self):
        """Testa verificação de senha."""
        password = "MinhaSenha123"
        hashed = PasswordValidator.hash_password(password)
        
        assert PasswordValidator.verify_password(password, hashed)
        assert not PasswordValidator.verify_password("SenhaErrada", hashed)


class TestTokenManager:
    """Testes para gerenciamento de tokens JWT."""
    
    def test_create_access_token(self):
        """Testa criação de token de acesso."""
        token = TokenManager.create_access_token({"sub": "1"})
        assert token is not None
        assert len(token) > 50
    
    def test_create_refresh_token(self):
        """Testa criação de refresh token."""
        token = TokenManager.create_refresh_token(user_id=1)
        assert token is not None
        assert len(token) > 50
    
    def test_verify_access_token(self):
        """Testa verificação de token válido."""
        token = TokenManager.create_access_token({"sub": "1"})
        payload = TokenManager.verify_token(token, "access")
        
        assert payload is not None
        assert payload["sub"] == "1"
        assert payload["type"] == "access"
    
    def test_verify_invalid_token(self):
        """Testa verificação de token inválido."""
        payload = TokenManager.verify_token("token.invalido.aqui", "access")
        assert payload is None
    
    def test_verify_wrong_token_type(self):
        """Testa verificação com tipo errado."""
        token = TokenManager.create_access_token({"sub": "1"})
        payload = TokenManager.verify_token(token, "refresh")
        assert payload is None


class TestLoginAttemptTracker:
    """Testes para rastreamento de tentativas de login."""
    
    def test_record_success_clears_attempts(self):
        """Testa que sucesso limpa tentativas."""
        identifier = "test_user_1"
        
        # Registrar falhas
        for _ in range(3):
            LoginAttemptTracker.record_attempt(identifier, success=False)
        
        # Registrar sucesso
        LoginAttemptTracker.record_attempt(identifier, success=True)
        
        # Verificar que não está bloqueado
        is_locked, _ = LoginAttemptTracker.is_locked(identifier)
        assert not is_locked
    
    def test_lockout_after_max_attempts(self):
        """Testa bloqueio após tentativas máximas."""
        identifier = "test_user_2"
        
        # Registrar falhas até o limite
        for _ in range(SecurityConfig.MAX_LOGIN_ATTEMPTS):
            LoginAttemptTracker.record_attempt(identifier, success=False)
        
        # Verificar bloqueio
        is_locked, seconds = LoginAttemptTracker.is_locked(identifier)
        assert is_locked
        assert seconds > 0


class TestInputSanitizer:
    """Testes para sanitização de inputs."""
    
    def test_sanitize_normal_message(self):
        """Testa mensagem normal."""
        sanitizer = InputSanitizer()
        result = sanitizer.sanitize_message("Olá, tudo bem?")
        
        assert result.is_safe
        assert result.sanitized == "Olá, tudo bem?"
    
    def test_sanitize_xss_attempt(self):
        """Testa tentativa de XSS."""
        sanitizer = InputSanitizer()
        result = sanitizer.sanitize_message("<script>alert('xss')</script>")
        
        assert not result.is_safe or "<script>" not in result.sanitized
    
    def test_sanitize_sql_injection(self):
        """Testa tentativa de SQL injection."""
        sanitizer = InputSanitizer()
        result = sanitizer.sanitize_message("'; DROP TABLE users; --")
        
        assert not result.is_safe or "DROP TABLE" not in result.sanitized
    
    def test_message_too_long(self):
        """Testa mensagem muito longa."""
        sanitizer = InputSanitizer()
        long_message = "a" * 10000
        result = sanitizer.sanitize_message(long_message)
        
        assert len(result.sanitized) <= sanitizer.config.max_message_length


class TestSecurityUtilities:
    """Testes para utilitários de segurança."""
    
    def test_generate_secure_token(self):
        """Testa geração de token seguro."""
        token1 = generate_secure_token()
        token2 = generate_secure_token()
        
        assert len(token1) >= 32
        assert token1 != token2
    
    def test_hash_data(self):
        """Testa hash de dados."""
        data = "dados sensíveis"
        hash1 = hash_data(data)
        hash2 = hash_data(data)
        
        assert len(hash1) == 64  # SHA-256 hex
        assert hash1 == hash2
    
    def test_mask_sensitive_data(self):
        """Testa mascaramento de dados."""
        masked = mask_sensitive_data("1234567890", visible_chars=4)
        
        assert masked.startswith("1234")
        assert "*" in masked
        assert len(masked) == 10


class TestSecurityConfig:
    """Testes para configuração de segurança."""
    
    def test_security_headers_defined(self):
        """Testa que headers de segurança estão definidos."""
        assert "X-Content-Type-Options" in SecurityConfig.SECURITY_HEADERS
        assert "X-Frame-Options" in SecurityConfig.SECURITY_HEADERS
        assert "X-XSS-Protection" in SecurityConfig.SECURITY_HEADERS
    
    def test_password_requirements(self):
        """Testa requisitos de senha."""
        assert SecurityConfig.MIN_PASSWORD_LENGTH >= 8
        assert SecurityConfig.MAX_LOGIN_ATTEMPTS > 0
