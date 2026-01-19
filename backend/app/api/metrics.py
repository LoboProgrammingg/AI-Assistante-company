import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel

from app.api.deps import get_db, get_current_user
from app.models import User
from app.services.embedding_service import AgentMetricsService, FeedbackService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/metrics", tags=["metrics"])


class FeedbackRequest(BaseModel):
    feedback_type: str  # "positive", "negative", "correction"
    rating: Optional[int] = None  # 1-5
    agent_name: Optional[str] = None
    message_id: Optional[int] = None
    comment: Optional[str] = None


class FeedbackResponse(BaseModel):
    success: bool
    message: str


@router.post("/feedback", response_model=FeedbackResponse)
def submit_feedback(
    request: FeedbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Submete feedback do usuário sobre uma resposta da IA."""
    service = FeedbackService(db)
    success = service.save_feedback(
        user_id=current_user.id,
        feedback_type=request.feedback_type,
        rating=request.rating,
        agent_name=request.agent_name,
        message_id=request.message_id,
        comment=request.comment
    )
    
    if success:
        return FeedbackResponse(success=True, message="Feedback registrado com sucesso")
    
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Erro ao registrar feedback"
    )


@router.get("/agents")
def get_agent_metrics(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retorna métricas de accuracy por agente."""
    service = AgentMetricsService(db)
    metrics = service.get_accuracy_by_agent(days)
    return {"metrics": metrics, "period_days": days}


@router.get("/user")
def get_user_metrics(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retorna estatísticas de uso do usuário atual."""
    service = AgentMetricsService(db)
    stats = service.get_user_stats(current_user.id, days)
    return {"stats": stats, "period_days": days}


@router.get("/feedback/summary")
def get_feedback_summary(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retorna resumo de feedbacks."""
    service = FeedbackService(db)
    summary = service.get_feedback_summary(days)
    return {"summary": summary, "period_days": days}
