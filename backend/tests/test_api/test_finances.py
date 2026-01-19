"""
Testes para endpoints de finanças.
"""
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient


class TestCreateTransaction:
    """Testes de criação de transação."""

    def test_create_expense_success(self, client: TestClient, auth_headers):
        """Deve criar despesa."""
        response = client.post(
            "/api/v1/finances/",
            headers=auth_headers,
            json={
                "type": "expense",
                "amount": 150.00,
                "description": "Supermercado",
                "transaction_date": date.today().isoformat(),
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["type"] == "expense"
        assert data["amount"] == 150.00

    def test_create_income_success(self, client: TestClient, auth_headers):
        """Deve criar receita."""
        response = client.post(
            "/api/v1/finances/",
            headers=auth_headers,
            json={
                "type": "income",
                "amount": 5000.00,
                "description": "Salário",
                "transaction_date": date.today().isoformat(),
            }
        )
        
        assert response.status_code == 201
        assert response.json()["type"] == "income"


class TestListTransactions:
    """Testes de listagem de transações."""

    def test_list_transactions_success(self, client: TestClient, auth_headers, sample_finance):
        """Deve listar transações."""
        response = client.get("/api/v1/finances/", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["total"] >= 1

    def test_list_transactions_filter_type(self, client: TestClient, auth_headers):
        """Deve filtrar por tipo."""
        response = client.get(
            "/api/v1/finances/",
            headers=auth_headers,
            params={"type": "expense"}
        )
        
        assert response.status_code == 200

    def test_list_transactions_filter_dates(self, client: TestClient, auth_headers):
        """Deve filtrar por período."""
        response = client.get(
            "/api/v1/finances/",
            headers=auth_headers,
            params={
                "start_date": (date.today() - timedelta(days=30)).isoformat(),
                "end_date": date.today().isoformat(),
            }
        )
        
        assert response.status_code == 200


class TestGetTransaction:
    """Testes de obter transação."""

    def test_get_transaction_success(self, client: TestClient, auth_headers, sample_finance):
        """Deve retornar transação."""
        response = client.get(
            f"/api/v1/finances/{sample_finance.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.json()["id"] == sample_finance.id

    def test_get_transaction_not_found(self, client: TestClient, auth_headers):
        """Deve retornar 404."""
        response = client.get("/api/v1/finances/99999", headers=auth_headers)
        
        assert response.status_code == 404


class TestUpdateTransaction:
    """Testes de atualização."""

    def test_update_amount_success(self, client: TestClient, auth_headers, sample_finance):
        """Deve atualizar valor."""
        response = client.put(
            f"/api/v1/finances/{sample_finance.id}",
            headers=auth_headers,
            json={"amount": 75.00}
        )
        
        assert response.status_code == 200
        assert response.json()["amount"] == 75.00


class TestDeleteTransaction:
    """Testes de remoção."""

    def test_delete_success(self, client: TestClient, auth_headers, sample_finance):
        """Deve remover transação."""
        response = client.delete(
            f"/api/v1/finances/{sample_finance.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 204


class TestFinanceSummary:
    """Testes de resumo financeiro."""

    def test_get_summary_success(self, client: TestClient, auth_headers):
        """Deve retornar resumo."""
        response = client.get(
            "/api/v1/finances/summary",
            headers=auth_headers,
            params={
                "start_date": (date.today() - timedelta(days=30)).isoformat(),
                "end_date": date.today().isoformat(),
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "period" in data
        assert "summary" in data

    def test_get_monthly_summary(self, client: TestClient, auth_headers):
        """Deve retornar resumo mensal."""
        today = date.today()
        response = client.get(
            "/api/v1/finances/summary/monthly",
            headers=auth_headers,
            params={"year": today.year, "month": today.month}
        )
        
        assert response.status_code == 200


class TestFinanceTrend:
    """Testes de tendência."""

    def test_get_trend_success(self, client: TestClient, auth_headers):
        """Deve retornar tendência."""
        response = client.get(
            "/api/v1/finances/trend",
            headers=auth_headers,
            params={"months": 6}
        )
        
        assert response.status_code == 200
        assert "data" in response.json()


class TestCategories:
    """Testes de categorias."""

    def test_get_categories_success(self, client: TestClient, sample_expense_category):
        """Deve retornar categorias."""
        response = client.get("/api/v1/finances/categories")
        
        assert response.status_code == 200
        data = response.json()
        assert "expense_categories" in data
        assert "income_categories" in data
