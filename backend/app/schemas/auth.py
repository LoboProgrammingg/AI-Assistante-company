"""
Schemas de autenticação.
"""

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    """Schema para registro de usuário."""

    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    password_confirm: str = Field(..., min_length=8, max_length=100)
    phone_number: str = Field(..., min_length=10, max_length=20)
    timezone: Optional[str] = Field(default="America/Sao_Paulo", max_length=50)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Senha deve ter no mínimo 8 caracteres")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Senha deve conter pelo menos uma letra maiúscula")
        if not re.search(r"[a-z]", v):
            raise ValueError("Senha deve conter pelo menos uma letra minúscula")
        if not re.search(r"\d", v):
            raise ValueError("Senha deve conter pelo menos um número")
        return v

    @field_validator("password_confirm")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("Senhas não conferem")
        return v

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        # Remove caracteres não numéricos exceto +
        cleaned = re.sub(r"[^\d+]", "", v)
        if len(cleaned) < 10:
            raise ValueError("Número de telefone inválido")
        return cleaned


class RegisterResponse(BaseModel):
    """Schema de resposta do registro."""

    message: str
    email: str
    requires_verification: bool = True


class VerifyEmailRequest(BaseModel):
    """Schema para verificação de email."""

    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)


class VerifyEmailResponse(BaseModel):
    """Schema de resposta da verificação."""

    message: str
    verified: bool


class ResendCodeRequest(BaseModel):
    """Schema para reenvio de código."""

    email: EmailStr


class ResendCodeResponse(BaseModel):
    """Schema de resposta do reenvio."""

    message: str


class LoginRequest(BaseModel):
    """Schema para login."""

    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Schema de resposta do login."""

    access_token: str
    token_type: str = "bearer"
    user: "UserAuthResponse"


class UserAuthResponse(BaseModel):
    """Schema do usuário na resposta de autenticação."""

    id: int
    name: Optional[str]
    email: str
    phone_number: str
    is_verified: bool
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ForgotPasswordRequest(BaseModel):
    """Schema para solicitar reset de senha."""

    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    """Schema de resposta do forgot password."""

    message: str


class ResetPasswordRequest(BaseModel):
    """Schema para resetar senha."""

    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=8, max_length=100)
    new_password_confirm: str = Field(..., min_length=8, max_length=100)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Senha deve ter no mínimo 8 caracteres")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Senha deve conter pelo menos uma letra maiúscula")
        if not re.search(r"[a-z]", v):
            raise ValueError("Senha deve conter pelo menos uma letra minúscula")
        if not re.search(r"\d", v):
            raise ValueError("Senha deve conter pelo menos um número")
        return v

    @field_validator("new_password_confirm")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("Senhas não conferem")
        return v


class ResetPasswordResponse(BaseModel):
    """Schema de resposta do reset de senha."""

    message: str


class ChangePasswordRequest(BaseModel):
    """Schema para alteração de senha do usuário logado."""

    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=100)
    new_password_confirm: str = Field(..., min_length=8, max_length=100)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Senha deve ter no mínimo 8 caracteres")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Senha deve conter pelo menos uma letra maiúscula")
        if not re.search(r"[a-z]", v):
            raise ValueError("Senha deve conter pelo menos uma letra minúscula")
        if not re.search(r"\d", v):
            raise ValueError("Senha deve conter pelo menos um número")
        return v

    @field_validator("new_password_confirm")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("Senhas não conferem")
        return v


class ChangePasswordResponse(BaseModel):
    """Schema de resposta da alteração de senha."""

    message: str


# Update forward references
LoginResponse.model_rebuild()
