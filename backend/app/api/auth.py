"""
Endpoints de autenticação.
"""
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db, create_access_token
from app.api.rate_limiter import auth_limiter
from app.services.auth_service import AuthService
from app.schemas import (
    RegisterRequest,
    RegisterResponse,
    VerifyEmailRequest,
    VerifyEmailResponse,
    ResendCodeRequest,
    ResendCodeResponse,
    LoginRequest,
    LoginResponse,
    UserAuthResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    ChangePasswordRequest,
    ChangePasswordResponse,
)
from app.api.deps import get_current_user
from app.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: Request,
    data: RegisterRequest,
    db: Session = Depends(get_db)
):
    # Aplicar rate limiting
    await auth_limiter(request)
    """
    Registra novo usuário.
    
    Após o registro, um código de verificação é enviado para o email.
    O usuário deve verificar o email antes de fazer login.
    """
    auth_service = AuthService(db)
    
    try:
        user, code = auth_service.register_user(
            name=data.name,
            email=data.email,
            password=data.password,
            phone_number=data.phone_number,
            user_timezone=data.timezone
        )
        
        # Autorizar telefone para IA
        auth_service.authorize_phone_for_ai(user.phone_number, user.id)
        
        return RegisterResponse(
            message="Cadastro realizado com sucesso! Verifique seu email para ativar sua conta.",
            email=user.email,
            requires_verification=True
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/verify-email", response_model=VerifyEmailResponse)
def verify_email(
    data: VerifyEmailRequest,
    db: Session = Depends(get_db)
):
    """
    Verifica email do usuário com o código recebido.
    
    Após verificação bem-sucedida, o usuário pode fazer login.
    """
    auth_service = AuthService(db)
    
    try:
        auth_service.verify_email(data.email, data.code)
        
        return VerifyEmailResponse(
            message="Email verificado com sucesso! Você já pode fazer login.",
            verified=True
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/resend-code", response_model=ResendCodeResponse)
def resend_verification_code(
    data: ResendCodeRequest,
    db: Session = Depends(get_db)
):
    """
    Reenvia código de verificação para o email.
    """
    auth_service = AuthService(db)
    
    try:
        auth_service.resend_verification_code(data.email)
        
        return ResendCodeResponse(
            message="Código reenviado com sucesso! Verifique seu email."
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    data: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Autentica usuário com email e senha.
    
    Retorna token JWT para autenticação em endpoints protegidos.
    """
    # Aplicar rate limiting (previne brute force)
    await auth_limiter(request)
    auth_service = AuthService(db)
    
    try:
        user = auth_service.authenticate(data.email, data.password)
        
        token = create_access_token(user.id)
        
        return LoginResponse(
            access_token=token,
            token_type="bearer",
            user=UserAuthResponse(
                id=user.id,
                name=user.name,
                email=user.email,
                phone_number=user.phone_number,
                is_verified=user.is_verified,
                is_active=user.is_active,
                created_at=user.created_at
            )
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(
    request: Request,
    data: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Solicita reset de senha.
    
    Um código de reset é enviado para o email se o usuário existir.
    Por segurança, sempre retorna sucesso mesmo se o email não existir.
    """
    await auth_limiter(request)
    auth_service = AuthService(db)
    
    # Sempre retorna sucesso por segurança
    auth_service.request_password_reset(data.email)
    
    return ForgotPasswordResponse(
        message="Se o email estiver cadastrado, você receberá um código para redefinir sua senha."
    )


@router.post("/reset-password", response_model=ResetPasswordResponse)
async def reset_password(
    request: Request,
    data: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Redefine senha com o código recebido por email.
    """
    await auth_limiter(request)
    auth_service = AuthService(db)
    
    try:
        auth_service.reset_password(data.email, data.code, data.new_password)
        
        return ResetPasswordResponse(
            message="Senha redefinida com sucesso! Você já pode fazer login."
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/change-password", response_model=ChangePasswordResponse)
def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Altera a senha do usuário logado.
    
    Requer autenticação e a senha atual correta.
    """
    auth_service = AuthService(db)
    
    try:
        auth_service.change_password(
            user_id=current_user.id,
            current_password=data.current_password,
            new_password=data.new_password
        )
        
        return ChangePasswordResponse(
            message="Senha alterada com sucesso!"
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/bypass-verify")
async def bypass_verify_email(
    email: str,
    db: Session = Depends(get_db)
):
    """Endpoint temporário para bypass de verificação (apenas para desenvolvimento)"""
    from app.models import User
    
    user = db.query(User).filter(User.email == email.lower()).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )
    
    user.is_verified = True
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    
    return {"message": "Conta verificada com sucesso (bypass)"}
