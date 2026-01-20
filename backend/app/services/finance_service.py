import logging
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple


def utc_now():
    """Retorna datetime atual em UTC."""
    return datetime.now(timezone.utc)


from sqlalchemy import and_, extract, func
from sqlalchemy.orm import Session

from app.models import Finance, FinanceCategory, FinanceType
from app.schemas.finance import FinanceCreate, FinanceUpdate

logger = logging.getLogger(__name__)


class FinanceService:
    """Serviço para gerenciamento financeiro."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, user_id: int, data: FinanceCreate) -> Finance:
        """
        Registra uma nova transação financeira.

        Args:
            user_id: ID do usuário
            data: Dados da transação

        Returns:
            Finance: Transação criada
        """
        finance = Finance(
            user_id=user_id,
            type=FinanceType(data.type.value),
            amount=data.amount,
            description=data.description,
            category_id=data.category_id,
            transaction_date=data.transaction_date,
            is_recurring=data.is_recurring,
            tags=data.tags,
        )

        self.db.add(finance)
        self.db.commit()
        self.db.refresh(finance)

        logger.info(f"Transação criada: {finance.id} - R${data.amount}")
        return finance

    def create_from_entities(self, user_id: int, entities: dict) -> Finance:
        """
        Cria transação a partir de entidades extraídas pela IA.

        Args:
            user_id: ID do usuário
            entities: Entidades extraídas

        Returns:
            Finance: Transação criada
        """
        category = self._get_or_create_category(entities.get("category", "Outros"), entities.get("type", "expense"))

        transaction_date_str = entities.get("transaction_date", date.today().isoformat())
        try:
            transaction_date = date.fromisoformat(transaction_date_str)
        except:
            transaction_date = date.today()

        data = FinanceCreate(
            type=entities.get("type", "expense"),
            amount=float(entities.get("amount", 0)),
            description=entities.get("description"),
            category_id=category.id if category else None,
            transaction_date=transaction_date,
            is_recurring=entities.get("is_recurring", False),
            tags=entities.get("tags", []),
        )

        return self.create(user_id, data)

    def _get_or_create_category(self, name: str, finance_type: str) -> Optional[FinanceCategory]:
        """Busca ou cria categoria."""
        category = self.db.query(FinanceCategory).filter(FinanceCategory.name == name).first()

        if not category:
            category = FinanceCategory(
                name=name,
                type=FinanceType(finance_type),
            )
            self.db.add(category)
            self.db.commit()
            self.db.refresh(category)
            logger.info(f"Categoria criada: {name}")

        return category

    def get_by_id(self, finance_id: int, user_id: int) -> Optional[Finance]:
        """Busca transação por ID."""
        return self.db.query(Finance).filter(and_(Finance.id == finance_id, Finance.user_id == user_id)).first()

    def list_transactions(
        self,
        user_id: int,
        finance_type: Optional[str] = None,
        category_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Finance], int]:
        """
        Lista transações com filtros e paginação.

        Args:
            user_id: ID do usuário
            finance_type: income ou expense
            category_id: Filtro por categoria
            start_date: Data inicial
            end_date: Data final
            limit: Quantidade por página
            offset: Offset para paginação

        Returns:
            Tuple: (lista de transações, total)
        """
        query = self.db.query(Finance).filter(Finance.user_id == user_id)

        if finance_type:
            query = query.filter(Finance.type == FinanceType(finance_type))
        if category_id:
            query = query.filter(Finance.category_id == category_id)
        if start_date:
            query = query.filter(Finance.transaction_date >= start_date)
        if end_date:
            query = query.filter(Finance.transaction_date <= end_date)

        total = query.count()

        transactions = query.order_by(Finance.transaction_date.desc()).offset(offset).limit(limit).all()

        return transactions, total

    def update(self, finance_id: int, user_id: int, data: FinanceUpdate) -> Optional[Finance]:
        """Atualiza uma transação."""
        finance = self.get_by_id(finance_id, user_id)
        if not finance:
            return None

        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            if field == "type" and value:
                value = FinanceType(value.value)
            setattr(finance, field, value)

        finance.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(finance)

        logger.info(f"Transação atualizada: {finance_id}")
        return finance

    def delete(self, finance_id: int, user_id: int) -> bool:
        """Remove uma transação."""
        finance = self.get_by_id(finance_id, user_id)
        if not finance:
            return False

        self.db.delete(finance)
        self.db.commit()

        logger.info(f"Transação removida: {finance_id}")
        return True

    def get_summary(self, user_id: int, start_date: date, end_date: date) -> Dict[str, Any]:
        """
        Retorna resumo financeiro do período.

        Args:
            user_id: ID do usuário
            start_date: Data inicial
            end_date: Data final

        Returns:
            Dict com resumo
        """
        income = (
            self.db.query(func.sum(Finance.amount))
            .filter(
                and_(
                    Finance.user_id == user_id,
                    Finance.type == FinanceType.INCOME,
                    Finance.transaction_date >= start_date,
                    Finance.transaction_date <= end_date,
                )
            )
            .scalar()
            or 0
        )

        expenses = (
            self.db.query(func.sum(Finance.amount))
            .filter(
                and_(
                    Finance.user_id == user_id,
                    Finance.type == FinanceType.EXPENSE,
                    Finance.transaction_date >= start_date,
                    Finance.transaction_date <= end_date,
                )
            )
            .scalar()
            or 0
        )

        by_category = (
            self.db.query(
                FinanceCategory.name, func.sum(Finance.amount).label("total"), func.count(Finance.id).label("count")
            )
            .join(Finance)
            .filter(
                and_(
                    Finance.user_id == user_id,
                    Finance.type == FinanceType.EXPENSE,
                    Finance.transaction_date >= start_date,
                    Finance.transaction_date <= end_date,
                )
            )
            .group_by(FinanceCategory.name)
            .all()
        )

        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "summary": {
                "total_income": float(income),
                "total_expenses": float(expenses),
                "balance": float(income - expenses),
                "savings_rate": round((income - expenses) / income * 100, 2) if income > 0 else 0,
            },
            "by_category": [
                {
                    "category": cat.name,
                    "total": float(cat.total),
                    "percentage": round(float(cat.total) / expenses * 100, 2) if expenses > 0 else 0,
                    "transactions_count": cat.count,
                }
                for cat in by_category
            ],
        }

    def get_monthly_summary(self, user_id: int, year: int, month: int) -> Dict[str, Any]:
        """Retorna resumo de um mês específico."""
        start = date(year, month, 1)
        _, last_day = monthrange(year, month)
        end = date(year, month, last_day)

        return self.get_summary(user_id, start, end)

    def get_monthly_trend(self, user_id: int, months: int = 6) -> List[Dict[str, Any]]:
        """
        Retorna tendência mensal.

        Args:
            user_id: ID do usuário
            months: Quantidade de meses

        Returns:
            Lista com dados mensais
        """
        result = []
        today = date.today()

        for i in range(months):
            year = today.year
            month = today.month - i

            if month <= 0:
                month += 12
                year -= 1

            start = date(year, month, 1)
            _, last_day = monthrange(year, month)
            end = date(year, month, last_day)

            summary = self.get_summary(user_id, start, end)
            result.append(
                {
                    "month": start.strftime("%Y-%m"),
                    "income": summary["summary"]["total_income"],
                    "expenses": summary["summary"]["total_expenses"],
                    "balance": summary["summary"]["balance"],
                }
            )

        return list(reversed(result))

    def get_categories(self) -> Dict[str, List[FinanceCategory]]:
        """Retorna todas as categorias organizadas por tipo."""
        categories = self.db.query(FinanceCategory).all()

        return {
            "expense_categories": [c for c in categories if c.type == FinanceType.EXPENSE],
            "income_categories": [c for c in categories if c.type == FinanceType.INCOME],
        }

    def count_by_user(self, user_id: int) -> int:
        """Conta total de transações do usuário."""
        return self.db.query(func.count(Finance.id)).filter(Finance.user_id == user_id).scalar() or 0

    def get_totals_by_user(self, user_id: int) -> Dict[str, float]:
        """Retorna totais de receitas e despesas do usuário."""
        income = (
            self.db.query(func.sum(Finance.amount))
            .filter(and_(Finance.user_id == user_id, Finance.type == FinanceType.INCOME))
            .scalar()
            or 0.0
        )

        expenses = (
            self.db.query(func.sum(Finance.amount))
            .filter(and_(Finance.user_id == user_id, Finance.type == FinanceType.EXPENSE))
            .scalar()
            or 0.0
        )

        return {
            "total_income": float(income),
            "total_expenses": float(expenses),
            "balance": float(income) - float(expenses),
        }
