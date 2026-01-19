from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.api.deps import get_db, get_current_user, create_access_token
from app.models import User
from app.schemas import UserCreate, UserUpdate, UserResponse, UserStats
from app.services import ReminderService, FinanceService, MeetingService, cache_service

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    data: UserCreate,
    db: Session = Depends(get_db)
):
    """
    Cria novo usuário.
    Retorna token JWT no header X-Auth-Token.
    """
    existing = db.query(User).filter(
        User.phone_number == data.phone_number
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuário já existe com este número"
        )
    
    import uuid
    user = User(
        phone_number=data.phone_number,
        name=data.name,
        timezone=data.timezone,
        language=data.language,
        preferences=data.preferences,
        session_id=str(uuid.uuid4()),
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return user


@router.post("/token")
def login(
    data: dict,
    db: Session = Depends(get_db)
):
    """
    Autentica usuário por número de telefone e retorna token JWT.
    Se usuário não existir, retorna 404.
    """
    phone_number = data.get("phone_number")
    if not phone_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="phone_number é obrigatório"
        )
    
    user = db.query(User).filter(
        User.phone_number == phone_number
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )
    
    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Retorna dados do usuário autenticado."""
    return current_user


@router.put("/me", response_model=UserResponse)
def update_current_user(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Atualiza dados do usuário autenticado."""
    update_data = data.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(current_user, field, value)
    
    current_user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(current_user)
    
    return current_user


@router.get("/me/stats", response_model=UserStats)
def get_user_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retorna estatísticas do usuário (com cache de 5 min)."""
    cache_key = cache_service.get_user_stats_key(current_user.id)
    
    # Tentar obter do cache
    cached = cache_service.get(cache_key)
    if cached:
        return UserStats(**cached)
    
    # Calcular stats
    reminder_service = ReminderService(db)
    finance_service = FinanceService(db)
    meeting_service = MeetingService(db)
    
    reminder_counts = reminder_service.count_by_user(current_user.id)
    finance_totals = finance_service.get_totals_by_user(current_user.id)
    
    from app.models import Message
    total_messages = db.query(Message).filter(Message.user_id == current_user.id).count()
    
    stats = UserStats(
        total_reminders=reminder_counts["total"],
        active_reminders=reminder_counts["active"],
        completed_reminders=reminder_counts.get("completed", 0),
        total_transactions=finance_service.count_by_user(current_user.id),
        total_income=finance_totals["total_income"],
        total_expenses=finance_totals["total_expenses"],
        total_meetings=meeting_service.count_by_user(current_user.id),
        total_messages=total_messages,
        member_since=current_user.created_at,
        last_activity=current_user.last_interaction,
    )
    
    # Salvar no cache (5 min)
    cache_service.set(cache_key, stats.model_dump(), ttl_seconds=300)
    
    return stats


@router.post("/me/token")
def generate_token(
    current_user: User = Depends(get_current_user)
):
    """Gera novo token JWT para o usuário."""
    token = create_access_token(current_user.id)
    return {"access_token": token, "token_type": "bearer"}


@router.get("/by-phone/{phone_number}", response_model=UserResponse)
def get_user_by_phone(
    phone_number: str,
    db: Session = Depends(get_db)
):
    """
    Busca usuário por número de telefone.
    Endpoint interno para uso do webhook.
    """
    user = db.query(User).filter(
        User.phone_number == phone_number
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )
    
    return user
