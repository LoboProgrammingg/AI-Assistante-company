import math
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas import (
    FinanceCategoryResponse,
    FinanceCreate,
    FinanceListResponse,
    FinanceResponse,
    FinanceSummary,
    FinanceUpdate,
)
from app.services import FinanceService

router = APIRouter(prefix="/finances", tags=["finances"])


@router.post("/", response_model=FinanceResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    data: FinanceCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Registra nova transação financeira."""
    service = FinanceService(db)
    transaction = service.create(current_user.id, data)
    return transaction


@router.get("/", response_model=FinanceListResponse)
def list_transactions(
    type: Optional[str] = Query(None, regex="^(income|expense)$"),
    category_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Lista transações financeiras.

    - **type**: income ou expense
    - **category_id**: Filtrar por categoria
    - **start_date**: Data inicial (YYYY-MM-DD)
    - **end_date**: Data final (YYYY-MM-DD)
    """
    service = FinanceService(db)
    offset = (page - 1) * limit

    transactions, total = service.list_transactions(
        user_id=current_user.id,
        finance_type=type,
        category_id=category_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )

    pages = math.ceil(total / limit) if total > 0 else 1

    return FinanceListResponse(
        items=transactions, total=total, page=page, pages=pages, has_next=page < pages, has_prev=page > 1
    )


@router.get("/summary", response_model=FinanceSummary)
def get_summary(
    start_date: date = Query(..., description="Data inicial"),
    end_date: date = Query(..., description="Data final"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retorna resumo financeiro do período."""
    service = FinanceService(db)
    return service.get_summary(current_user.id, start_date, end_date)


@router.get("/summary/monthly")
def get_monthly_summary(
    year: int = Query(..., ge=2020, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retorna resumo de um mês específico."""
    service = FinanceService(db)
    return service.get_monthly_summary(current_user.id, year, month)


@router.get("/trend")
def get_trend(
    months: int = Query(6, ge=1, le=12), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Retorna tendência dos últimos N meses."""
    service = FinanceService(db)
    return {"data": service.get_monthly_trend(current_user.id, months)}


@router.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    """Retorna todas as categorias disponíveis."""
    service = FinanceService(db)
    categories = service.get_categories()
    return {
        "expense_categories": [FinanceCategoryResponse.model_validate(c) for c in categories["expense_categories"]],
        "income_categories": [FinanceCategoryResponse.model_validate(c) for c in categories["income_categories"]],
    }


@router.get("/{finance_id}", response_model=FinanceResponse)
def get_transaction(finance_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Busca transação por ID."""
    service = FinanceService(db)
    transaction = service.get_by_id(finance_id, current_user.id)

    if not transaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transação não encontrada")

    return transaction


@router.put("/{finance_id}", response_model=FinanceResponse)
def update_transaction(
    finance_id: int, data: FinanceUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Atualiza transação."""
    service = FinanceService(db)
    transaction = service.update(finance_id, current_user.id, data)

    if not transaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transação não encontrada")

    return transaction


@router.delete("/{finance_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(finance_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Remove transação."""
    service = FinanceService(db)
    deleted = service.delete(finance_id, current_user.id)

    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transação não encontrada")

    return None
