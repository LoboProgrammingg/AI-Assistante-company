"""
Testes para endpoints de reuniões.
"""
import pytest
from datetime import datetime
from fastapi.testclient import TestClient


class TestCreateMeeting:
    """Testes de criação de reunião."""

    def test_create_meeting_success(self, client: TestClient, auth_headers):
        """Deve criar reunião."""
        response = client.post(
            "/api/v1/meetings/",
            headers=auth_headers,
            json={
                "title": "Sprint Planning",
                "date": datetime.now().isoformat(),
                "duration_minutes": 60,
                "summary": "Planejamento da sprint 10.",
                "key_topics": ["Backend", "Frontend"],
                "participants": ["João", "Maria"],
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Sprint Planning"

    def test_create_meeting_minimal(self, client: TestClient, auth_headers):
        """Deve criar reunião com dados mínimos."""
        response = client.post(
            "/api/v1/meetings/",
            headers=auth_headers,
            json={}
        )
        
        assert response.status_code == 201


class TestListMeetings:
    """Testes de listagem."""

    def test_list_meetings_success(self, client: TestClient, auth_headers, sample_meeting):
        """Deve listar reuniões."""
        response = client.get("/api/v1/meetings/", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["total"] >= 1

    def test_list_meetings_pagination(self, client: TestClient, auth_headers):
        """Deve suportar paginação."""
        response = client.get(
            "/api/v1/meetings/",
            headers=auth_headers,
            params={"page": 1, "limit": 10}
        )
        
        assert response.status_code == 200
        assert "page" in response.json()


class TestGetMeeting:
    """Testes de obter reunião."""

    def test_get_meeting_success(self, client: TestClient, auth_headers, sample_meeting):
        """Deve retornar reunião."""
        response = client.get(
            f"/api/v1/meetings/{sample_meeting.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_meeting.id
        assert "key_topics" in data
        assert "action_items" in data

    def test_get_meeting_not_found(self, client: TestClient, auth_headers):
        """Deve retornar 404."""
        response = client.get("/api/v1/meetings/99999", headers=auth_headers)
        
        assert response.status_code == 404


class TestUpdateMeeting:
    """Testes de atualização."""

    def test_update_title_success(self, client: TestClient, auth_headers, sample_meeting):
        """Deve atualizar título."""
        response = client.put(
            f"/api/v1/meetings/{sample_meeting.id}",
            headers=auth_headers,
            json={"title": "Título Atualizado"}
        )
        
        assert response.status_code == 200
        assert response.json()["title"] == "Título Atualizado"

    def test_update_summary(self, client: TestClient, auth_headers, sample_meeting):
        """Deve atualizar resumo."""
        response = client.put(
            f"/api/v1/meetings/{sample_meeting.id}",
            headers=auth_headers,
            json={"summary": "Novo resumo."}
        )
        
        assert response.status_code == 200


class TestDeleteMeeting:
    """Testes de remoção."""

    def test_delete_success(self, client: TestClient, auth_headers, sample_meeting):
        """Deve remover reunião."""
        response = client.delete(
            f"/api/v1/meetings/{sample_meeting.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 204


class TestSearchMeetings:
    """Testes de busca."""

    def test_search_success(self, client: TestClient, auth_headers, sample_meeting):
        """Deve buscar por termo."""
        response = client.get(
            "/api/v1/meetings/search",
            headers=auth_headers,
            params={"q": "Planejamento"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "count" in data

    def test_search_min_length(self, client: TestClient, auth_headers):
        """Deve exigir tamanho mínimo."""
        response = client.get(
            "/api/v1/meetings/search",
            headers=auth_headers,
            params={"q": "a"}
        )
        
        assert response.status_code == 422


class TestActionItems:
    """Testes de action items."""

    def test_get_pending_action_items(self, client: TestClient, auth_headers, sample_meeting):
        """Deve retornar itens pendentes."""
        response = client.get(
            "/api/v1/meetings/action-items/pending",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "count" in data

    def test_update_action_item_status(self, client: TestClient, auth_headers, sample_meeting):
        """Deve atualizar status do item."""
        response = client.patch(
            f"/api/v1/meetings/{sample_meeting.id}/action-items/0",
            headers=auth_headers,
            params={"status": "completed"}
        )
        
        assert response.status_code == 200
        assert response.json()["action_items"][0]["status"] == "completed"
