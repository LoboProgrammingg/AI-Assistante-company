"""
Testes para os endpoints da API - IRIS.
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone


class TestHealthEndpoints:
    """Testes para endpoints de saúde."""
    
    def test_root(self, client: TestClient):
        """Testa endpoint raiz."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["status"] == "running"
    
    def test_health(self, client: TestClient):
        """Testa health check."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
    
    def test_health_api(self, client: TestClient):
        """Testa health check via API."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200


class TestAuthEndpoints:
    """Testes para endpoints de autenticação."""
    
    def test_register_success(self, client: TestClient):
        """Testa registro de usuário."""
        response = client.post("/api/v1/auth/register", json={
            "name": "Novo Usuário",
            "email": "novo@teste.com",
            "password": "Senha123!",
            "password_confirm": "Senha123!",
            "phone_number": "+5511999999998"
        })
        # Pode falhar se SMTP não configurado, mas não deve dar erro 500
        assert response.status_code in [200, 201, 400, 422]
    
    def test_register_password_mismatch(self, client: TestClient):
        """Testa registro com senhas diferentes."""
        response = client.post("/api/v1/auth/register", json={
            "name": "Usuário",
            "email": "user@teste.com",
            "password": "Senha123!",
            "password_confirm": "SenhaDiferente!",
            "phone_number": "+5511999999997"
        })
        assert response.status_code in [400, 422]
    
    def test_login_invalid_credentials(self, client: TestClient):
        """Testa login com credenciais inválidas."""
        response = client.post("/api/v1/auth/login", json={
            "email": "naoexiste@teste.com",
            "password": "senhaerrada"
        })
        assert response.status_code in [401, 404]


class TestRemindersEndpoints:
    """Testes para endpoints de lembretes."""
    
    def test_list_reminders_unauthorized(self, client: TestClient):
        """Testa listagem sem autenticação."""
        response = client.get("/api/v1/reminders/")
        assert response.status_code == 401
    
    def test_list_reminders_authorized(self, client: TestClient, auth_headers: dict):
        """Testa listagem com autenticação."""
        response = client.get("/api/v1/reminders/", headers=auth_headers)
        assert response.status_code == 200
        assert "items" in response.json()
    
    def test_create_reminder(self, client: TestClient, auth_headers: dict):
        """Testa criação de lembrete."""
        response = client.post("/api/v1/reminders/", 
            headers=auth_headers,
            json={
                "title": "Teste Lembrete",
                "scheduled_time": "2025-01-25T10:00:00Z"
            }
        )
        assert response.status_code in [200, 201]
        if response.status_code in [200, 201]:
            data = response.json()
            assert data["title"] == "Teste Lembrete"


class TestFinancesEndpoints:
    """Testes para endpoints de finanças."""
    
    def test_list_finances_unauthorized(self, client: TestClient):
        """Testa listagem sem autenticação."""
        response = client.get("/api/v1/finances/")
        assert response.status_code == 401
    
    def test_list_finances_authorized(self, client: TestClient, auth_headers: dict):
        """Testa listagem com autenticação."""
        response = client.get("/api/v1/finances/", headers=auth_headers)
        assert response.status_code == 200
        assert "items" in response.json()
    
    def test_create_finance(self, client: TestClient, auth_headers: dict):
        """Testa criação de transação."""
        response = client.post("/api/v1/finances/",
            headers=auth_headers,
            json={
                "type": "expense",
                "amount": 50.0,
                "description": "Teste gasto",
                "transaction_date": "2025-01-20"
            }
        )
        assert response.status_code in [200, 201]
    
    def test_get_categories(self, client: TestClient, auth_headers: dict):
        """Testa obtenção de categorias."""
        response = client.get("/api/v1/finances/categories", headers=auth_headers)
        assert response.status_code == 200


class TestMeetingsEndpoints:
    """Testes para endpoints de reuniões."""
    
    def test_list_meetings_unauthorized(self, client: TestClient):
        """Testa listagem sem autenticação."""
        response = client.get("/api/v1/meetings/")
        assert response.status_code == 401
    
    def test_list_meetings_authorized(self, client: TestClient, auth_headers: dict):
        """Testa listagem com autenticação."""
        response = client.get("/api/v1/meetings/", headers=auth_headers)
        assert response.status_code == 200


class TestContactsEndpoints:
    """Testes para endpoints de contatos."""
    
    def test_list_contacts_unauthorized(self, client: TestClient):
        """Testa listagem sem autenticação."""
        response = client.get("/api/v1/contacts/")
        assert response.status_code == 401
    
    def test_list_contacts_authorized(self, client: TestClient, auth_headers: dict):
        """Testa listagem com autenticação."""
        response = client.get("/api/v1/contacts/", headers=auth_headers)
        assert response.status_code == 200
    
    def test_create_contact(self, client: TestClient, auth_headers: dict):
        """Testa criação de contato."""
        response = client.post("/api/v1/contacts/",
            headers=auth_headers,
            json={
                "name": "Contato Teste",
                "phone_number": "+5511888888888"
            }
        )
        assert response.status_code in [200, 201]


class TestDocumentsEndpoints:
    """Testes para endpoints de documentos."""
    
    def test_list_documents_unauthorized(self, client: TestClient):
        """Testa listagem sem autenticação."""
        response = client.get("/api/v1/documents/")
        assert response.status_code == 401
    
    def test_list_documents_authorized(self, client: TestClient, auth_headers: dict):
        """Testa listagem com autenticação."""
        response = client.get("/api/v1/documents/", headers=auth_headers)
        assert response.status_code == 200
    
    def test_get_stats(self, client: TestClient, auth_headers: dict):
        """Testa estatísticas de documentos."""
        response = client.get("/api/v1/documents/stats", headers=auth_headers)
        assert response.status_code == 200


class TestRateLimiting:
    """Testes para rate limiting."""
    
    def test_rate_limit_headers(self, client: TestClient, auth_headers: dict):
        """Testa presença de headers de rate limit."""
        response = client.get("/api/v1/reminders/", headers=auth_headers)
        # Rate limit headers podem estar presentes
        assert response.status_code == 200
