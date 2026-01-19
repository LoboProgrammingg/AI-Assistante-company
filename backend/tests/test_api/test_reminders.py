"""
Testes para endpoints de lembretes.
"""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient


class TestCreateReminder:
    """Testes de criação de lembrete via API."""

    def test_create_reminder_success(self, client: TestClient, auth_headers):
        """Deve criar lembrete com sucesso."""
        scheduled = (datetime.now() + timedelta(days=1)).isoformat()
        
        response = client.post(
            "/api/v1/reminders/",
            headers=auth_headers,
            json={
                "title": "Reunião com cliente",
                "description": "Discutir proposta",
                "scheduled_time": scheduled,
                "remind_before_minutes": 30,
                "recurrence_type": "once",
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Reunião com cliente"
        assert data["is_active"] is True

    def test_create_reminder_unauthorized(self, client: TestClient):
        """Deve retornar 401 sem autenticação."""
        response = client.post("/api/v1/reminders/", json={
            "title": "Teste",
            "scheduled_time": datetime.now().isoformat(),
        })
        
        assert response.status_code == 401


class TestListReminders:
    """Testes de listagem de lembretes."""

    def test_list_reminders_success(self, client: TestClient, auth_headers, sample_reminder):
        """Deve listar lembretes."""
        response = client.get("/api/v1/reminders/", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_list_reminders_pagination(self, client: TestClient, auth_headers):
        """Deve suportar paginação."""
        response = client.get(
            "/api/v1/reminders/",
            headers=auth_headers,
            params={"page": 1, "limit": 5}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "page" in data
        assert "pages" in data
        assert "has_next" in data

    def test_list_reminders_filter_status(self, client: TestClient, auth_headers):
        """Deve filtrar por status."""
        response = client.get(
            "/api/v1/reminders/",
            headers=auth_headers,
            params={"status": "active"}
        )
        
        assert response.status_code == 200


class TestGetReminder:
    """Testes de obter lembrete específico."""

    def test_get_reminder_success(self, client: TestClient, auth_headers, sample_reminder):
        """Deve retornar lembrete por ID."""
        response = client.get(
            f"/api/v1/reminders/{sample_reminder.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.json()["id"] == sample_reminder.id

    def test_get_reminder_not_found(self, client: TestClient, auth_headers):
        """Deve retornar 404 para ID inexistente."""
        response = client.get("/api/v1/reminders/99999", headers=auth_headers)
        
        assert response.status_code == 404


class TestUpdateReminder:
    """Testes de atualização de lembrete."""

    def test_update_reminder_success(self, client: TestClient, auth_headers, sample_reminder):
        """Deve atualizar lembrete."""
        response = client.put(
            f"/api/v1/reminders/{sample_reminder.id}",
            headers=auth_headers,
            json={"title": "Título Atualizado"}
        )
        
        assert response.status_code == 200
        assert response.json()["title"] == "Título Atualizado"


class TestDeleteReminder:
    """Testes de remoção de lembrete."""

    def test_delete_reminder_success(self, client: TestClient, auth_headers, sample_reminder):
        """Deve remover lembrete."""
        response = client.delete(
            f"/api/v1/reminders/{sample_reminder.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 204

    def test_delete_reminder_not_found(self, client: TestClient, auth_headers):
        """Deve retornar 404 para ID inexistente."""
        response = client.delete("/api/v1/reminders/99999", headers=auth_headers)
        
        assert response.status_code == 404


class TestCompleteReminder:
    """Testes de conclusão de lembrete."""

    def test_complete_reminder_success(self, client: TestClient, auth_headers, sample_reminder):
        """Deve marcar como concluído."""
        response = client.post(
            f"/api/v1/reminders/{sample_reminder.id}/complete",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.json()["is_completed"] is True


class TestUpcomingReminders:
    """Testes de lembretes próximos."""

    def test_get_upcoming_success(self, client: TestClient, auth_headers):
        """Deve retornar lembretes próximos."""
        response = client.get(
            "/api/v1/reminders/upcoming",
            headers=auth_headers,
            params={"hours": 48}
        )
        
        assert response.status_code == 200
        assert "items" in response.json()
        assert "count" in response.json()
