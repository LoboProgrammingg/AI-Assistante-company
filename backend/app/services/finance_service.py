import logging
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple


def utc_now():
    """Retorna datetime atual em UTC."""
    return datetime.now(timezone.utc)


from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models import Finance, FinanceCategory, FinanceType
from app.schemas.finance import FinanceCreate, FinanceUpdate
from app.services.ai_context_cache import get_ai_cache

logger = logging.getLogger(__name__)


MONTH_NAMES = {
    "janeiro": 1,
    "jan": 1,
    "fevereiro": 2,
    "fev": 2,
    "março": 3,
    "marco": 3,
    "mar": 3,
    "abril": 4,
    "abr": 4,
    "maio": 5,
    "mai": 5,
    "junho": 6,
    "jun": 6,
    "julho": 7,
    "jul": 7,
    "agosto": 8,
    "ago": 8,
    "setembro": 9,
    "set": 9,
    "outubro": 10,
    "out": 10,
    "novembro": 11,
    "nov": 11,
    "dezembro": 12,
    "dez": 12,
}


def parse_period_to_dates(periodo: str, ano: Optional[int] = None) -> Tuple[date, date]:
    """
    Converte período em datas de início e fim.

    Suporta:
    - 'hoje', 'semana', 'mes', 'ano', 'tudo'
    - Nomes de meses: 'janeiro', 'fevereiro', etc.

    Args:
        periodo: Nome do período
        ano: Ano específico (opcional, padrão = ano atual)

    Returns:
        Tuple[date, date]: (data_inicio, data_fim)
    """
    today = date.today()
    current_year = ano or today.year

    periodo_lower = periodo.lower().strip()

    # Verificar se é um nome de mês
    if periodo_lower in MONTH_NAMES:
        month = MONTH_NAMES[periodo_lower]
        start = date(current_year, month, 1)
        _, last_day = monthrange(current_year, month)
        end = date(current_year, month, last_day)
        return start, end

    # Períodos padrão
    if periodo_lower == "hoje":
        return today, today
    elif periodo_lower == "semana":
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        return start, end
    elif periodo_lower == "mes":
        start = date(today.year, today.month, 1)
        _, last_day = monthrange(today.year, today.month)
        end = date(today.year, today.month, last_day)
        return start, end
    elif periodo_lower == "ano":
        start = date(current_year, 1, 1)
        end = date(current_year, 12, 31)
        return start, end
    elif periodo_lower == "tudo":
        start = date(2020, 1, 1)
        end = date(2099, 12, 31)
        return start, end
    elif periodo_lower in ["mes_anterior", "mês_anterior", "mes passado", "mês passado"]:
        # Mês anterior
        if today.month == 1:
            prev_month = 12
            prev_year = today.year - 1
        else:
            prev_month = today.month - 1
            prev_year = today.year
        start = date(prev_year, prev_month, 1)
        _, last_day = monthrange(prev_year, prev_month)
        end = date(prev_year, prev_month, last_day)
        return start, end
    else:
        # Fallback: mês atual
        start = date(today.year, today.month, 1)
        _, last_day = monthrange(today.year, today.month)
        end = date(today.year, today.month, last_day)
        return start, end


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

        # Invalidar cache após criar transação
        get_ai_cache().invalidate_finance(user_id)

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

        # Suporta tanto "date" (da tool) quanto "transaction_date" (legado)
        transaction_date_str = entities.get("date") or entities.get("transaction_date")
        if not transaction_date_str:
            # Usar timezone de Cuiabá para data padrão
            from zoneinfo import ZoneInfo

            transaction_date = datetime.now(ZoneInfo("America/Cuiaba")).date()
        else:
            try:
                transaction_date = date.fromisoformat(transaction_date_str)
            except:
                from zoneinfo import ZoneInfo

                transaction_date = datetime.now(ZoneInfo("America/Cuiaba")).date()

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

        # Invalidar cache após atualização
        get_ai_cache().invalidate_finance(user_id)

        logger.info(f"Transação atualizada: {finance_id}")
        return finance

    def delete(self, finance_id: int, user_id: int) -> bool:
        """Remove uma transação."""
        finance = self.get_by_id(finance_id, user_id)
        if not finance:
            return False

        self.db.delete(finance)
        self.db.commit()

        # Invalidar cache após remoção
        get_ai_cache().invalidate_finance(user_id)

        logger.info(f"Transação removida: {finance_id}")
        return True

    def delete_by_filters(self, user_id: int, filters: dict) -> dict:
        """
        Deleta transações baseado em filtros flexíveis.

        Args:
            user_id: ID do usuário
            filters: Dict com filtros (id, descricao, ultima, data, tipo)

        Returns:
            Dict com resultado da operação
        """
        deleted_count = 0
        deleted_items = []

        # Deletar por ID específico
        if filters.get("id"):
            finance = self.get_by_id(filters["id"], user_id)
            if finance:
                desc = finance.description
                self.db.delete(finance)
                deleted_count += 1
                deleted_items.append(desc)

        # Deletar última transação
        elif filters.get("ultima"):
            finance = (
                self.db.query(Finance).filter(Finance.user_id == user_id).order_by(Finance.created_at.desc()).first()
            )
            if finance:
                desc = finance.description
                self.db.delete(finance)
                deleted_count += 1
                deleted_items.append(desc)

        # Deletar por descrição (busca parcial)
        elif filters.get("descricao"):
            descricao = filters["descricao"].lower().strip()
            data_filtro = filters.get("data")  # Data específica (ex: "hoje")

            query = self.db.query(Finance).filter(
                and_(
                    Finance.user_id == user_id,
                    Finance.description.ilike(f"%{descricao}%"),
                )
            )

            # Filtrar por data se especificado
            if data_filtro == "hoje":
                query = query.filter(Finance.transaction_date == date.today())

            transactions = query.all()
            for finance in transactions:
                deleted_items.append(finance.description)
                self.db.delete(finance)
                deleted_count += 1

        if deleted_count > 0:
            self.db.commit()
            # Invalidar cache após remoção
            get_ai_cache().invalidate_finance(user_id)
            logger.info(f"[FINANCE] Deletadas {deleted_count} transações: {deleted_items}")

        return {
            "deleted_count": deleted_count,
            "deleted_items": deleted_items,
        }

    def update_by_filters(self, user_id: int, filters: dict, updates: dict) -> dict:
        """
        Atualiza transações baseado em filtros.

        Args:
            user_id: ID do usuário
            filters: Dict com filtros para encontrar a transação
            updates: Dict com campos a atualizar

        Returns:
            Dict com resultado da operação
        """
        finance = None

        # Encontrar por ID
        if filters.get("id"):
            finance = self.get_by_id(filters["id"], user_id)

        # Encontrar por descrição (última que bate)
        elif filters.get("descricao"):
            descricao = filters["descricao"].lower().strip()
            finance = (
                self.db.query(Finance)
                .filter(
                    and_(
                        Finance.user_id == user_id,
                        Finance.description.ilike(f"%{descricao}%"),
                    )
                )
                .order_by(Finance.created_at.desc())
                .first()
            )

        # Encontrar última transação
        elif filters.get("ultima"):
            finance = (
                self.db.query(Finance).filter(Finance.user_id == user_id).order_by(Finance.created_at.desc()).first()
            )

        if not finance:
            return {"success": False, "error": "Transação não encontrada"}

        old_desc = finance.description
        old_amount = finance.amount

        # Aplicar atualizações
        if "amount" in updates:
            finance.amount = float(updates["amount"])
        if "description" in updates:
            finance.description = updates["description"]
        if "category" in updates:
            category = self._get_or_create_category(updates["category"], finance.type.value)
            finance.category_id = category.id if category else finance.category_id
        if "type" in updates:
            finance.type = FinanceType(updates["type"])

        finance.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(finance)

        logger.info(f"[FINANCE] Atualizada: '{old_desc}' R${old_amount} -> '{finance.description}' R${finance.amount}")

        return {
            "success": True,
            "old": {"description": old_desc, "amount": float(old_amount)},
            "new": {"description": finance.description, "amount": float(finance.amount)},
        }

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

        # Contar total de transações no período
        total_count = (
            self.db.query(func.count(Finance.id))
            .filter(
                and_(
                    Finance.user_id == user_id,
                    Finance.transaction_date >= start_date,
                    Finance.transaction_date <= end_date,
                )
            )
            .scalar()
            or 0
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
                "count": total_count,
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

    def get_summary_by_period(
        self, user_id: int, periodo: str, ano: Optional[int] = None, busca: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Retorna resumo financeiro baseado em período flexível.

        Suporta:
        - 'hoje', 'semana', 'mes', 'ano', 'tudo'
        - Nomes de meses: 'janeiro', 'fevereiro', etc.
        - Busca por descrição (ex: 'uber', 'almoço')

        Args:
            user_id: ID do usuário
            periodo: Nome do período ou mês
            ano: Ano específico (opcional)
            busca: Filtro por descrição (opcional)

        Returns:
            Dict com resumo financeiro
        """
        start_date, end_date = parse_period_to_dates(periodo, ano)

        # Se há busca, retornar transações filtradas
        if busca:
            return self.get_filtered_transactions(user_id, start_date, end_date, busca)

        summary = self.get_summary(user_id, start_date, end_date)

        # Adicionar nome do período na resposta
        periodo_lower = periodo.lower().strip()
        if periodo_lower in MONTH_NAMES:
            month_name = periodo.capitalize()
            year = ano or date.today().year
            summary["period"]["name"] = f"{month_name} de {year}"
        else:
            summary["period"]["name"] = periodo.capitalize()

        return summary

    def get_filtered_transactions(self, user_id: int, start_date: date, end_date: date, busca: str) -> Dict[str, Any]:
        """
        Retorna transações filtradas por descrição.

        Args:
            user_id: ID do usuário
            start_date: Data inicial
            end_date: Data final
            busca: Termo de busca na descrição

        Returns:
            Dict com transações filtradas e totais
        """
        busca_lower = busca.lower().strip()

        # Buscar transações que contenham o termo na descrição
        query = (
            self.db.query(Finance)
            .filter(
                and_(
                    Finance.user_id == user_id,
                    Finance.transaction_date >= start_date,
                    Finance.transaction_date <= end_date,
                    Finance.description.ilike(f"%{busca_lower}%"),
                )
            )
            .order_by(Finance.transaction_date.desc())
        )

        transactions = query.all()

        total_income = sum(t.amount for t in transactions if t.type == FinanceType.INCOME)
        total_expenses = sum(t.amount for t in transactions if t.type == FinanceType.EXPENSE)

        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "search_term": busca,
            "transactions": [
                {
                    "id": t.id,
                    "description": t.description,
                    "amount": float(t.amount),
                    "type": t.type.value,
                    "date": t.transaction_date.isoformat(),
                }
                for t in transactions
            ],
            "summary": {
                "total_income": float(total_income),
                "total_expenses": float(total_expenses),
                "count": len(transactions),
            },
        }

    def get_top_transactions(
        self,
        user_id: int,
        limit: int = 10,
        tipo: str = "expense",
        periodo: str = "mes",
        ordenacao: str = "maior",
    ) -> Dict[str, Any]:
        """
        Retorna as N maiores/menores transações.

        Args:
            user_id: ID do usuário
            limit: Quantidade de transações
            tipo: 'expense', 'income' ou 'all'
            periodo: 'hoje', 'semana', 'mes', 'ano'
            ordenacao: 'maior' ou 'menor'

        Returns:
            Dict com transações ordenadas
        """
        start_date, end_date = parse_period_to_dates(periodo)

        query = self.db.query(Finance).filter(
            and_(
                Finance.user_id == user_id,
                Finance.transaction_date >= start_date,
                Finance.transaction_date <= end_date,
            )
        )

        # Filtrar por tipo
        if tipo == "expense":
            query = query.filter(Finance.type == FinanceType.EXPENSE)
        elif tipo == "income":
            query = query.filter(Finance.type == FinanceType.INCOME)

        # Ordenar
        if ordenacao == "maior":
            query = query.order_by(Finance.amount.desc())
        else:
            query = query.order_by(Finance.amount.asc())

        transactions = query.limit(limit).all()

        total = sum(t.amount for t in transactions)

        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "query": {
                "limit": limit,
                "tipo": tipo,
                "ordenacao": ordenacao,
            },
            "transactions": [
                {
                    "id": t.id,
                    "description": t.description,
                    "amount": float(t.amount),
                    "type": t.type.value,
                    "category": t.category.value if t.category else "outros",
                    "date": t.transaction_date.isoformat(),
                }
                for t in transactions
            ],
            "total": float(total),
            "count": len(transactions),
        }

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
