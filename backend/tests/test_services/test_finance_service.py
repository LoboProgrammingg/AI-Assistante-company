"""
Testes para FinanceService.
"""
import pytest
from datetime import date, timedelta

from app.services import FinanceService
from app.schemas import FinanceCreate, FinanceUpdate, FinanceTypeEnum
from app.models import User, Finance, FinanceCategory, FinanceType


class TestFinanceServiceCreate:
    """Testes de criação de transações."""

    def test_create_expense_success(self, db, sample_user, sample_expense_category):
        """Deve criar despesa com sucesso."""
        service = FinanceService(db)
        
        data = FinanceCreate(
            type=FinanceTypeEnum.EXPENSE,
            amount=150.50,
            description="Supermercado",
            category_id=sample_expense_category.id,
            transaction_date=date.today(),
        )
        
        finance = service.create(sample_user.id, data)
        
        assert finance.id is not None
        assert finance.type == FinanceType.EXPENSE
        assert finance.amount == 150.50
        assert finance.user_id == sample_user.id

    def test_create_income_success(self, db, sample_user, sample_income_category):
        """Deve criar receita com sucesso."""
        service = FinanceService(db)
        
        data = FinanceCreate(
            type=FinanceTypeEnum.INCOME,
            amount=5000.00,
            description="Salário mensal",
            category_id=sample_income_category.id,
            transaction_date=date.today(),
        )
        
        finance = service.create(sample_user.id, data)
        
        assert finance.type == FinanceType.INCOME
        assert finance.amount == 5000.00

    def test_create_with_tags(self, db, sample_user):
        """Deve criar transação com tags."""
        service = FinanceService(db)
        
        data = FinanceCreate(
            type=FinanceTypeEnum.EXPENSE,
            amount=30.00,
            description="Uber",
            transaction_date=date.today(),
            tags=["transporte", "trabalho"],
        )
        
        finance = service.create(sample_user.id, data)
        
        assert finance.tags == ["transporte", "trabalho"]


class TestFinanceServiceRead:
    """Testes de leitura de transações."""

    def test_get_by_id_success(self, db, sample_user, sample_finance):
        """Deve buscar transação por ID."""
        service = FinanceService(db)
        
        finance = service.get_by_id(sample_finance.id, sample_user.id)
        
        assert finance is not None
        assert finance.id == sample_finance.id

    def test_get_by_id_wrong_user(self, db, sample_user_2, sample_finance):
        """Não deve retornar transação de outro usuário."""
        service = FinanceService(db)
        
        finance = service.get_by_id(sample_finance.id, sample_user_2.id)
        
        assert finance is None

    def test_list_transactions_with_filters(self, db, sample_user, sample_finance):
        """Deve listar transações com filtros."""
        service = FinanceService(db)
        
        transactions, total = service.list_transactions(
            user_id=sample_user.id,
            finance_type="expense",
            start_date=date.today() - timedelta(days=1),
            end_date=date.today() + timedelta(days=1),
        )
        
        assert total >= 1
        assert all(t.type == FinanceType.EXPENSE for t in transactions)


class TestFinanceServiceUpdate:
    """Testes de atualização de transações."""

    def test_update_amount_success(self, db, sample_user, sample_finance):
        """Deve atualizar valor da transação."""
        service = FinanceService(db)
        
        data = FinanceUpdate(amount=75.00)
        
        updated = service.update(sample_finance.id, sample_user.id, data)
        
        assert updated is not None
        assert updated.amount == 75.00

    def test_update_description(self, db, sample_user, sample_finance):
        """Deve atualizar descrição."""
        service = FinanceService(db)
        
        data = FinanceUpdate(description="Nova descrição")
        
        updated = service.update(sample_finance.id, sample_user.id, data)
        
        assert updated.description == "Nova descrição"


class TestFinanceServiceDelete:
    """Testes de remoção de transações."""

    def test_delete_success(self, db, sample_user, sample_finance):
        """Deve remover transação."""
        service = FinanceService(db)
        
        result = service.delete(sample_finance.id, sample_user.id)
        
        assert result is True
        
        finance = service.get_by_id(sample_finance.id, sample_user.id)
        assert finance is None

    def test_delete_not_found(self, db, sample_user):
        """Deve retornar False para ID inexistente."""
        service = FinanceService(db)
        
        result = service.delete(99999, sample_user.id)
        
        assert result is False


class TestFinanceServiceSummary:
    """Testes de resumo financeiro."""

    def test_get_summary_with_transactions(self, db, sample_user, sample_expense_category, sample_income_category):
        """Deve calcular resumo corretamente."""
        service = FinanceService(db)
        
        service.create(sample_user.id, FinanceCreate(
            type=FinanceTypeEnum.INCOME,
            amount=1000.00,
            transaction_date=date.today(),
            category_id=sample_income_category.id,
        ))
        
        service.create(sample_user.id, FinanceCreate(
            type=FinanceTypeEnum.EXPENSE,
            amount=300.00,
            transaction_date=date.today(),
            category_id=sample_expense_category.id,
        ))
        
        summary = service.get_summary(
            sample_user.id,
            start_date=date.today() - timedelta(days=1),
            end_date=date.today() + timedelta(days=1),
        )
        
        assert summary["summary"]["total_income"] == 1000.00
        assert summary["summary"]["total_expenses"] == 300.00
        assert summary["summary"]["balance"] == 700.00

    def test_get_monthly_summary(self, db, sample_user, sample_finance):
        """Deve retornar resumo mensal."""
        service = FinanceService(db)
        
        today = date.today()
        summary = service.get_monthly_summary(sample_user.id, today.year, today.month)
        
        assert "period" in summary
        assert "summary" in summary


class TestFinanceServiceTrend:
    """Testes de tendência."""

    def test_get_monthly_trend(self, db, sample_user):
        """Deve retornar tendência mensal."""
        service = FinanceService(db)
        
        trend = service.get_monthly_trend(sample_user.id, months=3)
        
        assert len(trend) == 3
        assert all("month" in item for item in trend)


class TestFinanceServiceCategories:
    """Testes de categorias."""

    def test_get_categories(self, db, sample_expense_category, sample_income_category):
        """Deve retornar categorias organizadas por tipo."""
        service = FinanceService(db)
        
        categories = service.get_categories()
        
        assert "expense_categories" in categories
        assert "income_categories" in categories
