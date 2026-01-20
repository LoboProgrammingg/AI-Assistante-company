"""
Configuração global de testes para IRIS.
"""
import os
import pytest
from datetime import datetime, timezone
from typing import Generator
from unittest.mock import MagicMock, AsyncMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient

# Configurar ambiente de teste
os.environ["TESTING"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["GOOGLE_API_KEY"] = "test-api-key"

from app.main import app
from app.database import Base, get_db
from app.models import User, Reminder, Finance, Meeting, Contact
from app.config import settings


# Banco de dados de teste (SQLite em memória)
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override do get_db para testes."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Cria tabelas antes dos testes e limpa depois."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    # Remover arquivo de teste
    if os.path.exists("./test.db"):
        os.remove("./test.db")


@pytest.fixture
def db() -> Generator[Session, None, None]:
    """Fixture de sessão do banco de dados."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture
def client(db: Session) -> TestClient:
    """Cliente de teste FastAPI."""
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db: Session) -> User:
    """Cria usuário de teste."""
    user = User(
        phone_number="+5511999999999",
        name="Usuário Teste",
        email="teste@teste.com",
        hashed_password="$2b$12$test_hash",
        is_active=True,
        is_verified=True,
        timezone="America/Sao_Paulo",
        created_at=datetime.now(timezone.utc)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict:
    """Headers de autenticação para testes."""
    from jose import jwt
    from datetime import timedelta
    
    token = jwt.encode(
        {"sub": str(test_user.id), "exp": datetime.utcnow() + timedelta(hours=1)},
        settings.SECRET_KEY,
        algorithm="HS256"
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_llm():
    """Mock do LLM para testes."""
    mock = MagicMock()
    mock.invoke = MagicMock(return_value=MagicMock(content="Resposta de teste"))
    mock.ainvoke = AsyncMock(return_value=MagicMock(content="Resposta de teste"))
    return mock


@pytest.fixture
def sample_reminder(db: Session, test_user: User) -> Reminder:
    """Cria lembrete de teste."""
    from app.models import RecurrenceType
    
    reminder = Reminder(
        user_id=test_user.id,
        title="Lembrete Teste",
        description="Descrição do lembrete",
        scheduled_time=datetime.now(timezone.utc),
        actual_reminder_time=datetime.now(timezone.utc),
        recurrence_type=RecurrenceType.ONCE,
        is_active=True,
        is_completed=False
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


@pytest.fixture
def sample_finance(db: Session, test_user: User) -> Finance:
    """Cria transação financeira de teste."""
    from app.models import FinanceType
    
    finance = Finance(
        user_id=test_user.id,
        type=FinanceType.EXPENSE,
        amount=50.0,
        description="Almoço teste",
        category_id=None,
        transaction_date=datetime.now(timezone.utc).date(),
        is_recurring=False
    )
    db.add(finance)
    db.commit()
    db.refresh(finance)
    return finance
