"""
Serviço de autenticação.
"""
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import bcrypt
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    User, 
    VerificationToken, 
    VerificationTokenType,
    Plan,
    PlanType,
    Subscription,
    SubscriptionStatus
)
from app.services.email_service import email_service

logger = logging.getLogger(__name__)


class AuthService:
    """Serviço de autenticação e gerenciamento de usuários."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def hash_password(self, password: str) -> str:
        """Gera hash da senha usando bcrypt."""
        password_bytes = password.encode('utf-8')[:72]
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode('utf-8')
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verifica se a senha corresponde ao hash."""
        password_bytes = plain_password.encode('utf-8')[:72]
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    
    def generate_verification_code(self) -> str:
        """Gera código de verificação de 6 dígitos."""
        return "".join([str(secrets.randbelow(10)) for _ in range(6)])
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Busca usuário por email."""
        return self.db.query(User).filter(User.email == email.lower()).first()
    
    def get_user_by_phone(self, phone_number: str) -> Optional[User]:
        """Busca usuário por telefone."""
        return self.db.query(User).filter(User.phone_number == phone_number).first()
    
    def register_user(
        self,
        name: str,
        email: str,
        password: str,
        phone_number: str,
        user_timezone: str = None
    ) -> Tuple[User, str]:
        """
        Registra novo usuário.
        
        Args:
            name: Nome completo
            email: Email
            password: Senha
            phone_number: Número de telefone
            timezone: Timezone do usuário (ex: America/Cuiaba)
            
        Returns:
            Tuple[User, str]: Usuário criado e código de verificação
            
        Raises:
            ValueError: Se email ou telefone já existir
        """
        email_lower = email.lower()
        
        if self.get_user_by_email(email_lower):
            raise ValueError("Email já cadastrado")
        
        if self.get_user_by_phone(phone_number):
            raise ValueError("Telefone já cadastrado")
        
        user = User(
            name=name,
            email=email_lower,
            password_hash=self.hash_password(password),
            phone_number=phone_number,
            session_id=str(uuid.uuid4()),
            is_verified=False,
            is_active=True,
            timezone=user_timezone or settings.DEFAULT_TIMEZONE
        )
        
        self.db.add(user)
        self.db.flush()
        
        # Criar token de verificação
        code = self.generate_verification_code()
        token = VerificationToken(
            user_id=user.id,
            token=code,
            token_type=VerificationTokenType.EMAIL_VERIFICATION,
            expires_at=datetime.now(timezone.utc) + timedelta(
                minutes=settings.VERIFICATION_CODE_EXPIRE_MINUTES
            )
        )
        self.db.add(token)
        
        # Atribuir plano FREE
        self._assign_free_plan(user.id)
        
        self.db.commit()
        self.db.refresh(user)
        
        # Enviar email de verificação
        email_service.send_verification_code(email_lower, code, name)
        
        logger.info(f"Novo usuário registrado: {email_lower}")
        
        return user, code
    
    def _assign_free_plan(self, user_id: int) -> None:
        """Atribui plano FREE ao usuário."""
        free_plan = self.db.query(Plan).filter(Plan.type == PlanType.FREE).first()
        
        if not free_plan:
            # Criar plano FREE se não existir
            free_plan = Plan(
                name="Free",
                type=PlanType.FREE,
                description="Plano gratuito com todas as funcionalidades",
                price=0.0,
                features={
                    "reminders": True,
                    "finances": True,
                    "meetings": True,
                    "contacts": True,
                    "whatsapp_ai": True,
                    "scheduled_messages": True
                },
                limits={
                    "reminders_per_month": -1,  # -1 = ilimitado
                    "transactions_per_month": -1,
                    "meetings_per_month": -1,
                    "contacts": -1,
                    "messages_per_day": -1
                },
                is_active=True
            )
            self.db.add(free_plan)
            self.db.flush()
        
        subscription = Subscription(
            user_id=user_id,
            plan_id=free_plan.id,
            status=SubscriptionStatus.ACTIVE,
            starts_at=datetime.now(timezone.utc),
            expires_at=None  # FREE não expira
        )
        self.db.add(subscription)
    
    def verify_email(self, email: str, code: str) -> bool:
        """
        Verifica email do usuário.
        
        Args:
            email: Email do usuário
            code: Código de verificação
            
        Returns:
            True se verificado com sucesso
            
        Raises:
            ValueError: Se código inválido ou expirado
        """
        user = self.get_user_by_email(email)
        if not user:
            raise ValueError("Usuário não encontrado")
        
        if user.is_verified:
            raise ValueError("Email já verificado")
        
        token = self.db.query(VerificationToken).filter(
            VerificationToken.user_id == user.id,
            VerificationToken.token == code,
            VerificationToken.token_type == VerificationTokenType.EMAIL_VERIFICATION,
            VerificationToken.used == False,
            VerificationToken.expires_at > datetime.now(timezone.utc)
        ).first()
        
        if not token:
            raise ValueError("Código inválido ou expirado")
        
        # Marcar token como usado
        token.used = True
        
        # Verificar usuário
        user.is_verified = True
        user.updated_at = datetime.now(timezone.utc)
        
        self.db.commit()
        
        # Enviar email de boas-vindas
        email_service.send_welcome(user.email, user.name)
        
        logger.info(f"Email verificado: {email}")
        
        return True
    
    def resend_verification_code(self, email: str) -> str:
        """
        Reenvia código de verificação.
        
        Args:
            email: Email do usuário
            
        Returns:
            Novo código de verificação
            
        Raises:
            ValueError: Se usuário não encontrado ou já verificado
        """
        user = self.get_user_by_email(email)
        if not user:
            raise ValueError("Usuário não encontrado")
        
        if user.is_verified:
            raise ValueError("Email já verificado")
        
        # Invalidar tokens anteriores
        self.db.query(VerificationToken).filter(
            VerificationToken.user_id == user.id,
            VerificationToken.token_type == VerificationTokenType.EMAIL_VERIFICATION,
            VerificationToken.used == False
        ).update({"used": True})
        
        # Criar novo token
        code = self.generate_verification_code()
        token = VerificationToken(
            user_id=user.id,
            token=code,
            token_type=VerificationTokenType.EMAIL_VERIFICATION,
            expires_at=datetime.now(timezone.utc) + timedelta(
                minutes=settings.VERIFICATION_CODE_EXPIRE_MINUTES
            )
        )
        self.db.add(token)
        self.db.commit()
        
        # Enviar email
        email_service.send_verification_code(email, code, user.name)
        
        logger.info(f"Código de verificação reenviado: {email}")
        
        return code
    
    def authenticate(self, email: str, password: str) -> User:
        """
        Autentica usuário.
        
        Args:
            email: Email
            password: Senha
            
        Returns:
            Usuário autenticado
            
        Raises:
            ValueError: Se credenciais inválidas ou conta não verificada
        """
        user = self.get_user_by_email(email)
        
        if not user or not user.password_hash:
            raise ValueError("Credenciais inválidas")
        
        if not self.verify_password(password, user.password_hash):
            raise ValueError("Credenciais inválidas")
        
        if not user.is_verified:
            raise ValueError("Email não verificado. Verifique seu email antes de fazer login.")
        
        if not user.is_active:
            raise ValueError("Conta desativada")
        
        # Atualizar última interação
        user.last_interaction = datetime.now(timezone.utc)
        self.db.commit()
        
        logger.info(f"Login bem-sucedido: {email}")
        
        return user
    
    def request_password_reset(self, email: str) -> Optional[str]:
        """
        Solicita reset de senha.
        
        Args:
            email: Email do usuário
            
        Returns:
            Código de reset ou None se usuário não encontrado
        """
        user = self.get_user_by_email(email)
        if not user:
            return None  # Não revelar se email existe
        
        # Invalidar tokens anteriores
        self.db.query(VerificationToken).filter(
            VerificationToken.user_id == user.id,
            VerificationToken.token_type == VerificationTokenType.PASSWORD_RESET,
            VerificationToken.used == False
        ).update({"used": True})
        
        # Criar novo token
        code = self.generate_verification_code()
        token = VerificationToken(
            user_id=user.id,
            token=code,
            token_type=VerificationTokenType.PASSWORD_RESET,
            expires_at=datetime.now(timezone.utc) + timedelta(
                minutes=settings.VERIFICATION_CODE_EXPIRE_MINUTES
            )
        )
        self.db.add(token)
        self.db.commit()
        
        # Enviar email
        email_service.send_password_reset(email, code, user.name)
        
        logger.info(f"Reset de senha solicitado: {email}")
        
        return code
    
    def reset_password(self, email: str, code: str, new_password: str) -> bool:
        """
        Redefine senha do usuário.
        
        Args:
            email: Email do usuário
            code: Código de reset
            new_password: Nova senha
            
        Returns:
            True se senha redefinida
            
        Raises:
            ValueError: Se código inválido ou expirado
        """
        user = self.get_user_by_email(email)
        if not user:
            raise ValueError("Usuário não encontrado")
        
        token = self.db.query(VerificationToken).filter(
            VerificationToken.user_id == user.id,
            VerificationToken.token == code,
            VerificationToken.token_type == VerificationTokenType.PASSWORD_RESET,
            VerificationToken.used == False,
            VerificationToken.expires_at > datetime.now(timezone.utc)
        ).first()
        
        if not token:
            raise ValueError("Código inválido ou expirado")
        
        # Marcar token como usado
        token.used = True
        
        # Atualizar senha
        user.password_hash = self.hash_password(new_password)
        user.updated_at = datetime.now(timezone.utc)
        
        self.db.commit()
        
        logger.info(f"Senha redefinida: {email}")
        
        return True
    
    def change_password(self, user_id: int, current_password: str, new_password: str) -> bool:
        """
        Altera senha do usuário logado.
        
        Args:
            user_id: ID do usuário
            current_password: Senha atual
            new_password: Nova senha
            
        Returns:
            True se senha alterada
            
        Raises:
            ValueError: Se senha atual incorreta
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("Usuário não encontrado")
        
        if not user.password_hash:
            raise ValueError("Usuário não possui senha configurada")
        
        if not self.verify_password(current_password, user.password_hash):
            raise ValueError("Senha atual incorreta")
        
        user.password_hash = self.hash_password(new_password)
        user.updated_at = datetime.now(timezone.utc)
        
        self.db.commit()
        
        logger.info(f"Senha alterada para usuário {user_id}")
        
        return True

    def authorize_phone_for_ai(self, phone_number: str, user_id: int) -> bool:
        """
        Autoriza número de telefone para interagir com a IA.
        
        Esta função é chamada após o registro bem-sucedido para
        garantir que o número do usuário possa usar o WhatsApp AI.
        
        Args:
            phone_number: Número de telefone
            user_id: ID do usuário
            
        Returns:
            True se autorizado
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        
        # O número já está vinculado ao usuário no registro
        # Aqui podemos adicionar lógica adicional se necessário
        # Por exemplo, enviar mensagem de boas-vindas via WhatsApp
        
        logger.info(f"Telefone {phone_number} autorizado para IA (user_id={user_id})")
        
        return True
