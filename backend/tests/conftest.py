"""
Configurações e fixtures para testes.
"""
import os
import sys

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["TESTING"] = "true"

import pytest
from datetime import datetime, date
from typing import Generator
from unittest.mock import MagicMock, AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool


SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

from app.models import Base, User, Reminder, Finance, FinanceCategory, Meeting, Message
from app.models import RecurrenceType, FinanceType


@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """
    Cria uma sessão de banco de dados limpa para cada teste.
    """
    Base.metadata.create_all(bind=engine)
    
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db: Session) -> Generator:
    """
    Cliente de teste do FastAPI com banco de dados de teste.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api import api_router
    
    test_app = FastAPI()
    test_app.include_router(api_router, prefix="/api/v1")
    
    def override_get_db():
        try:
            yield db
        finally:
            pass
    
    from app.api.deps import get_db
    test_app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(test_app) as test_client:
        yield test_client
    
    test_app.dependency_overrides.clear()


@pytest.fixture
def sample_user(db: Session) -> User:
    """
    Cria um usuário de teste.
    """
    user = User(
        phone_number="+5511999999999",
        name="Usuário Teste",
        session_id="test-session-123",
        timezone="America/Sao_Paulo",
        language="pt-BR",
        preferences={"notifications": True},
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def sample_user_2(db: Session) -> User:
    """
    Cria um segundo usuário de teste.
    """
    user = User(
        phone_number="+5511888888888",
        name="Outro Usuário",
        session_id="test-session-456",
        timezone="America/Sao_Paulo",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def sample_reminder(db: Session, sample_user: User) -> Reminder:
    """
    Cria um lembrete de teste.
    """
    reminder = Reminder(
        user_id=sample_user.id,
        title="Lembrete de Teste",
        description="Descrição do lembrete",
        scheduled_time=datetime(2026, 1, 20, 14, 0, 0),
        remind_before_minutes=30,
        actual_reminder_time=datetime(2026, 1, 20, 13, 30, 0),
        recurrence_type=RecurrenceType.ONCE,
        is_active=True,
        is_completed=False,
        notified=False,
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


@pytest.fixture
def sample_expense_category(db: Session) -> FinanceCategory:
    """
    Cria uma categoria de despesa.
    """
    category = FinanceCategory(
        name="Alimentação",
        type=FinanceType.EXPENSE,
        icon="🍔",
        color="#FF6B6B",
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@pytest.fixture
def sample_income_category(db: Session) -> FinanceCategory:
    """
    Cria uma categoria de receita.
    """
    category = FinanceCategory(
        name="Salário",
        type=FinanceType.INCOME,
        icon="💰",
        color="#4ECDC4",
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@pytest.fixture
def sample_finance(
    db: Session,
    sample_user: User,
    sample_expense_category: FinanceCategory
) -> Finance:
    """
    Cria uma transação financeira de teste.
    """
    finance = Finance(
        user_id=sample_user.id,
        type=FinanceType.EXPENSE,
        amount=50.00,
        description="Almoço",
        category_id=sample_expense_category.id,
        transaction_date=date.today(),
        is_recurring=False,
        tags=["alimentação", "trabalho"],
    )
    db.add(finance)
    db.commit()
    db.refresh(finance)
    return finance


@pytest.fixture
def sample_meeting(db: Session, sample_user: User) -> Meeting:
    """
    Cria uma reunião de teste.
    """
    meeting = Meeting(
        user_id=sample_user.id,
        title="Reunião de Planejamento",
        date=datetime.now(),
        duration_minutes=60,
        summary="Discussão sobre próximos passos do projeto.",
        key_topics=[
            {"topic": "Cronograma", "summary": "Definição de prazos"},
            {"topic": "Recursos", "summary": "Alocação de equipe"},
        ],
        action_items=[
            {"task": "Enviar proposta", "responsible": "João", "status": "pending"},
            {"task": "Revisar documentação", "responsible": "Maria", "status": "pending"},
        ],
        participants=[
            {"name": "João", "role": "Gerente"},
            {"name": "Maria", "role": "Desenvolvedora"},
        ],
        decisions=[
            {"decision": "Aprovar orçamento", "context": "Após revisão"},
        ],
        sentiment="positive",
        keywords=["projeto", "planejamento", "cronograma"],
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return meeting


@pytest.fixture
def sample_message(db: Session, sample_user: User) -> Message:
    """
    Cria uma mensagem de teste.
    """
    message = Message(
        user_id=sample_user.id,
        message_type="text",
        content="Olá, quero criar um lembrete",
        direction="incoming",
        wa_message_id="wa_msg_123",
        intent="reminder",
        entities={"reminder": {"title": "Teste"}},
        ai_response="Lembrete criado!",
        processed_at=datetime.utcnow(),
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


@pytest.fixture
def auth_headers(sample_user: User) -> dict:
    """
    Retorna headers de autenticação para testes de API.
    """
    from app.api.deps import create_access_token
    
    token = create_access_token(sample_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_llm() -> MagicMock:
    """
    Mock do LLM para testes de agentes.
    """
    mock = MagicMock()
    mock.invoke = MagicMock(return_value=MagicMock(
        content='{"intent": "general", "confidence": 0.9}'
    ))
    mock.ainvoke = AsyncMock(return_value=MagicMock(
        content='{"intent": "general", "confidence": 0.9}'
    ))
    return mock
