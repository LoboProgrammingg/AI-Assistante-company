"""
Testes para endpoints de usuários.
"""
import pytest
from fastapi.testclient import TestClient


class TestCreateUser:
    """Testes de criação de usuário."""

    def test_create_user_success(self, client: TestClient):
        """Deve criar usuário com sucesso."""
        response = client.post("/api/v1/users/", json={
            "phone_number": "+5511777777777",
            "name": "Novo Usuário",
            "timezone": "America/Sao_Paulo",
        })
        
        assert response.status_code == 201
        data = response.json()
        assert data["phone_number"] == "+5511777777777"
        assert data["name"] == "Novo Usuário"
        assert "id" in data
        assert "session_id" in data

    def test_create_user_duplicate_phone(self, client: TestClient, sample_user):
        """Não deve criar usuário com telefone duplicado."""
        response = client.post("/api/v1/users/", json={
            "phone_number": sample_user.phone_number,
            "name": "Duplicado",
        })
        
        assert response.status_code == 400
        assert "já existe" in response.json()["detail"]

    def test_create_user_minimal_data(self, client: TestClient):
        """Deve criar usuário com dados mínimos."""
        response = client.post("/api/v1/users/", json={
            "phone_number": "+5511666666666",
        })
        
        assert response.status_code == 201


class TestGetCurrentUser:
    """Testes de obter usuário atual."""

    def test_get_me_success(self, client: TestClient, sample_user, auth_headers):
        """Deve retornar dados do usuário autenticado."""
        response = client.get("/api/v1/users/me", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_user.id
        assert data["phone_number"] == sample_user.phone_number

    def test_get_me_unauthorized(self, client: TestClient):
        """Deve retornar 401 sem token."""
        response = client.get("/api/v1/users/me")
        
        assert response.status_code == 401

    def test_get_me_invalid_token(self, client: TestClient):
        """Deve retornar 401 com token inválido."""
        response = client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer invalid_token"}
        )
        
        assert response.status_code == 401


class TestUpdateUser:
    """Testes de atualização de usuário."""

    def test_update_me_success(self, client: TestClient, auth_headers):
        """Deve atualizar dados do usuário."""
        response = client.put(
            "/api/v1/users/me",
            headers=auth_headers,
            json={"name": "Nome Atualizado"}
        )
        
        assert response.status_code == 200
        assert response.json()["name"] == "Nome Atualizado"

    def test_update_me_timezone(self, client: TestClient, auth_headers):
        """Deve atualizar timezone."""
        response = client.put(
            "/api/v1/users/me",
            headers=auth_headers,
            json={"timezone": "America/Fortaleza"}
        )
        
        assert response.status_code == 200
        assert response.json()["timezone"] == "America/Fortaleza"


class TestUserStats:
    """Testes de estatísticas do usuário."""

    def test_get_stats_success(self, client: TestClient, auth_headers):
        """Deve retornar estatísticas."""
        response = client.get("/api/v1/users/me/stats", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "total_reminders" in data
        assert "total_transactions" in data
        assert "total_meetings" in data


class TestUserByPhone:
    """Testes de busca por telefone."""

    def test_get_by_phone_success(self, client: TestClient, sample_user):
        """Deve encontrar usuário por telefone."""
        response = client.get(f"/api/v1/users/by-phone/{sample_user.phone_number}")
        
        assert response.status_code == 200
        assert response.json()["id"] == sample_user.id

    def test_get_by_phone_not_found(self, client: TestClient):
        """Deve retornar 404 para telefone inexistente."""
        response = client.get("/api/v1/users/by-phone/+5500000000000")
        
        assert response.status_code == 404
